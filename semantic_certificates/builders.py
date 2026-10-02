"""Deterministic, untrusted construction of small candidate schedules.

The scheduler is intentionally simple. Its interval search is exact only for the
fixed offsets and attempt topology it constructs, never over all schedules.
"""
from copy import deepcopy
from .checker import check


class ConstructionFailure(ValueError):
    def __init__(self, candidate, issues):
        self.candidate = deepcopy(candidate)
        self.issues = deepcopy(issues)
        super().__init__('No admitted interval at these fixed offsets within the bounded search')


def neg(x): return ['not',x]
def conj(*x): return ['and',*x]
def disj(*x): return ['or',*x]
def equiv(x,y): return disj(conj(x,y),conj(neg(x),neg(y)))
def inp(x): return {'input':x}
def val(x): return {'constant':x}
def node(x,d=0): return {'node':x,'distance':d}

def instruction(name, op, args, guard=True, fallback=None, emit=False):
    return {'name':name,'op':op,'args':args,'guard':guard,
            'fallback':val(0) if fallback is None else fallback,'emit':emit}


def costs(div_latency=3):
    return {'id':{'latency':1,'resource':'alu','reserve':[0]},
            'add':{'latency':1,'resource':'alu','reserve':[0]},
            'sub':{'latency':1,'resource':'alu','reserve':[0]},
            'mul':{'latency':2,'resource':'alu','reserve':[0]},
            'div':{'latency':div_latency,'resource':'div','reserve':[0]},
            'load':{'latency':2,'resource':'mem','reserve':[0]},
            'store':{'latency':2,'resource':'mem','reserve':[0]},
            'copy':{'latency':1,'resource':'move','reserve':[0]},
            'mux':{'latency':1,'resource':'move','reserve':[0]}}


def make_program(nodes, inputs=('x','y','z'), actual=('p',), predicted=('h',),
                 release=3, capacity=2, div_latency=3):
    if len(actual) != len(predicted): raise ValueError('Predictor map must be bijective')
    return {'actual':list(actual),'predicted':list(predicted),
            'guard_ready':{**{x:release for x in actual},**{x:0 for x in predicted}},
            'inputs':list(inputs),'input_ready':{x:0 for x in inputs},
            'nodes':deepcopy(nodes),'costs':costs(div_latency),
            'resources':{'alu':capacity,'div':capacity,'move':2*capacity,'mem':capacity},
            'ii':1,'retire':1,'attempts':[],'retirement':{}}


def build(p, mode='recover'):
    p = deepcopy(p)
    if mode not in ('recover','wait'): raise ValueError('Unknown construction')
    p['attempts'],p['retirement'] = [],{}
    predict = dict(zip(p['actual'],p['predicted']))
    def guessed(e):
        if isinstance(e,bool): return e
        if isinstance(e,str): return predict[e]
        return [e[0],*(guessed(a) for a in e[1:])]
    match = conj(*(equiv(x,predict[x]) for x in p['actual'])) if p['actual'] else True
    ready = max(p['guard_ready'].values(),default=0)
    done, schedules = {},{}
    def arm(prefix, use_prediction, active, start):
        values = {}
        for v in p['nodes']:
            g = guessed(v['guard']) if use_prediction else v['guard']
            def convert(r):
                if 'node' not in r: return deepcopy(r)
                if r['distance']:
                    return {'retired':r['node'],'distance':r['distance']}
                return {'attempt':values[r['node']]}
            def earliest(refs):
                times = [start]
                for r in refs:
                    if 'attempt' in r: times.append(done[r['attempt']])
                    if 'input' in r: times.append(p['input_ready'][r['input']])
                return max(times)
            names = []
            for kind,refs,guard in [('op',[convert(r) for r in v['args']],g),
                                    ('copy',[convert(v['fallback'])],neg(g))]:
                name = prefix+v['name']+'_'+kind
                offset = earliest(refs)
                a = {'name':name,'node':v['name'],'kind':kind,
                     'when':conj(active,guard),'offset':offset,'args':refs}
                p['attempts'].append(a)
                c = p['costs'][v['op'] if kind=='op' else 'copy']
                done[name] = offset+c['latency']
                names.append(name)
            name = prefix+v['name']+'_join'
            offset = max(done[n] for n in names)
            p['attempts'].append({'name':name,'node':v['name'],'kind':'mux',
                'when':active,'offset':offset,
                'choices':[{'when':g,'attempt':names[0]},
                           {'when':neg(g),'attempt':names[1]}]})
            done[name] = offset+p['costs']['mux']['latency']
            values[v['name']] = name
        return values
    if mode == 'recover':
        fast = arm('f_',True,True,0)
        slow = arm('r_',False,neg(match),ready)
        for v in p['nodes']:
            p['retirement'][v['name']] = [{'when':match,'attempt':fast[v['name']]},
                                         {'when':neg(match),'attempt':slow[v['name']]}]
    else:
        stable = arm('w_',False,True,ready)
        for v in p['nodes']:
            p['retirement'][v['name']] = [{'when':True,'attempt':stable[v['name']]}]
    p['retire'] = max([ready]+list(done.values()))
    # A bounded search over one dimension only. Failure is not an optimality result.
    last = None
    for ii in range(1,min(256,p['retire']+len(p['attempts'])+1)+1):
        p['ii'] = ii
        result = check(p)
        if result.accepted: return p
        last = result
        if any(x['code'] not in ('resource_capacity','dependence_time') for x in result.issues):
            raise ValueError('Construction bug: '+str(result.issues[:3]))
    raise ConstructionFailure(p, last.issues)


def catalogue():
    return {
        'guarded-division':make_program([
            instruction('q','div',[inp('x'),inp('y')],'p',inp('z')),
            instruction('r','add',[node('q'),val(1)],'p',val(0),True)]),
        'fault-prefix':make_program([
            instruction('a','add',[inp('x'),val(1)],True,emit=True),
            instruction('b','div',[inp('x'),inp('y')],'p'),
            instruction('c','div',[inp('z'),inp('y')],True,emit=True)]),
        'memory-token':make_program([
            instruction('m','store',[inp('heap'),inp('k'),inp('x')],'p',inp('heap')),
            instruction('r','load',[node('m'),inp('k')],True,emit=True)],
            inputs=('heap','k','x')),
        'recurrence-one':make_program([
            instruction('a','id',[inp('x')]),
            instruction('s','add',[node('s',1),node('a')],'p',node('s',1),True)]),
        'recurrence-three':make_program([
            instruction('s','add',[node('s',3),inp('x')],'p',node('s',3),True)]),
        'complementary':make_program([
            instruction('a','mul',[inp('x'),inp('y')],'p',inp('z'),True),
            instruction('b','sub',[inp('x'),inp('y')],neg('p'),inp('z'),True)]),
        'two-predicates':make_program([
            instruction('a','div',[inp('x'),inp('y')],conj('p','q'),inp('z')),
            instruction('b','add',[node('a'),val(2)],disj('p','q'),inp('z'),True)],
            actual=('p','q'),predicted=('h','j')),
        'identity-boundary':make_program([
            instruction('a','id',[inp('x')],'p',inp('x'),True)])}


def data_for(p,n,guard_bits=None,values=None):
    keys = p['actual']+p['predicted']
    guards = {k:[False]*n for k in keys}
    if guard_bits is not None:
        for j,k in enumerate(keys): guards[k] = list(guard_bits[j*n:(j+1)*n])
    inputs = {k:[1]*n for k in p['inputs']}
    if 'heap' in inputs: inputs['heap'] = [[0,1] for _ in range(n)]
    if 'k' in inputs: inputs['k'] = [0]*n
    if values:
        for k,v in values.items():
            inputs[k] = list(v) if isinstance(v,list) and len(v)==n else [v]*n
    initial = {v['name']:{str(-k):0 for k in range(1,65)} for v in p['nodes']}
    return {'n':n,'guards':guards,'inputs':inputs,'initial':initial}
