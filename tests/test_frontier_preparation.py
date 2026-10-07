"""Finite fixed-skeleton reuse regressions; ordinary unittest discovery includes these."""
import unittest
from copy import deepcopy
from itertools import product
from unittest.mock import patch

from semantic_certificates import frontiers as f
from semantic_certificates.builders import build, data_for, inp, instruction, make_program, node
from semantic_certificates.checker import check
from semantic_certificates.frontier_oracle import enumerate_annotations, run_tick
from semantic_certificates.reference import run_source
from semantic_certificates.target import run_target


def owned_skeleton(distance=1, latency=5, release=0):
    return build(make_program([
        instruction('s', 'add', [node('s', distance), inp('x')], True, emit=True),
        instruction('t', 'div', [inp('z'), inp('y')], True, emit=True)],
        release=release, div_latency=latency, capacity=4), 'wait')


class PreparationTests(unittest.TestCase):
    def test_independent_all_annotation_definition_and_observations(self):
        # These masks/completions follow from the unconditional source and the
        # explicitly specified wait construction, NOT checker goodness, candidate
        # preparation, production selector search or its bank-size equation.
        for distance, latency, release in product((1, 3), (2, 5), (0, 2)):
            p = owned_skeleton(distance, latency, release)
            snapshot = deepcopy(p)
            retire = release + latency + 1
            self.assertEqual(p['retire'], retire)
            candidates = {'s': [(release + 1, 15), (release + 1, 0), (release + 2, 15)]}
            wanted = {ii: enumerate_annotations([release, 0], candidates,
                      [('s', distance, release)], ii, retire)['minimum_cells']
                      for ii in range(1, retire + 1)}
            for budget in (None, 0, 1, 3):
                result = f.hybrid_design_space(p, cell_budget=budget)
                self.assertTrue(result['complete_for_unbounded_intervals'])
                admitted = []
                for row in result['rows']:
                    ii = row['ii']
                    self.assertEqual(row['admitted'], wanted[ii] is not None)
                    if row['admitted']:
                        self.assertEqual(row['cells'], wanted[ii])
                        self.assertEqual(row['fits_budget'], budget is None or wanted[ii] <= budget)
                        admitted.append(row)
                pareto = [r for r in admitted if not any(
                    s['ii'] <= r['ii'] and s['cells'] <= r['cells'] and s != r
                    for s in admitted)]
                self.assertEqual(result['pareto'], pareto)
                self.assertEqual(result['minimum_budget_feasible_ii'], min(
                    (ii for ii, cells in wanted.items() if cells is not None and
                     (budget is None or cells <= budget)), default=None))
            # Owned finite streams, including empty runs, negative initial state,
            # first division faults and equal-time export/retirement event order.
            for ii in range(1, retire + 1):
                if wanted[ii] is None:
                    continue
                q, meta = f.hybrid_at(p, ii)
                slots = {v: b['slots'] for v, b in meta['bank_layout'].items()}
                for n in (0, 1, 4):
                    for y in (0, 1):
                        data = data_for(q, n, values={'x': -2, 'y': y, 'z': 3})
                        data['initial']['s'] = {str(-k): -k for k in range(1, 65)}
                        expected = run_source(q, data)
                        self.assertEqual(run_target(q, data, bank_slots=slots), expected)
                        self.assertEqual(run_tick(q, data), expected)
            self.assertEqual(p, snapshot)

    def test_call_local_preparation_not_target_verdict_or_mutable_global_cache(self):
        p = owned_skeleton()
        for query in (f.design_space, f.hybrid_design_space):
            checked = []
            def observe(q):
                checked.append(q is p)
                return check(q)
            with patch.object(f, '_candidate_sets', wraps=f._candidate_sets) as prepare, \
                    patch.object(f, 'check', side_effect=observe):
                result = query(p)
            self.assertEqual(prepare.call_count, 1)
            self.assertEqual(checked.count(True), 1)
            self.assertGreaterEqual(checked.count(False), sum(r['admitted'] for r in result['rows']))
        facts = f._prepare_skeleton(p)
        with self.assertRaises(TypeError):
            facts.groups['s'] = ()
        with self.assertRaises(TypeError):
            facts.groups['s'][0] = facts.groups['s'][0]
        # Both public single-period functions still derive facts anew.
        with patch.object(f, '_candidate_sets', wraps=f._candidate_sets) as prepare:
            f.synthesize(p, interval=p['retire'])
            f.hybrid_at(p, p['retire'])
        self.assertEqual(prepare.call_count, 2)
        p['guard_ready']['p'] = True
        for query in (f.design_space, f.hybrid_design_space):
            with self.assertRaisesRegex(f.NoFrontier, 'format'):
                query(p)

    def test_nonmonotone_reservations_cap_and_inactive_uses_remain_checked(self):
        p = build(make_program([instruction('s', 'id', [inp('x')], True, emit=True)],
                              release=0, capacity=1), 'wait')
        first = deepcopy(next(a for a in p['attempts'] if a['kind'] == 'op'))
        first['when'] = True; first['offset'] = 0
        late = deepcopy(first); late['name'] = 'late'; late['offset'] = 3
        p['attempts'] = [first, late]; p['retire'] = 4
        p['retirement'] = {'s': [{'when': True, 'attempt': first['name']}]}
        for query in (f.design_space, f.hybrid_design_space):
            result = query(p, cell_budget=0)
            self.assertEqual([r['admitted'] for r in result['rows']], [False, True, False, True])
            p['retire'] = 257
            result = query(p, cell_budget=0)
            self.assertFalse(result['complete_for_unbounded_intervals'])
            self.assertEqual((result['mathematical_cutoff'], result['enumerated_through']), (257, 256))
            p['retire'] = 4
        p = owned_skeleton()
        inactive = deepcopy(next(a for a in p['attempts'] if a['kind'] == 'op' and a['node'] == 's'))
        inactive['name'] = 'inactive'; inactive['when'] = ['and', 'p', ['not', 'p']]
        p['attempts'].append(inactive)
        space = f.hybrid_design_space(p)
        for row in space['rows']:
            if row['admitted']:
                q, meta = f.hybrid_at(p, row['ii'])
                self.assertTrue(check(q).accepted)
                self.assertEqual((row['cells'], row['export_times']), (meta['cells'], meta['selected']))
                self.assertIn('retired', q['attempts'][-1]['args'][0])


if __name__ == '__main__':
    unittest.main()
