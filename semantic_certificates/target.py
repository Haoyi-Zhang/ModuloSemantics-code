"""Event-driven target interpreter; separate arithmetic and Boolean evaluators.

Tentative instructions only create local values/fault tokens. All observations
occur in a source-ordered retirement batch. Predicates are read at scheduled time.
The checker is never called by this interpreter, including for invalid mutants.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import heapq


@dataclass(frozen=True)
class Token:
    error: str


def pred(e: Any, state: dict) -> bool:
    if isinstance(e,bool): return e
    if isinstance(e,str): return bool(state[e])
    operator, *rest = e
    if operator == 'not': return not pred(rest[0],state)
    if operator == 'and': return all(map(lambda x:pred(x,state),rest))
    if operator == 'or': return any(map(lambda x:pred(x,state),rest))
    raise ValueError('Unknown target predicate')


def primitive(code: str, xs: list[Any]) -> Any:
    bad = next((x for x in xs if isinstance(x,Token)),None)
    if bad is not None: return bad
    arities = {'id':1,'add':2,'sub':2,'mul':2,'div':2,'load':2,'store':3}
    if len(xs) != arities.get(code,-1): return Token('type')
    if code == 'id': return xs[0]
    if code in ('load','store'):
        if not isinstance(xs[0],tuple) or type(xs[1]) is not int: return Token('type')
        if xs[1] < 0 or xs[1] >= len(xs[0]): return Token('bounds')
        if code == 'load': return xs[0][xs[1]]
        tmp = list(xs[0]); tmp[xs[1]] = xs[2]; return tuple(tmp)
    if any(type(x) is not int for x in xs): return Token('type')
    if code == 'add': return sum(xs)
    if code == 'sub': return xs[0]-xs[1]
    if code == 'mul': return xs[0]*xs[1]
    if xs[1] == 0: return Token('division-by-zero')
    magnitude = abs(xs[0])//abs(xs[1])
    return magnitude if xs[0]*xs[1] >= 0 else -magnitude


def run_target(p: dict, data: dict, *, eager_faults: bool = False,
               reverse_retirement: bool = False,
               bank_slots: dict[str, int] | None = None,
               metrics: dict | None = None,
               issue_trace: list[dict] | None = None) -> dict:
    n = data['n']
    if n == 0: return {'trace':[],'state':{},'status':'done'}
    src = {x['name']:x for x in p['nodes']}
    buf, pending, committed, state, trace = {}, {}, {}, {}, []
    exported = {}
    banks = None
    if bank_slots is not None:
        if (set(bank_slots) != set(p.get('exports', {}))
                or any(type(k) is not int or k < 1 for k in bank_slots.values())):
            return {'trace': [], 'state': {}, 'status': 'stuck',
                    'detail': 'Invalid forwarding bank dimensions'}
        banks = {v: [None] * size for v, size in bank_slots.items()}
    def count(label):
        if metrics is not None:
            metrics[label] = metrics.get(label, 0) + 1
    events = []
    attempts = {a['name']:a for a in p['attempts']}
    def add(t, phase, i, rank, kind, item):
        heapq.heappush(events,(t,phase,i,rank,kind,item))
    for i in range(n):
        for rank,a in enumerate(p['attempts']):
            add(i*p['ii']+a['offset'],3,i,rank,'issue',a['name'])
        for rank, (v, entry) in enumerate(p.get('exports', {}).items()):
            add(i*p['ii']+entry['offset'],1,i,rank,'export',v)
        add(i*p['ii']+p['retire'],2,i,0,'retire','')
    def ref(r,i):
        if 'constant' in r: return r['constant']
        if 'input' in r:
            if p['input_ready'][r['input']] > current_time - i*p['ii']:
                raise ValueError('Input read before release')
            x = data['inputs'][r['input']][i]
            return tuple(x) if isinstance(x,list) else x
        if 'attempt' in r: return buf[(i,r['attempt'])]
        j = i-r['distance']
        v = r['forward'] if 'forward' in r else r['retired']
        if j < 0:
            x = data['initial'][v][str(j)]
            return tuple(x) if isinstance(x,list) else x
        if 'forward' in r:
            count('forward_reads')
            if current_time < j*p['ii']+p['retire']:
                count('forward_reads_before_retirement')
            if banks is None:
                return exported[(j, v)]
            cell = banks[v][j % len(banks[v])]
            if cell is None or cell[0] != j:
                raise ValueError('Forwarding slot does not contain the requested iteration')
            return cell[1]
        return committed[(j,v)]
    try:
        while events:
            t,phase,i,rank,kind,name = heapq.heappop(events)
            current_time = t
            env = {k: data['guards'][k][i] for k in p['actual']+p['predicted']
                   if p['guard_ready'][k] <= t - i*p['ii']}
            if kind == 'complete':
                # Pending and completed values occupy disjoint maps; names are opaque.
                val = pending.pop((i,name))
                buf[(i,name)] = val
                if eager_faults and isinstance(val,Token):
                    trace.append(['fault',i,attempts[name]['node'],val.error])
                    return {'trace':trace,'state':state,'status':'fault'}
                continue
            if kind == 'export':
                chosen = [b for b in p['exports'][name]['choices'] if pred(b['when'], env)]
                if len(chosen) != 1:
                    raise ValueError('Export is not a partition')
                val = buf[(i, chosen[0]['attempt'])]
                if banks is None:
                    exported[(i, name)] = val
                else:
                    banks[name][i % len(banks[name])] = (i, val)
                count('exports')
                if isinstance(val, Token):
                    count('fault_exports')
                if t < i*p['ii']+p['retire']:
                    count('exports_before_retirement')
                continue
            if kind == 'issue':
                a = attempts[name]
                if not pred(a['when'],env): continue
                if issue_trace is not None:
                    issue_trace.append({'iteration': i, 'attempt': name, 'time': t})
                v = src[a['node']]
                if a['kind'] == 'op':
                    val = primitive(v['op'],[ref(r,i) for r in a['args']])
                    cost = p['costs'][v['op']]
                elif a['kind'] == 'copy':
                    val = ref(a['args'][0],i)
                    cost = p['costs']['copy']
                else:
                    selected = [b for b in a['choices'] if pred(b['when'],env)]
                    if len(selected) != 1: raise ValueError('Mux is not a partition')
                    val = buf[(i,selected[0]['attempt'])]
                    cost = p['costs']['mux']
                pending[(i,name)] = val
                add(t+cost['latency'],0,i,rank,'complete',name)
            else:
                order = list(reversed(p['nodes'])) if reverse_retirement else p['nodes']
                for v in order:
                    chosen = [b for b in p['retirement'][v['name']] if pred(b['when'],env)]
                    if len(chosen) != 1: raise ValueError('Retirement is not a partition')
                    val = buf[(i,chosen[0]['attempt'])]
                    if isinstance(val,Token):
                        trace.append(['fault',i,v['name'],val.error])
                        return {'trace':trace,'state':state,'status':'fault'}
                    committed[(i,v['name'])] = val
                    state[v['name']] = val
                    if pred(v['guard'],env) and v['emit']:
                        trace.append(['emit',i,v['name'],val])
                if i == n-1:
                    return {'trace':trace,'state':state,'status':'done'}
        raise ValueError('Missing terminal retirement')
    except (KeyError,ValueError,IndexError,TypeError) as ex:
        return {'trace':trace,'state':state,'status':'stuck','detail':str(ex)}
