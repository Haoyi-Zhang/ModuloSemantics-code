"""Small exhaustive oracles, independently expressed from the frontier checker.

No imports from checker, target, logic or frontiers. These implementations were
co-developed, not independently authored or proof-assistant verified.
"""
from dataclasses import dataclass
from itertools import product
from typing import Any


def enumerate_selectors(releases: list[int], candidates: list[tuple[int, int]], at: int) -> bool:
    """Enumerate complete decision tables, then test observation uniformity.

    Input masks are indexed lexicographically by Boolean valuations. This is a
    small oracle, exponential in the number of valuations as well as atoms.
    """
    valuations = list(product((False, True), repeat=len(releases)))
    observations = [tuple(bit for bit, r in zip(v, releases) if r <= at) for v in valuations]
    for table in product(range(len(candidates)), repeat=len(valuations)):
        seen = {}
        valid = True
        for k, choice in enumerate(table):
            ready, mask = candidates[choice]
            if ready > at or not ((mask >> k) & 1):
                valid = False
                break
            obs = observations[k]
            if obs in seen and seen[obs] != choice:
                valid = False
                break
            seen[obs] = choice
        if valid:
            return True
    return False


def ring_is_safe(ii: int, start: int, last: int, size: int, n: int) -> bool:
    """Explicitly execute labelled writes and reads; no lifetime formula."""
    if size <= 0:
        return False
    cells = [None] * size
    events = sorted([(j*ii+start, 0, j) for j in range(n)] +
                    [(j*ii+last, 1, j) for j in range(n)])
    for _, phase, j in events:
        slot = j % size
        if phase == 0:
            cells[slot] = j
        elif cells[slot] != j:
            return False
    return True


@dataclass(frozen=True)
class ErrorValue:
    why: str


def _bool(e: Any, env: dict[str, bool]) -> bool:
    if type(e) is bool:
        return e
    if type(e) is str:
        return env[e]
    op = e[0]
    values = [_bool(child, env) for child in e[1:]]
    if op == 'not' and len(values) == 1:
        return not values[0]
    if op == 'and':
        return sum(values) == len(values)
    if op == 'or':
        return sum(values) != 0
    raise ValueError('Invalid oracle predicate')


def _op(op: str, xs: list[Any]) -> Any:
    for x in xs:
        if isinstance(x, ErrorValue):
            return x
    arity = {'id': 1, 'add': 2, 'sub': 2, 'mul': 2, 'div': 2, 'load': 2, 'store': 3}
    if op not in arity or len(xs) != arity[op]:
        return ErrorValue('type')
    if op == 'id':
        return xs[0]
    if op in ('load', 'store'):
        if not isinstance(xs[0], tuple) or type(xs[1]) is not int:
            return ErrorValue('type')
        if not 0 <= xs[1] < len(xs[0]):
            return ErrorValue('bounds')
        if op == 'load':
            return xs[0][xs[1]]
        return xs[0][:xs[1]] + (xs[2],) + xs[0][xs[1]+1:]
    if any(type(x) is not int for x in xs):
        return ErrorValue('type')
    x, y = xs
    if op == 'add':
        return x + y
    if op == 'sub':
        return x - y
    if op == 'mul':
        return x * y
    if y == 0:
        return ErrorValue('division-by-zero')
    q, _ = divmod(abs(x), abs(y))
    return -q if (x < 0) != (y < 0) else q


def run_tick(p: dict, data: dict, *, expose_exports: bool = False,
             retirement_first: bool = False) -> dict:
    """Clock-scan oracle rather than a heap-event interpreter.

    Mutant flags intentionally violate the observation contract and are only
    used as negative controls. All storage is unbounded in this oracle.
    """
    n = data['n']
    trace, state = [], {}
    if n == 0:
        return {'trace': trace, 'state': state, 'status': 'done'}
    pending, completed, exported, retired = {}, {}, {}, {}
    nodes = {v['name']: v for v in p['nodes']}
    def env_at(i, t):
        return {a: data['guards'][a][i] for a, r in p['guard_ready'].items() if i*p['ii']+r <= t}
    def read(r, i, t):
        if 'constant' in r:
            return r['constant']
        if 'input' in r:
            if t < i*p['ii']+p['input_ready'][r['input']]:
                raise ValueError('Premature oracle input')
            x = data['inputs'][r['input']][i]
            return tuple(x) if isinstance(x, list) else x
        if 'attempt' in r:
            return completed[i, r['attempt']]
        j = i-r['distance']
        source = r.get('forward', r.get('retired'))
        if j < 0:
            x = data['initial'][source][str(j)]
            return tuple(x) if isinstance(x, list) else x
        return (exported if 'forward' in r else retired)[j, source]
    def choose(choices, i, t):
        selected = [b['attempt'] for b in choices if _bool(b['when'], env_at(i, t))]
        if len(selected) != 1:
            raise ValueError('Oracle selection is not unique')
        return completed[i, selected[0]]
    def observe(i, t):
        order = p['nodes'][::-1] if retirement_first else p['nodes']
        for v in order:
            value = choose(p['retirement'][v['name']], i, t)
            if isinstance(value, ErrorValue):
                trace.append(['fault', i, v['name'], value.why])
                return {'trace': trace, 'state': state, 'status': 'fault'}
            retired[i, v['name']] = value
            state[v['name']] = value
            if v['emit'] and _bool(v['guard'], env_at(i, t)):
                trace.append(['emit', i, v['name'], value])
        if i == n-1:
            return {'trace': trace, 'state': state, 'status': 'done'}
        return None
    try:
        for t in range((n-1)*p['ii']+p['retire']+1):
            for key, (when, value) in list(pending.items()):
                if when == t:
                    completed[key] = value
                    del pending[key]
            for i in range(n):
                for v, entry in p.get('exports', {}).items():
                    if i*p['ii']+entry['offset'] == t:
                        value = choose(entry['choices'], i, t)
                        exported[i, v] = value
                        if expose_exports and isinstance(value, ErrorValue):
                            trace.append(['fault', i, v, value.why])
                            return {'trace': trace, 'state': state, 'status': 'fault'}
            for i in range(n):
                if i*p['ii']+p['retire'] == t:
                    terminal = observe(i, t)
                    if terminal is not None:
                        return terminal
            for i in range(n):
                for a in p['attempts']:
                    if i*p['ii']+a['offset'] != t or not _bool(a['when'], env_at(i, t)):
                        continue
                    if a['kind'] == 'mux':
                        value = choose(a['choices'], i, t)
                        cost = p['costs']['mux']
                    elif a['kind'] == 'copy':
                        value = read(a['args'][0], i, t)
                        cost = p['costs']['copy']
                    else:
                        op = nodes[a['node']]['op']
                        value = _op(op, [read(r, i, t) for r in a['args']])
                        cost = p['costs'][op]
                    pending[i, a['name']] = (t+cost['latency'], value)
        raise ValueError('No oracle termination')
    except (KeyError, ValueError, IndexError, TypeError) as exc:
        return {'trace': trace, 'state': state, 'status': 'stuck', 'detail': str(exc)}


def enumerate_annotations(releases: list[int], candidates: dict[str, list[tuple[int,int]]],
                          uses: list[tuple[str,int,int]], ii: int, retire: int) -> dict:
    """Brute force all retired/forward choices and all integer export times.

    `uses` contains satisfiable (source,distance,consumer-offset) occurrences.
    Local and resource obligations are external to this small component oracle.
    Whole decision tables check each selector and labelled events check storage;
    neither production canonicalization nor its lifetime equation is imported.
    """
    available={(v,t):enumerate_selectors(releases,cs,t)
               for v,cs in candidates.items() for t in range(retire+1)}
    best=None; witness=None; assignments=0; time_tuples=0; bank_cache={}
    for selected in product((False,True),repeat=len(uses)):
        assignments+=1
        if any(not f and retire>s+d*ii for f,(_,d,s) in zip(selected,uses)):
            continue
        names=sorted({v for f,(v,_,_) in zip(selected,uses) if f})
        for times in product(range(retire+1),repeat=len(names)):
            time_tuples+=1; fs=dict(zip(names,times))
            if any(not available[v,fs[v]] for v in names):
                continue
            if any(f and fs[v]>s+d*ii for f,(v,d,s) in zip(selected,uses)):
                continue
            total=0
            for v in names:
                last=max([fs[v]]+[s+d*ii for f,(u,d,s) in zip(selected,uses) if f and u==v])
                key=(fs[v],last)
                if key not in bank_cache:
                    cap=2+(last//ii)
                    size=next(k for k in range(1,cap+1)
                              if ring_is_safe(ii,fs[v],last,k,cap+3))
                    bank_cache[key]=size
                total+=bank_cache[key]
            if best is None or total<best:
                best=total;witness={'forward_occurrences':selected,'export_times':fs}
    return {'minimum_cells':best,'annotation_assignments':assignments,
            'export_time_tuples':time_tuples,'witness':witness}
