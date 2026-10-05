"""Bounded evidence for causal selection and certified private forwarding.

Each subcommand is a separate reproducible step. Output counts are measured,
not pre-filled. All mismatches are fatal and retain their concrete inputs.
"""
from __future__ import annotations
import argparse
import csv
import itertools as it
import json
import random
import resource
import time
from copy import deepcopy
from pathlib import Path
from .builders import (instruction, make_program, build, inp, node, val, data_for,
                       ConstructionFailure, neg, conj)
from .checker import check
from .logic import TruthTable
from .frontiers import (Candidate, selection_at, earliest_selection, synthesize,
                        NoFrontier, bank_layout, design_space, obstruction_at, verify_obstruction, resource_prefix_witness,
                        hybrid_at, hybrid_design_space, _candidate_sets)
from .frontier_oracle import enumerate_selectors, ring_is_safe, run_tick, enumerate_annotations
from .reference import run_source
from .target import run_target

ROOT = Path(__file__).resolve().parents[1]

def save(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(obj, indent=2, sort_keys=True)+'\n')
    temp.replace(path)

def rows_csv(name, rows):
    path = ROOT/'results'/name
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

def same(a,b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)

def require_equal(a,b,case):
    if not same(a,b):
        save(ROOT/'results/frontier_failure.json', dict(case, reference=a, actual=b))
        raise AssertionError('Observation mismatch; see results/frontier_failure.json')

def selector_grid():
    tt = TruthTable(['p','q'])
    rows=[]; queries=0; earliest_queries=0; false_pointwise=0; conservative_rejects=0
    for m,n in it.product(range(16), repeat=2):
        for a,b in it.product((0,1), repeat=2):
            cs=[Candidate('a',a,m), Candidate('b',b,n)]
            for rp,rq in it.product((0,2), repeat=2):
                releases={'p':rp,'q':rq}; first=None
                for t in range(4):
                    answer=selection_at(tt,releases,cs,t)
                    oracle=enumerate_selectors([rp,rq],[(a,m),(b,n)],t)
                    if (answer is not None) != oracle:
                        save(ROOT/'results/frontier_failure.json',locals_case(m,n,a,b,rp,rq,t))
                        raise AssertionError('Selector oracle disagreement')
                    cover=0
                    for c in cs:
                        if c.ready<=t: cover |= c.good
                    pointwise=cover==tt.all
                    global_ticket=any(c.ready<=t and c.good==tt.all for c in cs)
                    false_pointwise += pointwise and not oracle
                    conservative_rejects += oracle and not global_ticket
                    if oracle and first is None: first=t
                    if answer is not None:
                        masks=[tt.bits(c['when']) for c in answer['choices']]
                        assert sum(masks)==tt.all
                        assert not any(x & y for j,x in enumerate(masks) for y in masks[j+1:])
                        for arm,mask in zip(answer['choices'],masks):
                            parent=next(c for c in cs if c.name==arm['attempt'])
                            assert not mask & ~parent.good and parent.ready<=t
                    rows.append({'mask_a':m,'mask_b':n,'complete_a':a,'complete_b':b,
                                 'release_p':rp,'release_q':rq,'time':t,
                                 'selector_exists':oracle,'pointwise_coverage':pointwise,
                                 'one_global_ticket':global_ticket})
                    queries+=1
                try: critical=earliest_selection(tt,releases,cs,3)['offset']
                except NoFrontier: critical=None
                assert critical==first
                earliest_queries+=1
    # A separately seeded finite three-atom check; whole-table oracle is still feasible.
    rng=random.Random(407183); held=0
    tt3=TruthTable(['p','q','r'])
    for k in range(256):
        rs=[rng.randrange(4) for _ in range(3)]
        cs=[Candidate('a',rng.randrange(4),rng.randrange(256)),
            Candidate('b',rng.randrange(4),rng.randrange(256))]
        for t in range(4):
            answer=selection_at(tt3,dict(zip(tt3.atoms,rs)),cs,t)
            oracle=enumerate_selectors(rs,[(c.ready,c.good) for c in cs],t)
            assert (answer is not None)==oracle
            held+=1
    rows_csv('frontier_selector_rows.csv',rows)
    return {'two_atom_queries':queries,'earliest_time_queries':earliest_queries,
            'three_atom_queries':held,'three_atom_seed':407183,'disagreements':0,
            'pointwise_false_admissions':false_pointwise,
            'global_ticket_false_rejections':conservative_rejects,
            'raw_rows':'results/frontier_selector_rows.csv'}

def locals_case(m,n,a,b,rp,rq,t):
    return {'good_masks':[m,n],'completions':[a,b],'releases':[rp,rq],'time':t}

def storage_grid():
    rows=[]; too_small=0
    for ii in range(1,9):
        for f in range(13):
            for last in range(f,f+3*ii+4):
                predicted=(last-f)//ii+1
                n=predicted+3
                minimum=next(k for k in range(1,predicted+2)
                             if ring_is_safe(ii,f,last,k,n))
                assert minimum==predicted
                if predicted>1:
                    assert not ring_is_safe(ii,f,last,predicted-1,n)
                    too_small+=1
                rows.append({'ii':ii,'export':f,'last_use':last,'predicted_slots':predicted,
                             'enumerated_minimum':minimum,'iterations':n})
    rows_csv('frontier_storage_rows.csv',rows)
    return {'labelled_instances':len(rows),'undersized_counterexamples':too_small,
            'disagreements':0,'raw_rows':'results/frontier_storage_rows.csv'}

def families():
    recurrence=make_program([
        instruction('s','add',[node('s',1),inp('x')],True,emit=True),
        instruction('t','div',[inp('z'),inp('y')],True,emit=True)],
        release=0,div_latency=9,capacity=4)
    guarded=make_program([
        instruction('s','div',[node('s',2),inp('x')],'p',node('s',2),True),
        instruction('t','mul',[inp('z'),inp('y')],True,emit=True)],
        release=3,div_latency=2,capacity=4)
    guarded['costs']['mul']['latency']=11
    cross=make_program([
        instruction('a','add',[node('b',2),inp('x')],'p',node('a',1),True),
        instruction('b','sub',[node('a',1),inp('x')],neg('p'),node('b',3),True),
        instruction('t','div',[inp('z'),inp('y')],True,emit=True)],
        release=2,div_latency=7,capacity=8)
    memory=make_program([
        instruction('m','store',[node('m',1),inp('k'),inp('x')],'p',node('m',1)),
        instruction('r','load',[node('m'),inp('k')],True,emit=True),
        instruction('t','div',[inp('z'),inp('y')],True,emit=True)],
        inputs=('k','x','z','y'),release=2,div_latency=9,capacity=8)
    return {'recurrence-tail':(recurrence,{'x':[-1,0,1],'y':[0,1]},2),
            'guarded-feedback':(guarded,{'x':[-1,0,1]},3),
            'cross-feedback':(cross,{'x':[-1,0,1]},3),
            'functional-feedback':(memory,{'k':[-1,0,1,2],'x':[0,1]},2)}

def minimum_hybrid(base):
    for ii in range(1, min(max(1, base['retire']), 256)+1):
        try:
            q,meta=hybrid_at(base,ii)
            meta['policy']='hybrid'
            return q,meta
        except NoFrontier:
            continue
    raise NoFrontier('No admitted hybrid annotation in the complete represented domain')

def semantic_family(name):
    p,domains,nmax=families()[name]
    certificates=[]; failures=[]; outcomes=[]
    for mode in ('wait','recover'):
        try: base=build(p,mode)
        except ConstructionFailure as e: base=e.candidate
        for policy in ('earliest','latest','hybrid'):
            try:
                q,meta=(minimum_hybrid(base) if policy=='hybrid' else synthesize(base,policy=policy))
            except NoFrontier as ex:
                failures.append({'mode':mode,'policy':policy,'reason':str(ex)})
                continue
            label=mode+'-'+policy
            assert check(q).accepted
            certificates.append((label,q))
            save(ROOT/'cases/frontiers'/name/(label+'.json'),{'program':q,'synthesis':meta})
            outcomes.append({'variant':label,'ii':q['ii'],'retire':q['retire'],
                             'export_times':meta['selected'],
                             'bank_cells':sum(e['slots'] for e in bank_layout(q).values())})
    assert certificates
    first=certificates[0][1]; cases=0; comparisons=0; faults=0; rows=[]
    for n in range(nmax+1):
        count=0
        slots=[(k,j) for k in domains for j in range(n)]
        for gs in it.product((False,True),repeat=2*n):
            for xs in it.product(*(domains[k] for k,j in slots)):
                for init in (-2,1):
                    data=data_for(first,n,gs)
                    for v in data['initial']:
                        data['initial'][v]={str(-d):init+d%2 for d in range(1,65)}
                    if name=='functional-feedback':
                        data['initial']['m']={str(-d):[init,1-init] for d in range(1,65)}
                    for (k,j),x in zip(slots,xs): data['inputs'][k][j]=x
                    source=run_source(first,data); faults+=source['status']=='fault'
                    for variant,q in certificates:
                        layout={v:r['slots'] for v,r in bank_layout(q).items()}
                        for engine,actual in (
                            ('heap',run_target(q,data)),('clock',run_tick(q,data)),
                            ('ring',run_target(q,data,bank_slots=layout))):
                            require_equal(source,actual,{'family':name,'variant':variant,
                                'engine':engine,'program':q,'input':data})
                            comparisons+=1
                    count+=1
        expected=2*4**n
        for k in domains: expected*=len(domains[k])**n
        assert count==expected
        rows.append({'trip_count':n,'input_cases':count})
        cases+=count
    return {'family':name,'input_domains':domains,'max_trip_count':nmax,
            'initial_values':'two patterns: init=-2 or 1, add distance parity; tuple m=[init,1-init]',
            'source_inputs':cases,'source_fault_inputs':faults,'target_comparisons':comparisons,
            'variants':outcomes,'construction_failures':failures,'rows':rows,'disagreements':0}

def copied_selectors(base):
    q=deepcopy(base)
    needed={r['retired'] for a in q['attempts'] for r in a.get('args',[]) if 'retired' in r}
    tt=TruthTable(q['actual']+q['predicted']); amap={a['name']:a for a in q['attempts']}
    nodes={v['name']:v for v in q['nodes']}
    q['exports']={}
    for v in sorted(needed):
        cs=deepcopy(q['retirement'][v]); times=[0]
        from .logic import support
        for c in cs:
            times.extend(q['guard_ready'][x] for x in support(c['when']))
            if tt.bits(c['when']):
                a=amap[c['attempt']]
                op=nodes[v]['op'] if a['kind']=='op' else a['kind']
                times.append(a['offset']+q['costs'][op]['latency'])
        q['exports'][v]={'offset':max(times),'choices':cs}
    for a in q['attempts']:
        for r in a.get('args',[]):
            if 'retired' in r: r['forward']=r.pop('retired')
    for ii in range(1,257):
        q['ii']=ii
        if check(q).accepted: return q
    return None

def quality_grid():
    rows=[]; compared=0; improved=0; worse=0; same_i=0; storage_improved=0
    for d,lat,release,cap in it.product((1,2,3,5),(1,3,7,15,31),(0,3,8),(1,2,4)):
        p=make_program([
            instruction('s','add',[node('s',d),inp('x')],'p',node('s',d),True),
            instruction('t','div',[inp('z'),inp('y')],True,emit=True)],
            release=release,div_latency=lat,capacity=cap)
        for mode in ('wait','recover'):
            admitted=True
            try: base=build(p,mode)
            except ConstructionFailure as ex: base=ex.candidate; admitted=False
            try: early,meta=synthesize(base)
            except NoFrontier: early=None; meta=None
            copied=copied_selectors(base)
            row={'distance':d,'latency':lat,'release':release,'capacity':cap,'skeleton':mode,
                 'retirement_only_ii':base['ii'] if admitted else '',
                 'copied_selector_ii':copied['ii'] if copied else '',
                 'synthesized_ii':early['ii'] if early else '', 'retire':base['retire'],
                 'early_bank_cells':'','latest_bank_cells':'','common_storage_ii':''}
            if admitted and early:
                compared+=1; improved+=early['ii']<base['ii'];worse+=early['ii']>base['ii']
                same_i+=early['ii']==base['ii']
            if early:
                # Same I for both policies; no storage benefit obtained by changing period.
                late,_=synthesize(base,policy='latest',interval=early['ii'])
                es=sum(r['slots'] for r in bank_layout(early).values())
                ls=sum(r['slots'] for r in bank_layout(late).values())
                assert ls<=es
                row.update(early_bank_cells=es,latest_bank_cells=ls,common_storage_ii=early['ii'])
                storage_improved+=ls<es
                # All candidates are archived, not only improved ones.
                key=f'd{d}-l{lat}-r{release}-c{cap}-{mode}'
                save(ROOT/'cases/frontiers/quality'/(key+'.json'),
                     {'baseline':base,'baseline_admitted':admitted,'earliest':early,'latest':late})
            rows.append(row)
    rows_csv('frontier_quality_rows.csv',rows)
    return {'source_schemas':len(rows)//2,'constructor_pairs':len(rows),
            'retirement_only_admitted':sum(r['retirement_only_ii']!='' for r in rows),
            'synthesized_admitted':sum(r['synthesized_ii']!='' for r in rows),
            'copied_admitted':sum(r['copied_selector_ii']!='' for r in rows),
            'paired_admitted':compared,'smaller_ii':improved,'equal_ii':same_i,'larger_ii':worse,
            'smaller_banks_at_same_ii':storage_improved,'raw_rows':'results/frontier_quality_rows.csv'}

def controls():
    p=make_program([
        instruction('a','mul',[inp('z'),inp('y')],True,emit=True),
        instruction('q','div',[node('q',1),inp('x')],True,emit=True)],
        release=0,div_latency=1,capacity=4)
    p['costs']['mul']['latency']=12
    q,_=synthesize(build(p,'wait')); d=data_for(q,5,values={'x':0,'y':1,'z':1})
    src=run_source(q,d); metrics={}
    require_equal(src,run_target(q,d,metrics=metrics),{'program':q,'input':d})
    rows=[]
    for name,actual in [('visible-exported-fault',run_tick(q,d,expose_exports=True)),
                        ('reversed-retirement',run_tick(q,d,retirement_first=True))]:
        assert not same(src,actual)
        save(ROOT/'cases/frontiers/counterexamples'/(name+'.json'),
             {'program':q,'input':d,'source':src,'target':actual})
        rows.append({'name':name,'kind':'runtime contract','observation_differs':True})
    template=families()['recurrence-tail'][0]
    template['nodes'][0]['args'][0]['distance']=3
    good,_=synthesize(build(template,'wait')); d=data_for(good,10,values={'x':1,'y':1})
    bads=[]
    b=deepcopy(good);b['exports']['s']['offset']=0;bads.append(('early-export',b))
    b=deepcopy(good);b['exports']['s']['offset']=4;bads.append(('early-forward-read',b))
    b=deepcopy(good);b['exports']['s']['choices'][0]['attempt']='w_s_copy';bads.append(('wrong-ticket',b))
    b=deepcopy(good);b['exports']['s']['choices'][0]['when']=False;bads.append(('uncovered-export',b))
    b=deepcopy(good);b['exports']['s']['choices']*=2;bads.append(('overlapping-export',b))
    b=deepcopy(good);b['attempts'][0]['args'][0]['distance']=2;bads.append(('wrong-forward-distance',b))
    for name,b in bads:
        v=check(b); assert not v.accepted
        source=run_source(b,d); actual=run_target(b,d)
        assert not same(source,actual),name
        save(ROOT/'cases/frontiers/counterexamples'/(name+'.json'),
            {'program':b,'input':d,'source':source,'target':actual,'checker_issues':v.issues})
        rows.append({'name':name,'kind':'certificate','observation_differs':True,
                     'codes':sorted({x['code'] for x in v.issues})})
    layout={v:r['slots'] for v,r in bank_layout(good).items()}; assert layout['s']>1
    layout['s']-=1
    actual=run_target(good,d,bank_slots=layout)
    assert actual['status']=='stuck'
    save(ROOT/'cases/frontiers/counterexamples/undersized-bank.json',
         {'program':good,'input':d,'bank_slots':layout,'source':run_source(good,d),'target':actual})
    rows.append({'name':'undersized-bank','kind':'storage contract','observation_differs':True})
    return {'controls':rows,'controls_with_witnesses':len(rows),'fault_forwarding_metrics':metrics}

def inherited_matrix(part: int | None = None):
    rows=[]; source_inputs=0; comparisons=0; admitted=0; failures=0; source_faults=0
    paths=sorted((ROOT/'cases/generated').glob('case-*.json'))
    if part is not None:
        paths=paths[part*12:(part+1)*12]
    for path in paths:
        case=json.loads(path.read_text()); source_inputs+=len(case['inputs'])
        references=[run_source(case['source'],d) for d in case['inputs']]
        source_faults+=sum(r['status']=='fault' for r in references)
        for mode in ('wait','recover'):
            try: base=build(case['source'],mode); old=True
            except ConstructionFailure as ex: base=ex.candidate; old=False
            for policy in ('earliest','latest'):
                label=mode+'-'+policy
                try: q,meta=synthesize(base,policy=policy)
                except NoFrontier as ex:
                    failures+=1
                    rows.append({'case':path.stem,'variant':label,'admitted':False,
                                 'retirement_only_admitted':old,'ii':'','cells':'','comparisons':0,
                                 'reason':str(ex)})
                    continue
                admitted+=1; local=0
                bank={v:r['slots'] for v,r in bank_layout(q).items()}
                for data,ref in zip(case['inputs'],references):
                    for engine,result in [('heap',run_target(q,data)),('clock',run_tick(q,data)),
                                          ('ring',run_target(q,data,bank_slots=bank))]:
                        require_equal(ref,result,{'program':q,'input':data,'case':path.stem,
                                                 'variant':label,'engine':engine})
                        local+=1
                comparisons+=local
                save(ROOT/'cases/frontiers/inherited'/(path.stem+'-'+label+'.json'),
                     {'program':q,'synthesis':meta,'source_case':'cases/generated/'+path.name})
                rows.append({'case':path.stem,'variant':label,'admitted':True,
                             'retirement_only_admitted':old,'ii':q['ii'],'cells':sum(bank.values()),
                             'comparisons':local,'reason':''})
    assert len(rows)==len(paths)*4 and source_inputs==len(paths)*24
    raw='frontier_inherited_rows.csv' if part is None else f'frontier_inherited_{part}_rows.csv'
    rows_csv(raw,rows)
    return {'source_schemas':len(paths),'source_inputs':source_inputs,'source_fault_inputs':source_faults,
            'attempted_constructions':len(rows),'admitted_constructions':admitted,
            'failed_constructions':failures,'target_comparisons':comparisons,'disagreements':0,
            'not_a_holdout':'All 96 sources were part of the inherited development corpus.',
            'raw_rows':'results/'+raw}

def inherited_summary():
    parts=[json.loads((ROOT/'results'/f'frontier-inherited-{j}.json').read_text()) for j in range(8)]
    keys=('source_schemas','source_inputs','source_fault_inputs','attempted_constructions',
          'admitted_constructions','failed_constructions','target_comparisons','disagreements')
    result={k:sum(p[k] for p in parts) for k in keys}
    assert result['source_schemas']==96 and result['source_inputs']==2304
    assert result['attempted_constructions']==384 and result['disagreements']==0
    rows=[]
    for j,p in enumerate(parts):
        with (ROOT/p['raw_rows']).open() as f:rows.extend(list(csv.DictReader(f)))
    assert len(rows)==384 and len({(r['case'],r['variant']) for r in rows})==384
    rows_csv('frontier_inherited_rows.csv',rows)
    result.update(raw_rows='results/frontier_inherited_rows.csv',
                  not_a_holdout='All 96 sources were part of the inherited development corpus.',
                  bounded_parts=8)
    return result

def boundary_matrix():
    rng=random.Random(601027); rows=[]; inputs=0; comparisons=0; metric_totals={}
    for distance in (1,3,17,64):
        p=make_program([
            instruction('s','add',[node('s',distance),inp('x')],conj('p','q'),node('s',distance),True),
            instruction('u','sub',[node('s'),inp('x')],neg('p'),inp('z'),True),
            instruction('tail','div',[inp('z'),inp('y')],True,emit=True)],
            actual=('p','q'),predicted=('h','j'),release=7,capacity=16,div_latency=13)
        p['guard_ready']['p']=1
        p['costs']['div']['reserve']=[0,2,7]  # non-contiguous reservation positions
        # Input readiness is intentionally distinct from guard readiness.
        p['input_ready']['x']=2
        for mode in ('wait','recover'):
            base=build(p,mode)
            q,meta=synthesize(base,policy='latest')
            bank={v:r['slots'] for v,r in bank_layout(q).items()}
            save(ROOT/'cases/frontiers/boundary'/f'd{distance}-{mode}.json',
                 {'program':q,'synthesis':meta})
            local=0
            for n in (0,1,7,17,65,66):
                for pattern in ('constant','alternating','random'):
                    for fault in (False,True):
                        gs=[]
                        for k in range(4):
                            gs.extend([True if pattern=='constant' else ((i+k)%2==0 if pattern=='alternating'
                                       else bool(rng.randrange(2))) for i in range(n)])
                        data=data_for(q,n,gs,{'x':[rng.randrange(-3,4) for _ in range(n)],
                            'y':[1]*n,'z':[2]*n})
                        data['initial']['s']={str(-d):3*d-71 for d in range(1,65)}
                        if fault and n: data['inputs']['y'][n//2]=0
                        reference=run_source(q,data); metrics={}
                        for engine,actual in [('heap',run_target(q,data,metrics=metrics)),
                                              ('clock',run_tick(q,data)),
                                              ('ring',run_target(q,data,bank_slots=bank))]:
                            require_equal(reference,actual,{'distance':distance,'mode':mode,
                                'pattern':pattern,'program':q,'input':data,'engine':engine})
                            comparisons+=1
                        for key,value in metrics.items():metric_totals[key]=metric_totals.get(key,0)+value
                        save(ROOT/'cases/frontiers/boundary'/f'd{distance}-{mode}-{local:02d}-input.json',data)
                        inputs+=1;local+=1
            rows.append({'distance':distance,'mode':mode,'input_cases':local,
                         'ii':q['ii'],'retire':q['retire'],'cells':sum(bank.values())})
    return {'source_schemas':4,'constructed_certificates':len(rows),'source_inputs':inputs,
            'target_comparisons':comparisons,'seed':601027,'disagreements':0,'rows':rows,
            'metrics':metric_totals,
            'coverage':'skew actual releases; four atoms; non-contiguous reservations; distance 64; 66 iterations'}

def designs():
    rows=[]; detailed=[]; stability=0; replayed=0; storage_checks=0
    for distance,lat,capacity in it.product((1,3,5),(7,15),(1,4)):
        p=make_program([
            instruction('s','add',[node('s',distance),inp('x')],True,emit=True),
            instruction('t','div',[inp('z'),inp('y')],True,emit=True)],
            release=0,div_latency=lat,capacity=capacity)
        base=build(p,'wait')
        space=design_space(base,cell_budget=1)
        assert space['complete_for_unbounded_intervals']
        c=space['mathematical_cutoff']; terminal=None
        for ii in range(1,2*c+2):
            try:q,meta=synthesize(base,policy='latest',interval=ii)
            except NoFrontier:
                assert ii<c
                continue
            bank=bank_layout(q); cells=sum(r['slots'] for r in bank.values())
            for v,w in meta['minimality'].items():
                # The synthesizer internally replayed each explicit obstruction.
                replayed+=int('time' in w)
            for r in bank.values():
                assert ring_is_safe(ii,r['export'],r['last_use'],r['slots'],r['slots']+4)
                if r['slots']>1:
                    assert not ring_is_safe(ii,r['export'],r['last_use'],r['slots']-1,r['slots']+4)
                storage_checks+=1
            if ii==c: terminal=cells
            if ii>=c: assert cells==terminal;stability+=1
            rows.append({'distance':distance,'latency':lat,'capacity':capacity,'ii':ii,
                         'cells':cells,'cutoff':c,'export':meta['selected']['s']})
        detailed.append({'distance':distance,'latency':lat,'capacity':capacity,'design_space':space})
    rows_csv('frontier_design_rows.csv',rows)
    return {'skeletons':len(detailed),'admitted_periods_checked':len(rows),
            'checks_at_or_beyond_cutoff':stability,'obstructions_replayed':replayed,
            'tagged_bank_checks':storage_checks,'disagreements':0,
            'design_spaces':detailed,'raw_rows':'results/frontier_design_rows.csv'}

def scaling():
    import statistics
    rows=[]; samples=[]; batches=7; calls_per_batch=64
    for b in (0,2,4,6,8,10):
        atoms=[f'p{i}' for i in range(b)]
        for requested in (2,8,32):
            start=time.process_time(); tt=TruthTable(atoms)
            width=min(b,(requested-1).bit_length())
            masks=[0]*(1<<width)
            for j,env in enumerate(tt.envs):
                key=sum(int(env[a])<<(width-i-1) for i,a in enumerate(tt.atoms[:width]))
                masks[key]|=1<<j
            cs=[Candidate(f'c{i}',1,masks[i%len(masks)]) for i in range(requested)]
            releases={a:(2 if i==0 else 0) for i,a in enumerate(atoms)}
            prep=time.process_time()-start; cpu=[]; wall=[]
            # Batch short operations; retain both clocks and all batch samples.
            for batch in range(batches):
                t=time.process_time(); w=time.perf_counter()
                for _ in range(calls_per_batch):
                    selector=earliest_selection(tt,releases,cs,3)
                    assert selector['offset']==(2 if b else 1)
                dc=time.process_time()-t; dw=time.perf_counter()-w
                cpu.append(dc/calls_per_batch); wall.append(dw/calls_per_batch)
                samples.append({'boolean_atoms':b,'candidates':requested,'batch':batch,
                                'calls':calls_per_batch,'cpu_seconds':dc,'wall_seconds':dw})
            expression_chars=sum(len(json.dumps(c['when'])) for c in selector['choices'])
            rows.append({'boolean_atoms':b,'candidates':requested,'truth_valuations':len(tt.envs),
                         'preparation_cpu_seconds':prep,'batches':batches,'calls_per_batch':calls_per_batch,
                         'median_selector_cpu_seconds':statistics.median(cpu),
                         'maximum_selector_cpu_seconds':max(cpu),
                         'median_selector_wall_seconds':statistics.median(wall),
                         'serialized_predicate_characters':expression_chars})
    rows_csv('frontier_scaling_rows.csv',rows)
    rows_csv('frontier_scaling_samples.csv',samples)
    return {'configurations':len(rows),'batches_per_configuration':batches,
            'calls_per_batch':calls_per_batch,'rows':rows,
            'timing_scope':'Candidate masks prepared separately; medians of batch means. CPU zero is below resolution, not zero cost.',
            'raw_rows':'results/frontier_scaling_rows.csv','raw_samples':'results/frontier_scaling_samples.csv'}

def startup_witnesses():
    checked=0; violating=0; rows=[]
    paths=sorted((ROOT/'cases/generated').glob('case-*.json'))
    for path in paths:
        case=json.loads(path.read_text())
        for mode,base in case['admitted'].items():
            # Include both the inherited operand rule and the new interface.
            candidates=[('retired',base)]
            q,_=synthesize(base,policy='latest'); candidates.append(('export',q))
            for kind,p in candidates:
                amap={a['name']:a for a in p['attempts']}
                nodes={v['name']:v for v in p['nodes']}
                for cell in check(p).resources:
                    if not cell['peak']: continue
                    test=deepcopy(p)
                    if cell['peak']>1:
                        test['resources'][cell['resource']]=cell['peak']-1
                    w=resource_prefix_witness(test,cell['resource'],cell['phase'])
                    data=data_for(test,w['n']);data['guards']=w['guards']
                    issues=[]; observation=run_target(test,data,issue_trace=issues)
                    assert observation['status']!='stuck'
                    measured=0
                    for e in issues:
                        a=amap[e['attempt']]
                        op=nodes[a['node']]['op'] if a['kind']=='op' else a['kind']
                        c=p['costs'][op]
                        if c['resource']==w['resource']:
                            measured+=sum(e['time']+d==w['time'] for d in c['reserve'])
                    assert measured==w['expected_occupancy'] and w['time']<test['retire']
                    is_violation=measured>w['capacity'];violating+=is_violation;checked+=1
                    rows.append({'case':path.stem,'skeleton':mode,'operand_interface':kind,
                        'resource':w['resource'],'phase':w['phase'],'time':w['time'],
                        'retire':test['retire'],'trip_count':w['n'],
                        'expected':w['expected_occupancy'],'issued_occupancy':measured,
                        'capacity':w['capacity'],'capacity_violation':is_violation})
                    if is_violation and violating<=12:
                        save(ROOT/'cases/frontiers/resource-witnesses'/f'witness-{violating:02d}.json',
                            {'program':test,'input':data,'witness':w,'issue_trace':issues})
    rows_csv('frontier_startup_rows.csv',rows)
    return {'checked_cells':checked,'realized_capacity_violations':violating,'disagreements':0,
            'scope':'Every non-resource certificate condition holds; peak is realized before first retirement.',
            'raw_rows':'results/frontier_startup_rows.csv'}

def hybrid_oracle():
    rows=[]; assignments=0; time_tuples=0; comparisons=0
    for release,lat in it.product((0,2),(3,7)):
        p=make_program([
            instruction('a','add',[node('a',1),node('b',2)],True,emit=True),
            instruction('b','add',[node('a',3),inp('x')],'p',node('b',1),True),
            instruction('t','div',[inp('z'),inp('y')],True,emit=True)],
            release=release,div_latency=lat,capacity=32)
        base=build(p,'wait');tt,groups=_candidate_sets(base)
        uses=[(r['retired'],r['distance'],a['offset']) for a in base['attempts']
              if tt.bits(a['when']) for r in a.get('args',[]) if 'retired' in r]
        cs={v:[(c.ready,c.good) for c in groups[v]] for v,_,_ in uses}
        rs=[base['guard_ready'][a] for a in tt.atoms]
        for ii in range(1,base['retire']+2):
            oracle=enumerate_annotations(rs,cs,uses,ii,base['retire'])
            assignments+=oracle['annotation_assignments'];time_tuples+=oracle['export_time_tuples']
            try:q,meta=hybrid_at(base,ii);actual=meta['cells']
            except NoFrontier:q=None;actual=None
            assert actual==oracle['minimum_cells'], (release,lat,ii,actual,oracle)
            if q is not None:
                bank={v:r['slots'] for v,r in meta['bank_layout'].items()}
                for n in (0,1,4,8):
                    for pattern in (False,True):
                        data=data_for(q,n,[bool(i%2)==pattern for i in range(n)]+
                                        [bool((i+1)%2)==pattern for i in range(n)])
                        ref=run_source(q,data)
                        for engine,result in [('heap',run_target(q,data)),('clock',run_tick(q,data)),
                                              ('bank',run_target(q,data,bank_slots=bank))]:
                            require_equal(ref,result,{'program':q,'input':data,'engine':engine})
                            comparisons+=1
            rows.append({'release':release,'tail_latency':lat,'ii':ii,'retire':base['retire'],
                         'minimum_cells':actual,'oracle_cells':oracle['minimum_cells'],
                         'annotation_assignments':oracle['annotation_assignments'],
                         'export_time_tuples':oracle['export_time_tuples']})
    rows_csv('frontier_hybrid_oracle_rows.csv',rows)
    return {'skeletons':4,'period_queries':len(rows),'annotation_assignments':assignments,
            'export_time_tuples':time_tuples,'target_comparisons':comparisons,'disagreements':0,
            'raw_rows':'results/frontier_hybrid_oracle_rows.csv'}


def hybrid_designs():
    rows=[];spaces=[]; strict=0;zero=0
    for distance,lat,capacity in it.product((1,3,5),(7,15),(1,4)):
        p=make_program([
            instruction('s','add',[node('s',distance),inp('x')],True,emit=True),
            instruction('t','div',[inp('z'),inp('y')],True,emit=True)],
            release=0,div_latency=lat,capacity=capacity)
        base=build(p,'wait');space=hybrid_design_space(base,cell_budget=0)
        assert space['minimum_budget_feasible_ii']==base['ii']
        assert space['complete_for_unbounded_intervals']
        for r in space['rows']:
            if not r['admitted']:continue
            q,meta=hybrid_at(base,r['ii'])
            allq,allmeta=synthesize(base,policy='latest',interval=r['ii'])
            full=sum(v['slots'] for v in allmeta['bank_layout'].values())
            assert meta['cells']<=full
            strict+=meta['cells']<full;zero+=meta['cells']==0
            rows.append({'distance':distance,'tail_latency':lat,'capacity':capacity,
                         'ii':r['ii'],'hybrid_cells':meta['cells'],'all_forward_cells':full})
        # Cutoff stability is checked at a strictly larger period as well.
        q,meta=hybrid_at(base,2*base['retire']+1);assert meta['cells']==0
        spaces.append({'distance':distance,'tail_latency':lat,'capacity':capacity,'space':space})
    rows_csv('frontier_hybrid_design_rows.csv',rows)
    return {'skeletons':len(spaces),'admitted_period_pairs':len(rows),
            'strict_cell_reductions':strict,'zero_cell_configurations':zero,'disagreements':0,
            'design_spaces':spaces,'raw_rows':'results/frontier_hybrid_design_rows.csv'}

COMMANDS={'selectors':selector_grid,'storage':storage_grid,'quality':quality_grid,
          'controls':controls, 'inherited':inherited_summary, 'boundary':boundary_matrix,
          'designs':designs, 'scaling':scaling, 'startup':startup_witnesses,
          'hybrid-oracle':hybrid_oracle, 'hybrid-designs':hybrid_designs}

for _j in range(8):
    COMMANDS[f'inherited-{_j}']=(lambda j=_j: inherited_matrix(j))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('task',choices=[*COMMANDS,*families()])
    args=ap.parse_args()
    cpu=time.process_time(); start=time.perf_counter()
    fn=COMMANDS.get(args.task)
    result=fn() if fn else semantic_family(args.task)
    result['measurement']={'cpu_seconds':time.process_time()-cpu,
        'wall_seconds':time.perf_counter()-start,
        'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1}
    save(ROOT/'results'/('frontier-'+args.task+'.json'),result)
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
