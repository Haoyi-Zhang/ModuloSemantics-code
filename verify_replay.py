"""Reconcile existing replay-task output; this command is not a rerun."""
from pathlib import Path
import csv
import json
ROOT = Path(__file__).resolve().parent
R = ROOT/'results'

def read(name):
    return json.loads((R/('replay-'+name+'.json')).read_text())

def rows(name):
    with (R/name).open(newline='') as f:
        return list(csv.DictReader(f))

s = read('three-tickets'); a = rows('replay_three_ticket_rows.csv')
assert s['queries'] == len(a) == 32768
assert s['selectors'] == sum(r['has_selector']=='True' for r in a)
assert all(r['has_selector']==r['oracle'] for r in a)
assert s['obstructions_replayed'] == s['damaged_witnesses_rejected'] == s['queries']-s['selectors']
o = read('small-oracle'); b = rows('replay_small_oracle_rows.csv')
assert o['budget_queries'] == len(b) == 28
assert all(r['minimum_period']==r['enumerated_minimum'] and r['accepted']=='True' for r in b)
assert o['period_queries'] == len(rows('replay_annotation_minima.csv')) == 32
assert (o['annotation_assignments'],o['export_time_tuples']) == (512,13346)
t = read('structured'); c = rows('replay_structured_rows.csv')
assert t['budget_queries'] == len(c) == 144
assert t['skeletons'] == 48 and t['original_constructor_failures'] == 6
assert all(r['accepted']=='True' for r in c)
assert t['positive_optima'] == sum(bool(r['minimum_period']) for r in c)
assert t['positive_optima']+t['negative_optima'] == 144
assert t['mutants_rejected'] == 2*144+2*t['positive_optima']
assert all(x['disagreements']==0 for x in (s,o,t))
summary = {'reconciliation_only':True,'three_ticket_queries':s['queries'],
           'obstructions_replayed':s['obstructions_replayed'],
           'damaged_witnesses_rejected':s['damaged_witnesses_rejected'],
           'independent_budget_queries':o['budget_queries'],
           'structured_budget_queries':t['budget_queries'],
           'optimum_queries':o['budget_queries']+t['budget_queries'],
           'structured_positive_optima':t['positive_optima'],
           'structured_negative_optima':t['negative_optima'],
           'proof_mutants_rejected':t['mutants_rejected'],
           'disagreements':0,
           'annotation_grid_reuses_existing_domain_not_new_benchmark_population':True,
           'tests_not_proof_assistant_verification':True}
(R/'replay-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
print(json.dumps(summary,indent=2))
