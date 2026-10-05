"""Exact finite domains for optimum-proof replay; see proofs/optimization-replay.md."""
from collections import Counter
from copy import deepcopy
import csv
from itertools import product
import json
from pathlib import Path
import sys
from .builders import instruction, make_program, build, inp, node, ConstructionFailure
from .frontiers import (Candidate, selection_at, obstruction_at, verify_obstruction,
                        hybrid_design_space, _candidate_sets)
from .frontier_oracle import enumerate_selectors, enumerate_annotations
from .logic import TruthTable
from .optimization_witness import certify_budget
from .optimization_replay import verify_optimum

ROOT = Path(__file__).resolve().parents[1]


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True)+'\n')
    tmp.replace(path)


def csv_rows(name, rows):
    with (ROOT/'results'/name).open('w', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def three_ticket_grid():
    tt = TruthTable(['p','q']); rel = {'p':0, 'q':2}; at = 1
    rows = []; accepted = 0; replayed = 0; damaged_rejected = 0
    for masks in product(range(16), repeat=3):
        for ready in product((0,2), repeat=3):
            cs = [Candidate(str(j), ready[j], masks[j]) for j in range(3)]
            choice = selection_at(tt, rel, cs, at)
            oracle = enumerate_selectors([0,2], list(zip(ready, masks)), at)
            assert (choice is not None) == oracle, (masks, ready, choice, oracle)
            accepted += choice is not None
            if choice is None:
                w = obstruction_at(tt, rel, cs, at)
                assert verify_obstruction(tt, rel, cs, w)
                replayed += 1
                damaged = deepcopy(w); damaged['excluded'].pop('0')
                assert not verify_obstruction(tt, rel, cs, damaged)
                damaged_rejected += 1
                if replayed <= 8:
                    save(ROOT/'cases/replay'/f'obstruction-{replayed:02d}.json',
                         {'releases':rel,'masks':masks,'ready':ready,'at':at,'witness':w})
            rows.append({'m0':masks[0],'m1':masks[1],'m2':masks[2],
                         'r0':ready[0],'r1':ready[1],'r2':ready[2],
                         'has_selector':choice is not None,'oracle':oracle})
    csv_rows('replay_three_ticket_rows.csv',rows)
    return {'queries':len(rows),'selectors':accepted,'obstructions_replayed':replayed,
            'damaged_witnesses_rejected':damaged_rejected,'disagreements':0,
            'raw_rows':'results/replay_three_ticket_rows.csv'}


def small_oracle():
    rows = []; annotation_rows = []; counts = Counter(); kinds = Counter()
    for release, latency in product((0,2),(3,7)):
        s = make_program([
            instruction('a','add',[node('a',1),node('b',2)],True,emit=True),
            instruction('b','add',[node('a',3),inp('x')],'p',node('b',1),True),
            instruction('t','div',[inp('z'),inp('y')],True,emit=True)],
            release=release,div_latency=latency,capacity=32)
        base = build(s,'wait'); tt, groups = _candidate_sets(base)
        uses = [(r['retired'],r['distance'],a['offset']) for a in base['attempts']
                if tt.bits(a['when']) for r in a.get('args',[]) if 'retired' in r]
        candidates = {v:[(c.ready,c.good) for c in groups[v]] for v,_,_ in uses}
        costs = {}
        for ii in range(1,base['retire']+2):
            result = enumerate_annotations([base['guard_ready'][a] for a in tt.atoms],
                                          candidates,uses,ii,base['retire'])
            costs[ii] = result['minimum_cells']
            counts['period_queries'] += 1
            counts['annotation_assignments'] += result['annotation_assignments']
            counts['export_time_tuples'] += result['export_time_tuples']
            annotation_rows.append({'release':release,'latency':latency,'ii':ii,
                                    'minimum_cells':costs[ii]})
        for budget in range(7):
            expected = min((i for i,c in costs.items() if c is not None and c <= budget),default=None)
            proof = certify_budget(base,budget); checked = verify_optimum(base,budget,proof)
            assert checked['accepted'], checked
            assert proof['minimum_period'] == expected, (proof,expected)
            kinds.update(r['kind'] for r in proof['rows'])
            ident = f'small-{release}-{latency}-{budget}'
            save(ROOT/'cases/replay'/f'{ident}.json',{'skeleton':base,'proof':proof,'replay':checked})
            rows.append({'case':ident,'budget':budget,'minimum_period':proof['minimum_period'],
                         'enumerated_minimum':expected,'accepted':checked['accepted']})
    csv_rows('replay_small_oracle_rows.csv',rows)
    csv_rows('replay_annotation_minima.csv',annotation_rows)
    return {'budget_queries':len(rows),'independent_oracle':True,'disagreements':0,
            'exclusion_and_positive_rows':dict(kinds),**counts,
            'raw_rows':'results/replay_small_oracle_rows.csv'}


def structured():
    rows = []; counts = Counter(); kinds = Counter()
    for mode,distance,release,latency,capacity in product(
            ('wait','recover'),(1,2,4),(0,3),(3,9),(1,4)):
        p = make_program([
            instruction('s','add',[node('s',distance),inp('x')], 'p',node('s',distance),True),
            instruction('t','div',[inp('z'),inp('y')],True,emit=True)],
            release=release,div_latency=latency,capacity=capacity)
        counts['skeletons'] += 1
        try:
            base = build(p,mode); originally_admitted = True
        except ConstructionFailure as e:
            base = e.candidate; originally_admitted = False; counts['original_constructor_failures'] += 1
        for budget in (0,1,3):
            proof = certify_budget(base,budget); checked = verify_optimum(base,budget,proof)
            assert checked['accepted'], checked
            expected = hybrid_design_space(base,cell_budget=budget)['minimum_budget_feasible_ii']
            assert proof['minimum_period'] == expected, (mode,distance,budget,proof,expected)
            kinds.update(r['kind'] for r in proof['rows'])
            counts['positive_optima' if expected is not None else 'negative_optima'] += 1
            ident = f'matrix-{mode}-{distance}-{release}-{latency}-{capacity}-{budget}'
            save(ROOT/'cases/replay'/f'{ident}.json',{'skeleton':base,'proof':proof,'replay':checked})
            bad = deepcopy(proof); bad['rows'].pop(0)
            assert not verify_optimum(base,budget,bad)['accepted']; counts['mutants_rejected'] += 1
            bad = deepcopy(proof); bad['budget'] = (budget+1)
            assert not verify_optimum(base,budget,bad)['accepted']; counts['mutants_rejected'] += 1
            if proof['minimum_period'] is not None:
                bad = deepcopy(proof); bad['rows'][-1]['cells'] += 1
                assert not verify_optimum(base,budget,bad)['accepted']; counts['mutants_rejected'] += 1
                bad = deepcopy(proof); bad['rows'][-1]['certificate']['nodes'][0]['emit'] = False
                assert not verify_optimum(base,budget,bad)['accepted']; counts['mutants_rejected'] += 1
            rows.append({'case':ident,'constructor_admitted':originally_admitted,'budget':budget,
                         'minimum_period':expected,'accepted':checked['accepted'],
                         'proof_period_rows':len(proof['rows'])})
    csv_rows('replay_structured_rows.csv',rows)
    return {'budget_queries':len(rows),'disagreements':0,**counts,
            'exclusion_and_positive_rows':dict(kinds),
            'independent_oracle':False,
            'comparison':'Canonical optimizer; independent full enumeration is in replay-small-oracle.',
            'raw_rows':'results/replay_structured_rows.csv'}

TASKS={'three-tickets':three_ticket_grid,'small-oracle':small_oracle,'structured':structured}
if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1] not in TASKS:
        raise SystemExit('Choose '+', '.join(TASKS))
    task=sys.argv[1]; out=TASKS[task]()
    save(ROOT/'results'/('replay-'+task+'.json'),out)
    print(json.dumps(out,indent=2))
