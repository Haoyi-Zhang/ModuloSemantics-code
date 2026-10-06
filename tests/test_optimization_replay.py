import json
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from semantic_certificates.builders import instruction, make_program, build, inp, node
from semantic_certificates.checker import check
from semantic_certificates.frontiers import Candidate, selection_at, obstruction_at, verify_obstruction, hybrid_at, hybrid_design_space
from semantic_certificates.logic import TruthTable, FormatError
from semantic_certificates.optimization_replay import verify_optimum
from semantic_certificates.optimization_witness import certify_budget


def example(distance=1, latency=6):
    return build(make_program([
        instruction('s', 'add', [node('s', distance), inp('x')], True, emit=True),
        instruction('t', 'div', [inp('z'), inp('y')], True, emit=True)],
        release=0, div_latency=latency, capacity=4), 'wait')


class ObstructionFormatTests(unittest.TestCase):
    def test_problem_header_is_validated_before_replay(self):
        tt = TruthTable(['p'])
        cs = [Candidate('a', 0, 0)]
        w = obstruction_at(tt, {'p': 1}, cs, 0)
        self.assertTrue(verify_obstruction(tt, {'p': 1}, cs, w))
        for releases in (None, ['p'], 'p', {}, {'q': 1}, {'p': 1, 'q': 1},
                         {'p': True}, {'p': '1'}, {'p': -1}, {'p': 4097}):
            with self.subTest(releases=releases):
                self.assertFalse(verify_obstruction(tt, releases, cs, w))
                with self.assertRaises(FormatError):
                    selection_at(tt, releases, cs, 0)

    def test_invalid_candidates_do_not_become_obstructions(self):
        tt = TruthTable(['p']); rel = {'p': 1}
        w = obstruction_at(tt, rel, [Candidate('a', 0, 0)], 0)
        bad = [None, 'a', {}, [None], [Candidate('a', True, 0)],
               [Candidate('a', -1, 0)], [Candidate('a', 8193, 0)],
               [Candidate('a', 0, True)], [Candidate('a', 0, -1)],
               [Candidate('a', 0, 4)], [Candidate('', 0, 0)],
               [Candidate('a', 0, 0), Candidate('a', 1, 0)]]
        for candidates in bad:
            with self.subTest(candidates=candidates):
                self.assertFalse(verify_obstruction(tt, rel, candidates, w))
                with self.assertRaises(FormatError):
                    selection_at(tt, rel, candidates, 0)

    def test_replay_is_not_selector_search_or_exception_suppression(self):
        tt = TruthTable(['p']); rel = {'p': 1}; cs = [Candidate('a', 0, 0)]
        w = obstruction_at(tt, rel, cs, 0)
        with patch('semantic_certificates.frontiers.selection_at', side_effect=AssertionError('search called')):
            self.assertTrue(verify_obstruction(tt, rel, cs, w))
        with patch('semantic_certificates.frontiers._validate_selection_problem', side_effect=RuntimeError('bug')):
            with self.assertRaises(RuntimeError):
                verify_obstruction(tt, rel, cs, w)


class OptimumReplayTests(unittest.TestCase):
    def test_opaque_attempt_names_survive_synthesis_and_replay(self):
        # A valid source label at the Boolean-name bound produces longer opaque
        # attempt names. Admission must not add a second, undocumented bound.
        label = 's' * 64
        base = build(make_program([
            instruction(label, 'add', [node(label, 1), inp('x')], True, emit=True),
            instruction('tail', 'div', [inp('z'), inp('y')], True, emit=True)],
            release=0, div_latency=6, capacity=4), 'wait')
        self.assertTrue(check(base).accepted)
        self.assertGreater(max(len(a['name']) for a in base['attempts']), 64)
        target, plan = hybrid_at(base, 1)
        self.assertTrue(check(target).accepted)
        self.assertEqual(plan['cells'], 1)
        proof = certify_budget(base, 1)
        replay = verify_optimum(base, 1, proof)
        self.assertTrue(replay['accepted'], replay)
        self.assertEqual(replay['minimum_period'], 1)
        tt = TruthTable([])
        candidates = [Candidate('ticket' * 12, 2, tt.all)]
        self.assertIsNotNone(selection_at(tt, {}, candidates, 2))
        witness = obstruction_at(tt, {}, candidates, 1)
        self.assertTrue(verify_obstruction(tt, {}, candidates, witness))

    def test_budget_optimum_and_zero_budget(self):
        base = example()
        for budget in (0, 1, 2, 5):
            with self.subTest(budget=budget):
                proof = certify_budget(base, budget)
                actual = verify_optimum(base, budget, proof)
                self.assertTrue(actual['accepted'], actual)
                reference = hybrid_design_space(base, cell_budget=budget)
                self.assertEqual(actual['minimum_period'], reference['minimum_budget_feasible_ii'])
                self.assertEqual(actual['scope'], 'all_positive_periods')

    def test_no_annotation_or_selector_search_in_replayer(self):
        base = example(); proof = certify_budget(base, 1)
        with patch('semantic_certificates.frontiers.hybrid_at', side_effect=AssertionError('optimization called')), \
             patch('semantic_certificates.frontiers.selection_at', side_effect=AssertionError('selection called')), \
             patch('semantic_certificates.frontiers.bank_layout', side_effect=AssertionError('layout called')):
            self.assertTrue(verify_optimum(base, 1, proof)['accepted'])

    def test_every_smaller_period_and_budget_are_bound(self):
        base = example(); proof = certify_budget(base, 0)
        self.assertGreater(proof['minimum_period'], 1)
        mutations = []
        m = deepcopy(proof); m['rows'].pop(0); mutations.append(m)
        m = deepcopy(proof); m['rows'][0]['interval'] = 2; mutations.append(m)
        m = deepcopy(proof); m['rows'].reverse(); mutations.append(m)
        m = deepcopy(proof); m['budget'] = 1; mutations.append(m)
        m = deepcopy(proof); m['minimum_period'] = True; mutations.append(m)
        for m in mutations:
            self.assertFalse(verify_optimum(base, 0, m)['accepted'])

    def test_feasible_target_cannot_change_scientific_skeleton(self):
        base = example(); proof = certify_budget(base, 1)
        self.assertTrue(verify_optimum(base, 1, proof)['accepted'])
        m = deepcopy(proof); m['rows'][-1]['certificate']['resources']['alu'] += 1
        self.assertTrue(check(m['rows'][-1]['certificate']).accepted)
        self.assertFalse(verify_optimum(base, 1, m)['accepted'])
        for amount in (-1, 1):
            m = deepcopy(proof); m['rows'][-1]['cells'] += amount
            self.assertFalse(verify_optimum(base, 1, m)['accepted'])
        m = deepcopy(proof); m['rows'][-1]['certificate']['nodes'][0]['emit'] = False
        self.assertTrue(check(m['rows'][-1]['certificate']).accepted)
        self.assertFalse(verify_optimum(base, 1, m)['accepted'])

    def test_impossible_resources_and_truncated_negative_scope(self):
        base = example()
        base['resources']['alu'] = 1
        # Two identical same-offset unconditional ALU issues force a violation
        # at every period, but leave all non-resource skeleton obligations valid.
        original = next(a for a in base['attempts'] if a['kind'] == 'op' and a['node'] == 's')
        clone = deepcopy(original); clone['name'] = 'duplicate_reservation'
        base['attempts'].append(clone)
        for retire, scope in ((base['retire'], 'all_positive_periods'), (257, 'periods_1_through_256')):
            p = deepcopy(base); p['retire'] = retire
            proof = certify_budget(p, 0)
            self.assertIsNone(proof['minimum_period'])
            out = verify_optimum(p, 0, proof)
            self.assertTrue(out['accepted'], out)
            self.assertEqual(out['scope'], scope)
            m = deepcopy(proof); m['rows'][0]['resource'] = 'nonexistent'
            self.assertFalse(verify_optimum(p, 0, m)['accepted'])

    def test_malformed_proofs_and_cli_json(self):
        base = example(); proof = certify_budget(base, 1)
        for m in (None, [], 'proof', {}, {'budget': 1, 'minimum_period': 1, 'rows': None}):
            out = verify_optimum(base, 1, m)
            self.assertFalse(out['accepted'])
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'skeleton.json'; c = Path(directory)/'proof.json'
            p.write_text(json.dumps(base))
            for payload, status in ((proof, 0), (None, 2)):
                c.write_text(json.dumps(payload))
                proc = subprocess.run([sys.executable, '-m', 'semantic_certificates.optimization_replay',
                        str(p), str(c), '--budget', '1'], cwd=root, text=True, capture_output=True, timeout=15)
                self.assertEqual(proc.returncode, status, proc.stderr)
                self.assertEqual(proc.stderr, '')
                self.assertEqual(json.loads(proc.stdout)['accepted'], status == 0)
