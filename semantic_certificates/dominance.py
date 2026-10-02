"""Post-result falsification test for the proved fixed-construction dominance lemma.

Not a pre-registered performance hypothesis: the lemma explains the observed null
result. Periods 1 through 64 are tested for every stored generated source schema.
"""
from copy import deepcopy
import json
from .builders import build,ConstructionFailure
from .checker import check
from .experiments import limits,measured,save,canonical,ROOT


def candidate(source,mode):
    try:return build(source,mode)
    except ConstructionFailure as ex:return ex.candidate


def experiment():
    tested=0;antecedents=0;counterexamples=0;equal_retire=0
    for path in sorted((ROOT/'cases'/'generated').glob('case-*.json')):
        source=json.loads(path.read_text())['source']
        recover,wait=candidate(source,'recover'),candidate(source,'wait')
        equal_retire+=recover['retire']==wait['retire']
        if recover['retire']!=wait['retire']:raise AssertionError('Retirement offsets differ')
        for ii in range(1,65):
            r=deepcopy(recover);w=deepcopy(wait);r['ii']=w['ii']=ii
            ra,wa=check(r).accepted,check(w).accepted
            tested+=1;antecedents+=ra
            if ra and not wa:
                counterexamples+=1
                save(ROOT/'results'/'dominance_counterexample.json',{'recover':r,'wait':w})
                raise AssertionError('Dominance counterexample')
    return {'programs':equal_retire,'period_range':[1,64],
            'candidate_pairs':tested,'recover_admitted_pairs':antecedents,
            'implication_counterexamples':counterexamples,'equal_retirement_pairs':equal_retire,
            'hypothesis_timing':'exploratory explanation after the generated-matrix result'}

if __name__=='__main__':
    limits();r=measured(experiment);save(ROOT/'results'/'dominance.json',r);print(canonical(r))
