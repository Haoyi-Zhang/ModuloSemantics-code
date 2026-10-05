import unittest
from copy import deepcopy
from itertools import product
from semantic_certificates.builders import instruction, make_program, build, inp, node, data_for, val
from semantic_certificates.checker import check
from semantic_certificates.frontiers import (Candidate, selection_at, earliest_selection,
    synthesize, bank_layout, timing_bound, design_space, obstruction_at, verify_obstruction, resource_prefix_witness, hybrid_at, hybrid_design_space, NoFrontier)
from semantic_certificates.frontier_oracle import enumerate_selectors, run_tick, ring_is_safe
from semantic_certificates.logic import TruthTable, support
from semantic_certificates.reference import run_source
from semantic_certificates.target import run_target


def recurrence(distance=1, latency=12):
    return make_program([
        instruction('s', 'add', [node('s', distance), inp('x')], True, emit=True),
        instruction('t', 'div', [inp('z'), inp('y')], True, emit=True)],
        release=0, div_latency=latency, capacity=4)


class FrontierTests(unittest.TestCase):
    def test_resource_admission_is_not_monotone_in_period(self):
        p = build(make_program([instruction('s','id',[inp('x')],True,emit=True)],
                               release=0,capacity=1),'wait')
        first = deepcopy(next(a for a in p['attempts'] if a['kind']=='op'))
        first['when']=True; first['offset']=0
        late=deepcopy(first); late['name']='late-redundant'; late['offset']=3
        p['attempts']=[first,late]; p['retire']=4
        p['retirement']={'s':[{'when':True,'attempt':first['name']}]}
        for ii,wanted in [(2,True),(3,False),(4,True)]:
            with self.subTest(ii=ii):
                p['ii']=ii
                result=check(p)
                self.assertEqual(result.accepted,wanted,result.issues)
                self.assertTrue(all(e['code']=='resource_capacity' for e in result.issues))
                data=data_for(p,4)
                self.assertEqual(run_source(p,data),run_target(p,data))

    def test_information_is_not_pointwise_coverage(self):
        tt = TruthTable(['p'])
        cs = [Candidate('a', 0, tt.bits('p')), Candidate('b', 0, tt.bits(['not', 'p']))]
        self.assertIsNone(selection_at(tt, {'p': 5}, cs, 4))
        self.assertFalse(enumerate_selectors([5], [(0, c.good) for c in cs], 4))
        out = earliest_selection(tt, {'p': 5}, cs, 8)
        self.assertEqual(out['offset'], 5)
        self.assertEqual(len(out['choices']), 2)

    def test_unneeded_late_information_is_not_a_barrier(self):
        tt = TruthTable(['p', 'q'])
        cs = [Candidate('always', 2, tt.all)]
        out = earliest_selection(tt, {'p': 100, 'q': 90}, cs, 120)
        self.assertEqual(out, {'offset': 2, 'choices': [{'when': True, 'attempt': 'always'}]})

    def test_choice_formulas_use_only_released_atoms(self):
        tt = TruthTable(['p', 'q', 'r'])
        cs = [Candidate('a', 0, tt.bits('p')), Candidate('b', 1, tt.bits(['not', 'p']))]
        out = selection_at(tt, {'p': 2, 'q': 9, 'r': 9}, cs, 2)
        for c in out['choices']:
            self.assertLessEqual(support(c['when']), {'p'})
        masks = [tt.bits(c['when']) for c in out['choices']]
        self.assertEqual(masks[0] & masks[1], 0)
        self.assertEqual(masks[0] | masks[1], tt.all)

    def test_forwarding_before_retirement_and_three_executions(self):
        base = build(recurrence(), 'wait')
        early, plan = synthesize(base)
        self.assertEqual((base['ii'], early['ii'], early['exports']['s']['offset']), (13, 1, 1))
        for n in range(4):
            for ys in product((0, 1), repeat=n):
                data = data_for(early, n, values={'y': list(ys), 'x': 1})
                source = run_source(early, data)
                self.assertEqual(source, run_target(early, data))
                self.assertEqual(source, run_tick(early, data))
                slots = {v: e['slots'] for v, e in bank_layout(early).items()}
                self.assertEqual(source, run_target(early, data, bank_slots=slots))

    def test_fault_export_is_private_and_negative_control_detected(self):
        p = make_program([
            instruction('a', 'mul', [inp('z'), inp('y')], True, emit=True),
            instruction('q', 'div', [node('q', 1), inp('x')], True, emit=True)],
            release=0, div_latency=1, capacity=4)
        p['costs']['mul']['latency'] = 12
        q, _ = synthesize(build(p, 'wait'))
        data = data_for(q, 5, values={'x': 0, 'z': 1, 'y': 1})
        metrics = {}
        source = run_source(q, data)
        self.assertEqual(source, run_target(q, data, metrics=metrics))
        self.assertEqual(source, run_tick(q, data))
        self.assertGreater(metrics.get('fault_exports', 0), 0)
        self.assertGreater(metrics.get('forward_reads_before_retirement', 0), 0)
        self.assertNotEqual(source, run_tick(q, data, expose_exports=True))
        self.assertNotEqual(source, run_tick(q, data, retirement_first=True))

    def test_ring_inclusive_endpoint_and_undersized_witness(self):
        self.assertFalse(ring_is_safe(2, 0, 4, 2, 5))
        self.assertTrue(ring_is_safe(2, 0, 4, 3, 5))
        q, _ = synthesize(build(recurrence(3), 'wait'))
        layout = bank_layout(q)
        self.assertEqual(layout['s']['slots'], 3)
        data = data_for(q, 8, values={'x': 1, 'y': 1})
        self.assertEqual(run_source(q, data), run_target(q, data, bank_slots={'s': 3}))
        self.assertEqual(run_target(q, data, bank_slots={'s': 2})['status'], 'stuck')

    def test_late_exports_reduce_forwarding_bank_at_fixed_interval(self):
        p = build(recurrence(3), 'wait')
        early, _ = synthesize(p, interval=2)
        late, _ = synthesize(p, interval=2, policy='latest')
        self.assertLess(early['exports']['s']['offset'], late['exports']['s']['offset'])
        self.assertLess(bank_layout(late)['s']['slots'], bank_layout(early)['s']['slots'])
        d = data_for(late, 10, values={'y': 1})
        self.assertEqual(run_source(late, d), run_target(late, d, bank_slots={'s': bank_layout(late)['s']['slots']}))

    def test_forward_identity_and_availability_are_checked(self):
        q, _ = synthesize(build(recurrence(), 'wait'))
        bad = deepcopy(q)
        bad['exports']['s']['offset'] = 0
        self.assertIn('export_time', {e['code'] for e in check(bad).issues})
        bad = deepcopy(q)
        bad['exports']['s']['offset'] = 2
        self.assertIn('forward_time', {e['code'] for e in check(bad).issues})
        bad = deepcopy(q)
        bad['attempts'][0]['args'][0]['distance'] = 2
        self.assertIn('identity', {e['code'] for e in check(bad).issues})
        self.assertEqual(timing_bound(q), q['ii'])

    def test_invalid_export_objects_return_format(self):
        q, _ = synthesize(build(recurrence(), 'wait'))
        for value in (None, ['s'], 's', True):
            bad = deepcopy(q); bad['exports'] = value
            self.assertEqual(check(bad).issues[0]['code'], 'format')
        for value in (None, ['offset', 'choices'], 'offset', True):
            bad = deepcopy(q); bad['exports']['s'] = value
            self.assertEqual(check(bad).issues[0]['code'], 'format')
        for value in (None, True, -1, 1.0, '1', 4097):
            bad = deepcopy(q); bad['exports']['s']['offset'] = value
            self.assertEqual(check(bad).issues[0]['code'], 'format')

    def test_unknown_forward_and_selector_are_rejected(self):
        q, _ = synthesize(build(recurrence(), 'wait'))
        bad = deepcopy(q); bad['attempts'][0]['args'][0]['forward'] = 'missing'
        self.assertEqual(check(bad).issues[0]['code'], 'format')
        bad = deepcopy(q); bad['exports']['s']['choices'] = []
        self.assertEqual(check(bad).issues[0]['code'], 'format')
        bad = deepcopy(q); bad['exports']['s']['choices'][0]['attempt'] = 'w_s_copy'
        self.assertIn('export_goodness', {e['code'] for e in check(bad).issues})

    def test_no_selector_without_total_good_coverage(self):
        tt = TruthTable(['p'])
        with self.assertRaises(NoFrontier):
            earliest_selection(tt, {'p': 0}, [Candidate('only', 0, tt.bits('p'))], 3)

    def test_bank_fault_tokens_match_unbounded_storage(self):
        p = recurrence(3)
        p['nodes'][0]['op'] = 'div'
        p['costs']['div']['latency'] = 2
        q, _ = synthesize(build(p, 'wait'))
        d = data_for(q, 8, values={'x': 0, 'y': 1})
        slots = {v: e['slots'] for v, e in bank_layout(q).items()}
        self.assertEqual(run_source(q, d), run_target(q, d, bank_slots=slots))

    def test_finite_design_cutoff_and_pareto(self):
        p = build(recurrence(3, 7), 'wait')
        space = design_space(p, cell_budget=1)
        self.assertTrue(space['complete_for_unbounded_intervals'])
        self.assertEqual(space['mathematical_cutoff'], p['retire'])
        feasible = [r for r in space['rows'] if r['admitted']]
        self.assertEqual(space['minimum_budget_feasible_ii'],
                         min(r['ii'] for r in feasible if r['cells'] <= 1))
        q, _ = synthesize(p, policy='latest', interval=p['retire'])
        terminal = sum(x['slots'] for x in bank_layout(q).values())
        for ii in range(p['retire'], 2*p['retire']+2):
            later, _ = synthesize(p, policy='latest', interval=ii)
            self.assertEqual(sum(x['slots'] for x in bank_layout(later).values()), terminal)
        self.assertTrue(all(not any(t['ii'] <= r['ii'] and t['cells'] <= r['cells']
            and (t['ii'] < r['ii'] or t['cells'] < r['cells']) for t in feasible)
            for r in space['pareto']))

    def test_interval_growth_need_not_shrink_banks(self):
        p = build(recurrence(3, 7), 'wait')
        a, _ = synthesize(p, policy='latest', interval=1)
        b, _ = synthesize(p, policy='latest', interval=p['retire'])
        self.assertLess(bank_layout(a)['s']['slots'], bank_layout(b)['s']['slots'])

    def test_selector_obstruction_replay_and_tampering(self):
        tt = TruthTable(['p', 'q'])
        cs = [Candidate('a', 1, tt.bits('p')), Candidate('b', 1, tt.bits(['not','p']))]
        releases = {'p': 4, 'q': 0}
        witness = obstruction_at(tt, releases, cs, 3)
        self.assertTrue(verify_obstruction(tt, releases, cs, witness))
        missing = deepcopy(witness); del missing['excluded']['a']
        self.assertFalse(verify_obstruction(tt, releases, cs, missing))
        wrong = deepcopy(witness); wrong['excluded']['a']['bad_valuation']['p'] = True
        self.assertFalse(verify_obstruction(tt, releases, cs, wrong))
        self.assertIsNone(obstruction_at(tt, releases, cs, 4))

    def test_shannon_expression_avoids_irrelevant_late_bits(self):
        atoms = list('abcdefghij'); tt = TruthTable(atoms)
        cs = [Candidate('yes', 1, tt.bits('a')), Candidate('no', 1, tt.bits(['not','a']))]
        selector = selection_at(tt, {a: 0 for a in atoms}, cs, 1)
        self.assertEqual({str(c['when']) for c in selector['choices']}, {'a', "['not', 'a']"})

    def test_resource_envelope_has_startup_witness(self):
        p = recurrence(3)
        q, _ = synthesize(build(p, 'recover'))
        rows = [r for r in check(q).resources if r['peak'] > 0]
        amap = {a['name']: a for a in q['attempts']}
        nodes = {v['name']: v for v in q['nodes']}
        for row in rows:
            w = resource_prefix_witness(q, row['resource'], row['phase'])
            data = data_for(q, w['n']); data['guards'] = w['guards']
            trace = []; run_target(q, data, issue_trace=trace)
            count = 0
            for event in trace:
                a = amap[event['attempt']]
                op = nodes[a['node']]['op'] if a['kind'] == 'op' else a['kind']
                cost = q['costs'][op]
                if cost['resource'] == w['resource']:
                    count += sum(event['time']+d == w['time'] for d in cost['reserve'])
            self.assertEqual(count, w['expected_occupancy'])
            self.assertLess(w['time'], q['retire'])

    def test_bank_envelope_is_not_a_fault_truncated_lower_bound(self):
        p = make_program([
            instruction('q', 'div', [val(1), val(0)], True, emit=True),
            instruction('s', 'add', [node('s', 64), inp('x')], True, emit=True)],
            release=0, div_latency=1, capacity=4)
        q, _ = synthesize(build(p,'wait'))
        self.assertGreater(bank_layout(q)['s']['slots'], 1)
        data = data_for(q,70,values={'x':1})
        # No nonnegative feedback read is reached before the compulsory first fault.
        self.assertEqual(run_source(q,data), run_target(q,data,bank_slots={'s':1}))

    def test_optional_forwarding_recovers_zero_bank_baseline(self):
        p=build(recurrence(3,7),'wait')
        q,meta=hybrid_at(p,p['ii'])
        self.assertEqual(meta['cells'],0)
        self.assertEqual(q['exports'],{})
        self.assertEqual(hybrid_design_space(p,cell_budget=0)['minimum_budget_feasible_ii'],p['ii'])
        q,meta=hybrid_at(p,1)
        self.assertEqual(meta['cells'],1)
        data=data_for(q,12,values={'x':1,'y':1})
        self.assertEqual(run_source(q,data),run_target(q,data,bank_slots={'s':1}))
        self.assertEqual(run_source(q,data),run_tick(q,data))

    def test_hybrid_retains_late_uses_without_extending_bank(self):
        p=make_program([
            instruction('a','add',[node('a',1),node('a',3)],True,emit=True),
            instruction('t','div',[inp('z'),inp('y')],True,emit=True)],
            release=0,div_latency=7,capacity=8)
        base=build(p,'wait')
        q,meta=hybrid_at(base,3)
        uses=[r for a in q['attempts'] for r in a.get('args',[])]
        self.assertTrue(any('retired' in r and r['distance']==3 for r in uses))
        self.assertTrue(any('forward' in r and r['distance']==1 for r in uses))
        self.assertEqual(meta['cells'],1)
        full,_=synthesize(base,policy='latest',interval=3)
        self.assertGreater(bank_layout(full)['a']['slots'],meta['cells'])
        data=data_for(q,10,values={'y':1})
        self.assertEqual(run_source(q,data),run_target(q,data,bank_slots={'a':1}))
