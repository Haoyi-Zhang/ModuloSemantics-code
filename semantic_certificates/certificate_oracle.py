"""Exact finite semantic classification over a stated 216-certificate grammar.

One source definition: a = p ? trunc(x/y) : z. The two candidate
attempts perform division and copy; each activation, and the division's
retirement selector, is chosen independently from six Boolean expressions.
The complementary retirement selector chooses copy. All predicates are ready
at time zero. This grammar is not the full certificate language.
"""
import csv,itertools
from pathlib import Path
from copy import deepcopy
from .builders import make_program,instruction,inp,neg,data_for
from .checker import check
from .reference import run_source
from .target import run_target
from .experiments import limits,measured,save,canonical,ROOT


def experiment():
    predicates=[False,True,'p',neg('p'),'h',neg('h')]
    base=make_program([instruction('a','div',[inp('x'),inp('y')],'p',inp('z'),True)],release=0)
    rows=[];comparisons=0;accepted=0;false_admissions=0;false_rejections=0
    for ident,(i,j,k) in enumerate(itertools.product(range(6),repeat=3)):
        p=deepcopy(base);p['retire']=3;p['ii']=1
        p['attempts']=[{'name':'op','node':'a','kind':'op','when':predicates[i],
                        'offset':0,'args':[inp('x'),inp('y')]},
                       {'name':'copy','node':'a','kind':'copy','when':predicates[j],
                        'offset':0,'args':[inp('z')]}]
        p['retirement']={'a':[{'when':predicates[k],'attempt':'op'},
                              {'when':neg(predicates[k]),'attempt':'copy'}]}
        admission=check(p).accepted;accepted+=admission;witness=None;different=0
        for gs in itertools.product((False,True),repeat=2):
            for x,y,z in itertools.product((-1,0,1),repeat=3):
                d=data_for(p,1,gs,{'x':x,'y':y,'z':z})
                src,tgt=run_source(p,d),run_target(p,d);comparisons+=1
                if canonical(src)!=canonical(tgt):
                    different+=1
                    if witness is None:witness={'input':d,'source':src,'target':tgt}
        finite_equivalent=different==0
        false_admissions+=admission and not finite_equivalent
        false_rejections+=not admission and finite_equivalent
        rows.append({'case':ident,'op_activation':i,'copy_activation':j,
                     'op_selector':k,'admitted':admission,'oracle_equivalent':finite_equivalent,
                     'compared_inputs':108,'unequal_inputs':different})
        save(ROOT/'cases'/'certificate-oracle'/f'case-{ident:03d}.json',
             {'program':p,'checker_admitted':admission,'finite_equivalent':finite_equivalent,
              'first_counterexample':witness})
    with (ROOT/'results'/'certificate_oracle_rows.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    if false_admissions:raise AssertionError('An admitted certificate disagrees with the exact finite oracle')
    return {'grammar_certificates':216,'admitted':accepted,'trip_count':1,
            'inputs_per_certificate':108,'target_comparisons':comparisons,
            'false_admissions':false_admissions,'false_rejections_within_this_grammar':false_rejections,
            'predicate_order':predicates,'raw_rows':'results/certificate_oracle_rows.csv'}

if __name__=='__main__':
    limits();r=measured(experiment);save(ROOT/'results'/'certificate_oracle.json',r);print(canonical(r))
