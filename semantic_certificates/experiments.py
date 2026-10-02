"""Bounded, resumable experiment entry points. Each family is a separate run."""
from __future__ import annotations
import argparse,csv,itertools,json,os,random,resource,time
from pathlib import Path
from copy import deepcopy
from .builders import catalogue,build,data_for,instruction,make_program,inp,val,node,neg,conj,ConstructionFailure
from .checker import check
from .logic import TruthTable
from .reference import run_source
from .target import run_target
from .resource_oracle import exhaustive_peak

ROOT = Path(__file__).resolve().parents[1]


def limits():
    available = os.sched_getaffinity(0) if hasattr(os,'sched_getaffinity') else None
    if available: os.sched_setaffinity(0,{min(available)})
    resource.setrlimit(resource.RLIMIT_AS,(int(3.5*1024**3),int(3.5*1024**3)))
    resource.setrlimit(resource.RLIMIT_CPU,(40,44))


def measured(fn):
    start = time.perf_counter(); cpu = time.process_time()
    result = fn()
    result['measurement'] = {'wall_seconds':time.perf_counter()-start,
        'cpu_seconds':time.process_time()-cpu,
        'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1}
    return result


def save(path,obj):
    path = Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
    tmp.replace(path)


def canonical(x):
    # JSON normalizes immutable memory tuples to the public input representation.
    return json.dumps(x,sort_keys=True)


def domains(name):
    if name == 'memory-token':
        return {'heap':[[0,1],[1,0]],'k':[-1,0,1,2],'x':[0,1]},2
    if name in ('recurrence-one','identity-boundary'):
        return {'x':[-1,0,1]},3
    if name == 'recurrence-three': return {'x':[-1,0,1]},4
    if name == 'two-predicates': return {'x':[-1,0,1],'y':[-1,0,1],'z':[-1,0,1]},1
    return {'x':[-1,0,1],'y':[-1,0,1],'z':[-1,0,1]},2


def exhaustive_family(name, max_n=None):
    template = catalogue()[name]
    spec,wait = build(template,'recover'),build(template,'wait')
    save(ROOT/'cases'/f'{name}.json',spec)
    domain,nmax = domains(name)
    if max_n is not None: nmax = max_n
    rows=[]; count=0; compared=0
    for n in range(nmax+1):
        input_slots = [(key,j) for key in domain for j in range(n)]
        expected = 2**(len(spec['actual']+spec['predicted'])*n)
        for key in domain: expected *= len(domain[key])**n
        local=0; faults=0
        for gs in itertools.product((False,True),repeat=len(spec['actual']+spec['predicted'])*n):
            for data_values in itertools.product(*(domain[key] for key,j in input_slots)):
                data = data_for(spec,n,gs)
                for (key,j),x in zip(input_slots,data_values): data['inputs'][key][j] = x
                reference = run_source(spec,data)
                faults += reference['status']=='fault'
                for mode,p in [('recover',spec),('wait',wait)]:
                    actual = run_target(p,data)
                    if canonical(reference) != canonical(actual):
                        save(ROOT/'results'/'failure.json',{'family':name,'mode':mode,
                            'program':p,'input':data,'reference':reference,'target':actual})
                        raise AssertionError(f'Semantic mismatch in {name}, N={n}, {mode}')
                    compared+=1
                local+=1
        if local != expected: raise AssertionError('Enumeration count is inconsistent')
        count+=local
        rows.append({'trip_count':n,'input_cases':local,'source_fault_cases':faults,
                     'target_comparisons':2*local,'mismatches':0})
    return {'family':name,'input_domains':domain,'initial_values':'zero at every negative index',
            'source_nodes':len(spec['nodes']),'boolean_atoms':len(spec['actual']+spec['predicted']),
            'recover_attempts':len(spec['attempts']),'wait_attempts':len(wait['attempts']),
            'recover_ii':spec['ii'],'wait_ii':wait['ii'],
            'recover_retire':spec['retire'],'wait_retire':wait['retire'],
            'cases':count,'target_comparisons':compared,'rows':rows,'mismatches':0}


def pilot():
    result = exhaustive_family('guarded-division',2)
    p = build(catalogue()['guarded-division'])
    oracle_n = 1+max((a['offset']+max(p['costs'][
        next(v['op'] for v in p['nodes'] if v['name']==a['node'])
        if a['kind']=='op' else a['kind']]['reserve'],default=0))//p['ii'] for a in p['attempts'])
    brute = exhaustive_peak(p,oracle_n)
    report = check(p)
    for r in report.resources:
        if r['peak'] != brute['peaks'].get((r['resource'],r['phase']),0):
            raise AssertionError('Pilot resource oracle disagreement')
    bad = deepcopy(p)
    for name,choices in bad['retirement'].items():
        bad['retirement'][name] = [{'when':True,'attempt':choices[0]['attempt']}]
    data = data_for(p,1,(True,False),{'x':2,'y':1,'z':0})
    before,after = run_source(p,data),run_target(bad,data)
    if check(bad).accepted or canonical(before)==canonical(after):
        raise AssertionError('No-recovery negative control did not discriminate')
    save(ROOT/'cases'/'counterexamples'/'omitted-recovery.json',
         {'program':bad,'input':data,'source':before,'target':after,
          'checker_codes':sorted({x['code'] for x in check(bad).issues})})
    result['resource_oracle'] = {'trip_count':oracle_n,'assignments':brute['assignments'],
        'phase_resource_cells':len(report.resources),'disagreements':0}
    result['negative_control'] = {'name':'omitted-recovery','rejected':True,'trace_differs':True}
    return result


def resource_cases():
    predicates = [False,True,'p',neg('p'),'q',neg('q')]
    rows=[]; total_assignments=0; underestimates=0; overconservative=0
    for ii in (1,2,3):
        for s,t in itertools.product(range(4),repeat=2):
            for i,j in itertools.product(range(len(predicates)),repeat=2):
                p = make_program([instruction('a','id',[val(0)])],inputs=(),
                                 actual=('p','q'),predicted=('h','j'),release=0)
                p['predicted']=[]
                p['guard_ready']={'p':0,'q':0}
                # Resource-component input, not necessarily a complete semantic certificate.
                p['ii'],p['retire'] = ii,5
                p['attempts'] = [
                    {'name':'u','node':'a','kind':'op','when':predicates[i],'offset':s,'args':[val(0)]},
                    {'name':'v','node':'a','kind':'op','when':predicates[j],'offset':t,'args':[val(0)]}]
                p['retirement'] = {'a':[{'when':True,'attempt':'u'}]}
                n = max(s,t)//ii+1
                brute = exhaustive_peak(p,n)
                cert = check(p)
                if not cert.resources: raise AssertionError('Resource component was not evaluated')
                tt = TruthTable(p['actual'])
                ab = [tt.bits(e) for e in (predicates[i],predicates[j])]
                for row in cert.resources:
                    phase = row['phase']; exact = row['peak']
                    observed = brute['peaks'].get((row['resource'],phase),0)
                    selected = [k for k,x in enumerate((s,t)) if x%ii == phase]
                    pointwise = max(sum(bool(ab[k]&(1<<z)) for k in selected)
                                    for z in range(len(tt.envs)))
                    unconditional = len(selected)
                    if exact != observed: raise AssertionError('Resource factorization disagrees with unrolling')
                    underestimates += pointwise < exact
                    overconservative += unconditional > exact
                    rows.append({'ii':ii,'offset_u':s,'offset_v':t,'predicate_u':i,'predicate_v':j,
                                 'phase':phase,'exact_peak':exact,'unrolled_peak':observed,
                                 'naive_same_iteration_peak':pointwise,
                                 'unconditional_peak':unconditional,'oracle_trip_count':n})
                total_assignments += brute['assignments']
    path = ROOT/'results'/'resource_rows.csv'
    with path.open('w',newline='') as f:
        w = csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader();w.writerows(rows)
    return {'component_instances':3*16*36,'phase_resource_cells':len(rows),
            'global_guard_assignments':total_assignments,'mismatches':0,
            'naive_underestimated_cells':underestimates,
            'unconditional_overestimated_cells':overconservative,
            'predicate_order':predicates,'raw_rows':'results/resource_rows.csv'}


def mutations():
    p = build(catalogue()['guarded-division'])
    mutations=[]
    def add(label,q): mutations.append((label,q))
    q=deepcopy(p)
    for name,ch in q['retirement'].items(): q['retirement'][name]=[{'when':True,'attempt':ch[0]['attempt']}]
    add('omitted-recovery',q)
    q=deepcopy(p); q['attempts'][0]['args'][0]=inp('z');add('wrong-source-value',q)
    q=deepcopy(p); q['attempts'][0]['when']='p';add('unavailable-guard',q)
    q=deepcopy(p); next(a for a in q['attempts'] if a['name']=='f_r_op')['offset']=0
    add('early-consumer',q)
    q=deepcopy(p); q['retirement']['q']=q['retirement']['q'][:1];add('missing-retirement-arm',q)
    q=deepcopy(p); q['retire']=1;add('early-retirement',q)
    recurrence=build(catalogue()['recurrence-three'])
    q=deepcopy(recurrence)
    for a in q['attempts']:
        for r in a.get('args',[]):
            if 'retired' in r: r['distance']=2
    add('wrong-iteration-distance',q)
    rows=[]
    for label,q in mutations:
        verdict=check(q)
        if verdict.accepted: raise AssertionError('Mutated certificate unexpectedly accepted: '+label)
        witness=None
        max_n=4 if label=='wrong-iteration-distance' else 1
        for n in range(1,max_n+1):
            for gs in itertools.product((False,True),repeat=2*n):
                data=data_for(q,n,gs,{'x':2,'y':1,'z':0})
                src=run_source(q,data);tgt=run_target(q,data)
                if canonical(src)!=canonical(tgt):
                    witness={'program':q,'input':data,'source':src,'target':tgt,
                        'checker_codes':sorted({x['code'] for x in verdict.issues})};break
            if witness:break
        if witness is None: raise AssertionError('No semantic or availability witness for '+label)
        save(ROOT/'cases'/'counterexamples'/f'{label}.json',witness)
        rows.append({'name':label,'rejected':True,'witness_trip_count':n,
                     'target_status':tgt['status'],'codes':witness['checker_codes']})
    # Deliberately violate the runtime contract while keeping the certificate intact.
    d=data_for(p,1,(False,True),{'x':1,'y':0,'z':7})
    src,tgt=run_source(p,d),run_target(p,d,eager_faults=True)
    if canonical(src)==canonical(tgt):raise AssertionError('Eager-fault control failed')
    save(ROOT/'cases'/'counterexamples'/'eager-fault-exposure.json',
         {'program':p,'input':d,'source':src,'target':tgt,'runtime_mutation':'eager_faults'})
    f=build(catalogue()['fault-prefix']);d=data_for(f,1,(True,True),{'x':2,'y':0,'z':3})
    src,tgt=run_source(f,d),run_target(f,d,reverse_retirement=True)
    if canonical(src)==canonical(tgt):raise AssertionError('Order control failed')
    save(ROOT/'cases'/'counterexamples'/'reversed-retirement.json',
         {'program':f,'input':d,'source':src,'target':tgt,'runtime_mutation':'reverse_retirement'})
    # An algebraic identity makes a rejected schedule equivalent: id(x) and fallback x.
    q=build(catalogue()['identity-boundary'])
    q['retirement']['a']=[{'when':True,'attempt':q['retirement']['a'][0]['attempt']}]
    if check(q).accepted:raise AssertionError('Incompleteness witness was not rejected')
    tested=0
    for gs in itertools.product((False,True),repeat=4):
        for xs in itertools.product((-1,0,1),repeat=2):
            d=data_for(q,2,gs,{'x':list(xs)})
            if canonical(run_source(q,d))!=canonical(run_target(q,d)):
                raise AssertionError('Algebraic identity should be equivalent')
            tested+=1
    save(ROOT/'cases'/'counterexamples'/'algebraic-incompleteness.json',
         {'program':q,'finite_cases':tested,'rejected':True,
          'proof':'Both branches compute x; retirement tests the actual source guard for emission.'})
    return {'certificate_mutants':len(rows),'rejected':len(rows),'witnesses':rows,
            'runtime_contract_controls':2,'runtime_controls_discriminated':2,
            'algebraic_incompleteness_cases':tested}


def generated():
    rng=random.Random(72913)
    rows=[];comparisons=0
    for k in range(96):
        m=1+k%6; actual=('p','q') if k%3==0 else ('p',)
        predicted=('h','j') if len(actual)==2 else ('h',)
        nodes=[]
        def reference(j):
            choices=[inp('x'),inp('y'),val(rng.choice((-1,0,1)))]
            if j: choices.append(node('v'+str(rng.randrange(j))))
            if k%4==0: choices.append(node('v'+str(j),1+k%3))
            return deepcopy(rng.choice(choices))
        for j in range(m):
            op=rng.choice(('id','add','sub','mul','div'))
            arity=1 if op=='id' else 2
            g=rng.choice([True,False,'p',neg('p')]+(['q',conj('p','q')] if len(actual)==2 else []))
            nodes.append(instruction('v'+str(j),op,[reference(j) for _ in range(arity)],
                                     g,reference(j),j==m-1))
        base=make_program(nodes,inputs=('x','y'),actual=actual,predicted=predicted,
                          release=(0,3,8)[k%3],capacity=1+k%2,div_latency=(1,3,5)[k%3])
        schedules={}; failures={}
        for mode in ('recover','wait'):
            try:schedules[mode]=build(base,mode)
            except ConstructionFailure as ex:
                failures[mode]={'candidate':ex.candidate,'issues':ex.issues,
                                'search_upper_bound':ex.candidate['ii']}
        local=0;faults=0;inputs=[]
        for trial in range(24):
            n=trial%13
            bits=[bool(rng.randrange(2)) for _ in range(len(actual+predicted)*n)]
            d=data_for(base,n,bits,{x:[rng.randrange(-3,4) for _ in range(n)] for x in base['inputs']})
            for name in d['initial']:
                for index in d['initial'][name]:d['initial'][name][index]=rng.randrange(-3,4)
            inputs.append(d)
            src=run_source(base,d);faults+=src['status']=='fault'
            for schedule in schedules.values():
                if canonical(src)!=canonical(run_target(schedule,d)):
                    save(ROOT/'results'/'failure.json',{'program':schedule,'input':d,
                        'source':src,'target':run_target(schedule,d)})
                    raise AssertionError('Generated semantic mismatch')
                comparisons+=1
            local+=1
        # Explicitly recheck smaller intervals for admitted candidates only.
        rejected_smaller=0
        if 'recover' in schedules:
            recover=schedules['recover']
            for ii in range(1,recover['ii']):
                q=deepcopy(recover);q['ii']=ii
                if check(q).accepted:raise AssertionError('Interval search was not minimal at fixed offsets')
                rejected_smaller+=1
        save(ROOT/'cases'/'generated'/f'case-{k:03d}.json',
             {'source':base,'admitted':schedules,'construction_failures':failures,'inputs':inputs})
        rows.append({'case':k,'nodes':m,'boolean_atoms':len(actual+predicted),
            'recover_admitted':'recover' in schedules,'wait_admitted':'wait' in schedules,
            'recover_attempts':len(schedules['recover']['attempts']) if 'recover' in schedules else '',
            'wait_attempts':len(schedules['wait']['attempts']) if 'wait' in schedules else '',
            'recover_ii':schedules['recover']['ii'] if 'recover' in schedules else '',
            'wait_ii':schedules['wait']['ii'] if 'wait' in schedules else '',
            'recover_retire':schedules['recover']['retire'] if 'recover' in schedules else '',
            'wait_retire':schedules['wait']['retire'] if 'wait' in schedules else '',
            'input_cases':local,'target_comparisons':24*len(schedules),
            'source_fault_cases':faults,'smaller_intervals_rejected':rejected_smaller})
    path=ROOT/'results'/'generated_rows.csv'
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return {'seed':72913,'programs':96,'input_cases':96*24,'target_comparisons':comparisons,
            'mismatches':0,'rows':rows,'raw_rows':'results/generated_rows.csv',
            'recover_admitted':sum(r['recover_admitted'] for r in rows),
            'wait_admitted':sum(r['wait_admitted'] for r in rows),
            'construction_failure_is_not_global_infeasibility':True}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('action',choices=('pilot','family','resources','mutations','generated'))
    ap.add_argument('--name',choices=tuple(catalogue()))
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    limits()
    if args.action=='family':
        if args.name is None:ap.error('--name is required for a family run')
        fn=lambda:exhaustive_family(args.name)
    else:fn={'pilot':pilot,'resources':resource_cases,'mutations':mutations,'generated':generated}[args.action]
    result=measured(fn)
    save(args.output,result)
    print(json.dumps({'action':args.action,'output':args.output,'measurement':result['measurement']}))


if __name__=='__main__':main()
