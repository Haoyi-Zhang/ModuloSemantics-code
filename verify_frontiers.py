"""Reconcile generated frontier evidence; this is not an experiment rerun."""
from pathlib import Path
import csv,json,re
ROOT=Path(__file__).resolve().parent
R=ROOT/'results'
def read(task):return json.loads((R/('frontier-'+task+'.json')).read_text())
def rows(filename):
    with (R/filename).open() as f:return list(csv.DictReader(f))
def expect(d,key,value):
    assert d[key]==value,(key,d[key],value)
for task in ['selectors','storage','boundary','designs','startup','hybrid-oracle','hybrid-designs',
             'recurrence-tail','guarded-feedback','cross-feedback','functional-feedback','inherited']:
    expect(read(task),'disagreements',0)
s=read('selectors');expect(s,'two_atom_queries',16384);expect(s,'earliest_time_queries',4096)
expect(s,'three_atom_queries',1024);expect(s,'pointwise_false_admissions',570)
expect(s,'global_ticket_false_rejections',2030)
assert len(rows('frontier_selector_rows.csv'))==16384
b=read('storage');expect(b,'labelled_instances',1820)
assert len(rows('frontier_storage_rows.csv'))==1820
q=read('quality'); qr=rows('frontier_quality_rows.csv');assert len(qr)==q['constructor_pairs']==360
paired=[r for r in qr if r['synthesized_ii'] and r['retirement_only_ii']]
assert len(paired)==q['paired_admitted']
for key,cmp in [('smaller_ii',lambda a,b:a<b),('equal_ii',lambda a,b:a==b),('larger_ii',lambda a,b:a>b)]:
    assert q[key]==sum(cmp(int(r['synthesized_ii']),int(r['retirement_only_ii'])) for r in paired)
copy_better=sum(int(r['synthesized_ii'])<int(r['copied_selector_ii']) for r in paired)
copy_equal=sum(int(r['synthesized_ii'])==int(r['copied_selector_ii']) for r in paired)
copy_worse=len(paired)-copy_better-copy_equal
families={t:read(t) for t in ('recurrence-tail','guarded-feedback','cross-feedback','functional-feedback')}
for t,f in families.items():
    assert sum(r['input_cases'] for r in f['rows'])==f['source_inputs']
    assert len(f['variants'])==6 and not f['construction_failures']
    assert f['target_comparisons']==f['source_inputs']*len(f['variants'])*3
inherited=read('inherited');ir=rows('frontier_inherited_rows.csv')
assert len(ir)==384==inherited['attempted_constructions']
assert len({(r['case'],r['variant']) for r in ir})==384
assert sum(int(r['comparisons']) for r in ir)==inherited['target_comparisons']
assert inherited['admitted_constructions']+inherited['failed_constructions']==384
assert inherited['source_inputs']==2304 and inherited['source_schemas']==96
for key in ('source_inputs','source_fault_inputs','target_comparisons','admitted_constructions','failed_constructions'):
    assert inherited[key]==sum(read('inherited-'+str(j))[key] for j in range(8))
h=read('hybrid-oracle');hr=rows('frontier_hybrid_oracle_rows.csv')
assert len(hr)==h['period_queries']==32
assert sum(int(r['annotation_assignments']) for r in hr)==h['annotation_assignments']
assert sum(int(r['export_time_tuples']) for r in hr)==h['export_time_tuples']
assert all(r['minimum_cells']==r['oracle_cells'] for r in hr)
hd=read('hybrid-designs');hdr=rows('frontier_hybrid_design_rows.csv')
assert len(hdr)==hd['admitted_period_pairs']
assert sum(int(r['hybrid_cells'])<int(r['all_forward_cells']) for r in hdr)==hd['strict_cell_reductions']
assert all(int(r['hybrid_cells'])<=int(r['all_forward_cells']) for r in hdr)
st=read('startup');sr=rows('frontier_startup_rows.csv');assert len(sr)==st['checked_cells']
assert all(int(r['time'])<int(r['retire']) and r['expected']==r['issued_occupancy'] for r in sr)
assert sum(r['capacity_violation']=='True' for r in sr)==st['realized_capacity_violations']
controls=read('controls');assert len(controls['controls'])==controls['controls_with_witnesses']==9
assert all(r['observation_differs'] for r in controls['controls'])
log=(R/'unit-tests.txt').read_text()
n=re.search(r'Ran (\d+) tests',log);assert n and '\nOK' in log
summary={'reconciliation_only':True,'unit_test_methods':int(n[1]),'families':families,
         'family_source_inputs':sum(f['source_inputs'] for f in families.values()),
         'family_target_comparisons':sum(f['target_comparisons'] for f in families.values()),
         'all_new_target_comparisons':sum(f['target_comparisons'] for f in families.values())+
             inherited['target_comparisons']+read('boundary')['target_comparisons']+h['target_comparisons'],
         'selector_queries':s['two_atom_queries']+s['three_atom_queries'],
         'quality_vs_copied_selector':{'smaller':copy_better,'equal':copy_equal,'larger':copy_worse},
         'observed_disagreements':0,
         'finite_checks_are_not_a_general_mechanized_proof':True}
(R/'frontier-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='families'},indent=2))
