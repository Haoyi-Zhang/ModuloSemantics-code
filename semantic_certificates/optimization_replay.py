"""Replay a period/bank optimum without running annotation or selector search.

The source skeleton is an explicit, external input. A feasible certificate must
preserve it except for I, optional exports, and Ret/Forward reference tags. Every
smaller positive period is excluded by a resource violation, a replayed causal
obstruction, or a mandatory-lifetime lower bound exceeding the bank budget.

This module trusts the semantic checker, propositional tables and the written
normal-form theorem. It is not a proof-assistant-verified implementation and
does not call hybrid_at, synthesize, selection_at or bank_layout.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from .checker import check, integer
from .frontiers import Candidate, verify_obstruction
from .logic import FormatError, TruthTable


class ReplayError(ValueError):
    """An explicit failed certificate obligation, not an implementation fault."""


def _require(test: bool, message: str) -> None:
    if not test:
        raise ReplayError(message)


def _object(obj: object, keys: set[str], label: str) -> None:
    _require(isinstance(obj, dict) and set(obj) == keys, label + ': unexpected fields')


def _erase_annotation(p: dict) -> dict:
    """Erase only the declared annotation choices, not scientific input fields."""
    q = deepcopy(p)
    q.pop('exports', None)
    q['ii'] = 1
    for a in q['attempts']:
        for r in a.get('args', []):
            if 'forward' in r:
                r['retired'] = r.pop('forward')
    return q


def _facts(skeleton: dict, interval: int) -> tuple:
    integer(interval, 1, 256, 'certificate period')
    _require(isinstance(skeleton, dict), 'Skeleton must be an object')
    p = deepcopy(skeleton)
    p['ii'] = interval
    verdict = check(p)
    for issue in verdict.issues:
        if issue['code'] == 'resource_capacity':
            continue
        if issue['code'] == 'dependence_time' and 'distance' in issue:
            continue
        raise ReplayError('Invalid fixed skeleton: ' + str(issue))
    _require(not p.get('exports'), 'Skeleton already contains exports')
    _require(not any('forward' in r for a in p['attempts'] for r in a.get('args', [])),
             'Skeleton already contains forward references')
    tt = TruthTable(p['actual'] + p['predicted'])
    nodes = {n['name']: n for n in p['nodes']}
    groups: dict[str, list[Candidate]] = {name: [] for name in nodes}
    for a in p['attempts']:
        mask = 0
        for env in verdict.goodness[a['name']]:
            mask |= 1 << tt.envs.index(env)
        op = nodes[a['node']]['op'] if a['kind'] == 'op' else a['kind']
        groups[a['node']].append(Candidate(a['name'],
            a['offset'] + p['costs'][op]['latency'], mask))
    deadlines: dict[str, list[int]] = {}
    for a in p['attempts']:
        if not tt.bits(a['when']):
            continue
        for r in a.get('args', []):
            if 'retired' in r:
                d = a['offset'] + r['distance'] * interval
                if d < p['retire']:
                    deadlines.setdefault(r['retired'], []).append(d)
    endpoints = {v: (min(ds), max(ds)) for v, ds in deadlines.items()}
    lower = sum((last-first)//interval + 1 for first, last in endpoints.values())
    return p, verdict, tt, groups, endpoints, lower


def _cells(q: dict, tt: TruthTable) -> int:
    """Recompute all separate-bank lifetimes from a checked certificate."""
    last = {v: e['offset'] for v, e in q.get('exports', {}).items()}
    for a in q['attempts']:
        if not tt.bits(a['when']):
            continue
        for r in a.get('args', []):
            if 'forward' in r:
                v = r['forward']
                last[v] = max(last[v], a['offset'] + r['distance'] * q['ii'])
    return sum((last[v]-e['offset'])//q['ii'] + 1
               for v, e in q.get('exports', {}).items())


def _row(skeleton: dict, budget: int, row: dict, expected: int, final: bool) -> dict:
    _require(isinstance(row, dict), 'Period row must be an object')
    integer(row.get('interval'), 1, 256, 'row interval')
    _require(row['interval'] == expected, 'Missing, repeated or reordered period')
    p, verdict, tt, groups, endpoints, lower = _facts(skeleton, expected)
    kind = row.get('kind')
    if final:
        _object(row, {'interval', 'kind', 'certificate', 'cells'}, 'Feasible row')
        _require(kind == 'feasible', 'The claimed optimum has no feasible certificate')
        q = row['certificate']
        accepted = check(q)
        _require(accepted.accepted, 'Target certificate rejected: ' + str(accepted.issues))
        _require(q['ii'] == expected and _erase_annotation(q) == _erase_annotation(p),
                 'Target changes the supplied fixed skeleton')
        integer(row['cells'], 0, 2**31-1, 'bank cell count')
        cells = _cells(q, tt)
        _require(row['cells'] == cells == lower, 'Bank count fails the exact lower bound')
        _require(cells <= budget, 'Claimed optimum exceeds the supplied budget')
        return {'interval': expected, 'kind': kind, 'cells': cells}
    if kind == 'budget':
        _object(row, {'interval', 'kind'}, 'Budget exclusion')
        _require(lower > budget, 'Mandatory-lifetime bound does not exceed budget')
    elif kind == 'resource':
        _object(row, {'interval', 'kind', 'resource', 'phase'}, 'Resource exclusion')
        _require(isinstance(row['resource'], str), 'Resource name must be a string')
        integer(row['phase'], 0, expected-1, 'resource phase')
        _require(any(r['resource'] == row['resource'] and r['phase'] == row['phase']
                     and r['peak'] > r['capacity'] for r in verdict.resources),
                 'No matching recomputed capacity violation')
    elif kind == 'selector':
        _object(row, {'interval', 'kind', 'source', 'witness'}, 'Selector exclusion')
        v = row['source']
        _require(isinstance(v, str) and v in endpoints, 'Source has no mandatory export')
        w = row['witness']
        _require(isinstance(w, dict) and w.get('time') == endpoints[v][0],
                 'Obstruction is not at the latest mandatory deadline')
        _require(verify_obstruction(tt, p['guard_ready'], groups[v], w),
                 'Causal obstruction did not replay')
    else:
        raise ReplayError('Unrecognized exclusion reason')
    return {'interval': expected, 'kind': kind, 'mandatory_cell_lower_bound': lower}


def verify_optimum(skeleton: dict, budget: int, proof: dict) -> dict:
    """Return a structured decision; do not hide unexpected implementation errors.

    A positive minimum is global in the mathematical period domain: all smaller
    integers have been excluded. A negative result past the 256-period prototype
    cap is explicitly bounded, unless the complete-by-retirement cutoff is met.
    """
    try:
        integer(budget, 0, 4096, 'forwarding cell budget')
        _object(proof, {'budget', 'minimum_period', 'rows'}, 'Optimum proof')
        integer(proof['budget'], 0, 4096, 'proof budget')
        _require(proof['budget'] == budget, 'Proof refers to a different budget')
        base, _, _, _, _, _ = _facts(skeleton, 1)
        cutoff = max(1, base['retire'])
        winner = proof['minimum_period']
        if winner is not None:
            integer(winner, 1, min(cutoff, 256), 'minimum period')
        through = winner if winner is not None else min(cutoff, 256)
        rows = proof['rows']
        _require(isinstance(rows, list) and len(rows) == through,
                 'Proof must cover the entire required consecutive period prefix')
        checked = [_row(skeleton, budget, r, i, winner == i)
                   for i, r in enumerate(rows, 1)]
        scope = ('all_positive_periods' if winner is not None or cutoff <= 256
                 else 'periods_1_through_256')
        return {'accepted': True, 'issues': [], 'minimum_period': winner,
                'scope': scope, 'checked_through': through,
                'mathematical_cutoff': cutoff, 'rows': checked}
    except (FormatError, ReplayError) as exc:
        return {'accepted': False, 'issues': [{'code': 'optimization_certificate',
                                             'message': str(exc)}]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('skeleton', type=Path)
    ap.add_argument('proof', type=Path)
    ap.add_argument('--budget', required=True, type=int)
    args = ap.parse_args()
    try:
        skeleton = json.loads(args.skeleton.read_text(encoding='utf-8'))
        proof = json.loads(args.proof.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        out = {'accepted': False, 'issues': [{'code': 'format', 'message': str(exc)}]}
    else:
        out = verify_optimum(skeleton, args.budget, proof)
    print(json.dumps(out, sort_keys=True))
    return 0 if out['accepted'] else 2


if __name__ == '__main__':
    sys.exit(main())
