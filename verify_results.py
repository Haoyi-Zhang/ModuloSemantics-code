"""Reconcile retained scientific results; no timing or fingerprint equality."""
import csv,json
from pathlib import Path
from semantic_certificates.summarize import summarize
from semantic_certificates.checker import check
ROOT=Path(__file__).resolve().parent
s=summarize()
expected={'family_inputs':66304,'family_target_comparisons':132608,
          'generated_programs':96,'generated_inputs':2304,
          'generated_target_comparisons':2592,'generated_recover_admitted':46,
          'generated_wait_admitted':62,'generated_paired_programs':46,
          'generated_recover_ii_better':0,'generated_recover_ii_equal':3,
          'generated_recover_ii_worse':43,'generated_retire_equal':46,
          'accepted_comparisons':135200,'accepted_mismatches':0,
          'resource_instances':1728,'resource_cells':2376,
          'resource_assignments':90720,'resource_naive_underestimates':72,
          'resource_unconditional_overestimates':594}
for key,value in expected.items():
    assert s[key]==value,(key,s[key],value)
o=s['certificate_oracle']
for k,v in {'admitted':4,'false_admissions':0,'false_rejections_within_this_grammar':0,
            'grammar_certificates':216,'inputs_per_certificate':108,
            'target_comparisons':23328,'trip_count':1}.items():assert o[k]==v,(k,o[k])
assert len(list((ROOT/'cases/generated').glob('case-*.json')))==96
rows=list(csv.DictReader((ROOT/'results/generated_rows.csv').open()))
assert len(rows)==96
for path in sorted((ROOT/'cases/generated').glob('case-*.json')):
    d=json.loads(path.read_text());assert len(d['inputs'])==24
    assert set(d['admitted'])|set(d['construction_failures'])=={'recover','wait'}
    assert not set(d['admitted'])&set(d['construction_failures'])
    for p in d['admitted'].values():assert check(p).accepted
    for fail in d['construction_failures'].values():assert not check(fail['candidate']).accepted
m=json.loads((ROOT/'results/mutations.json').read_text())
assert m['certificate_mutants']==m['rejected']==7
assert m['runtime_controls_discriminated']==m['runtime_contract_controls']==2
assert m['algebraic_incompleteness_cases']==144
d=json.loads((ROOT/'results/dominance.json').read_text())
assert d['candidate_pairs']==6144 and d['recover_admitted_pairs']==2695
assert d['implication_counterexamples']==0 and d['equal_retirement_pairs']==96
p=json.loads((ROOT/'results/pilot.json').read_text())
assert p['cases']==11773 and p['target_comparisons']==23546 and p['mismatches']==0
assert p['negative_control']['rejected'] and p['negative_control']['trace_differs']
print(json.dumps({'scientific_counts_reconciled':True,'accepted_comparisons':s['accepted_comparisons'],
                  'finite_checks_are_not_a_general_mechanized_proof':True},indent=2))
