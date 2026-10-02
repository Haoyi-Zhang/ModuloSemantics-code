"""Sequential executable oracle. Does not import the certificate checker or target.

Values are integers or tuples of integers in the supplied cases. Faults are
explicit, defined observations, not undefined behavior. Source evaluation is lazy.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceFault:
    reason: str


def condition(e: Any, env: dict[str, bool]) -> bool:
    if type(e) is bool:
        return e
    if type(e) is str:
        return env[e]
    tag = e[0]
    if tag == 'not':
        return not condition(e[1], env)
    if tag == 'and':
        ans = True
        for arg in e[1:]:
            if not condition(arg, env):
                ans = False
                break
        return ans
    if tag == 'or':
        for arg in e[1:]:
            if condition(arg, env):
                return True
        return False
    raise ValueError('Bad source guard')


def operation(op: str, a: list[Any]) -> Any:
    for x in a:
        if isinstance(x, SourceFault):
            return x
    try:
        if op == 'id' and len(a) == 1:
            return a[0]
        if op in ('add','sub','mul','div') and len(a) == 2 and all(type(x) is int for x in a):
            x,y = a
            if op == 'add': return x+y
            if op == 'sub': return x-y
            if op == 'mul': return x*y
            if y == 0: return SourceFault('division-by-zero')
            q = abs(x)//abs(y)
            return -q if (x < 0) != (y < 0) else q
        if op == 'load' and len(a) == 2 and isinstance(a[0], tuple) and type(a[1]) is int:
            m,k = a
            return m[k] if 0 <= k < len(m) else SourceFault('bounds')
        if op == 'store' and len(a) == 3 and isinstance(a[0], tuple) and type(a[1]) is int:
            m,k,x = a
            if not 0 <= k < len(m): return SourceFault('bounds')
            return tuple(x if j == k else m[j] for j in range(len(m)))
    except (TypeError, ValueError, IndexError):
        return SourceFault('type')
    return SourceFault('type')


def run_source(p: dict, data: dict) -> dict:
    n = data['n']
    values: dict[tuple[int,str], Any] = {}
    state, trace = {}, []
    def read(r: dict, i: int) -> Any:
        if 'constant' in r: return r['constant']
        if 'input' in r:
            x = data['inputs'][r['input']][i]
            return tuple(x) if isinstance(x,list) else x
        j = i-r['distance']
        if j < 0:
            x = data['initial'][r['node']][str(j)]
            return tuple(x) if isinstance(x,list) else x
        return values[(j,r['node'])]
    for i in range(n):
        env = {k:data['guards'][k][i] for k in p['actual']}
        for v in p['nodes']:
            enabled = condition(v['guard'], env)
            if enabled:
                result = operation(v['op'], [read(r,i) for r in v['args']])
            else:
                result = read(v['fallback'],i)
            if isinstance(result, SourceFault):
                trace.append(['fault',i,v['name'],result.reason])
                return {'trace':trace,'state':state,'status':'fault'}
            values[(i,v['name'])] = result
            state[v['name']] = result
            if enabled and v['emit']:
                trace.append(['emit',i,v['name'],result])
    return {'trace':trace,'state':state,'status':'done'}
