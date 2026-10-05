"""Untrusted producer of replayable fixed-skeleton budget certificates."""
from copy import deepcopy
from .checker import check, integer
from .frontiers import _candidate_sets, hybrid_at, obstruction_at


def certify_budget(skeleton: dict, budget: int) -> dict:
    integer(budget, 0, 4096, 'forwarding cell budget')
    if not isinstance(skeleton, dict) or skeleton.get('exports'):
        raise ValueError('Expected a retirement-only fixed skeleton')
    tt, groups = _candidate_sets(skeleton)
    rows = []
    for interval in range(1, min(max(1, skeleton['retire']), 256)+1):
        p = deepcopy(skeleton); p['ii'] = interval
        verdict = check(p)
        bad = next((r for r in verdict.resources if r['peak'] > r['capacity']), None)
        if bad is not None:
            rows.append({'interval': interval, 'kind': 'resource',
                         'resource': bad['resource'], 'phase': bad['phase']})
            continue
        deadlines = {}
        for a in p['attempts']:
            if not tt.bits(a['when']):
                continue
            for r in a.get('args', []):
                if 'retired' in r:
                    d = a['offset'] + r['distance']*interval
                    if d < p['retire']:
                        deadlines.setdefault(r['retired'], []).append(d)
        bad_choice = None
        for v, ds in sorted(deadlines.items()):
            w = obstruction_at(tt, p['guard_ready'], groups[v], min(ds))
            if w is not None:
                bad_choice = {'interval': interval, 'kind': 'selector',
                              'source': v, 'witness': w}
                break
        if bad_choice is not None:
            rows.append(bad_choice)
            continue
        lower = sum((max(ds)-min(ds))//interval+1 for ds in deadlines.values())
        if lower > budget:
            rows.append({'interval': interval, 'kind': 'budget'})
            continue
        q, meta = hybrid_at(skeleton, interval)
        rows.append({'interval': interval, 'kind': 'feasible',
                     'certificate': q, 'cells': meta['cells']})
        return {'budget': budget, 'minimum_period': interval, 'rows': rows}
    return {'budget': budget, 'minimum_period': None, 'rows': rows}
