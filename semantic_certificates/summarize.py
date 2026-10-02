"""Reconcile stored results and emit a stable scientific summary (no timing claims)."""
import csv,json
from pathlib import Path
from .experiments import ROOT,save


def summarize():
    families=[]
    for path in sorted((ROOT/'results').glob('family-*.json')):
        d=json.loads(path.read_text())
        assert d['cases']==sum(x['input_cases'] for x in d['rows'])
        assert d['target_comparisons']==2*d['cases'] and d['mismatches']==0
        families.append({k:d[k] for k in ('family','cases','target_comparisons','recover_ii','wait_ii','recover_retire','wait_retire','recover_attempts','wait_attempts')})
    assert len(families)==8
    generated=json.loads((ROOT/'results/generated.json').read_text())
    assert generated['mismatches']==0
    common=[x for x in generated['rows'] if x['recover_admitted'] and x['wait_admitted']]
    assert generated['target_comparisons']==sum(x['target_comparisons'] for x in generated['rows'])
    resources=json.loads((ROOT/'results/resources.json').read_text())
    rr=list(csv.DictReader((ROOT/'results/resource_rows.csv').open()))
    assert len(rr)==resources['phase_resource_cells']
    assert all(x['exact_peak']==x['unrolled_peak'] for x in rr)
    oracle=json.loads((ROOT/'results/certificate_oracle.json').read_text())
    assert oracle['false_admissions']==0
    r={'family_inputs':sum(x['cases'] for x in families),
       'family_target_comparisons':sum(x['target_comparisons'] for x in families),
       'generated_programs':generated['programs'],'generated_inputs':generated['input_cases'],
       'generated_target_comparisons':generated['target_comparisons'],
       'generated_recover_admitted':generated['recover_admitted'],
       'generated_wait_admitted':generated['wait_admitted'],
       'generated_paired_programs':len(common),
       'generated_recover_ii_better':sum(x['recover_ii']<x['wait_ii'] for x in common),
       'generated_recover_ii_equal':sum(x['recover_ii']==x['wait_ii'] for x in common),
       'generated_recover_ii_worse':sum(x['recover_ii']>x['wait_ii'] for x in common),
       'generated_retire_equal':sum(x['recover_retire']==x['wait_retire'] for x in common),
       'accepted_comparisons':sum(x['target_comparisons'] for x in families)+generated['target_comparisons'],
       'accepted_mismatches':generated['mismatches'],'families':families,
       'resource_instances':resources['component_instances'],'resource_cells':resources['phase_resource_cells'],
       'resource_assignments':resources['global_guard_assignments'],
       'resource_naive_underestimates':resources['naive_underestimated_cells'],
       'resource_unconditional_overestimates':resources['unconditional_overestimated_cells'],
       'certificate_oracle':{k:v for k,v in oracle.items() if k!='measurement'}}
    save(ROOT/'results/summary.json',r)
    return r

if __name__=='__main__':print(json.dumps(summarize(),indent=2))
