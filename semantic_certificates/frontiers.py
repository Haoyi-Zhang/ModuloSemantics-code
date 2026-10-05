"""Time-indexed selection and certified cross-iteration forwarding.

The synthesizer is untrusted: every returned certificate is checked by check().
The selector existence test is exact *relative to the derived goodness masks*,
not relative to arbitrary arithmetic equivalence. No model or solver is called.
"""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from .checker import check, integer
from .logic import TruthTable, FormatError


@dataclass(frozen=True)
class Candidate:
    name: str
    ready: int
    good: int


class NoFrontier(ValueError):
    """No selector or admitted interval exists in the stated bounded search."""


def _join(op: str, xs: list[Any]) -> Any:
    identity = op == 'and'
    if not xs:
        return identity
    if len(xs) == 1:
        return xs[0]
    if len(xs) <= 32:
        return [op, *xs]
    return _join(op, [_join(op, xs[i:i+32]) for i in range(0, len(xs), 32)])


def _condition(atoms: tuple[str, ...], keys: list[tuple[bool, ...]]) -> Any:
    """A reduced Shannon expression for a set of observation cells.

    This only compresses a truth table; it does not invent new predicates or
    rely on a SAT solver. All atoms are already released.
    """
    if not keys:
        return False
    if len(keys) == 1 << len(atoms):
        return True
    atom, rest = atoms[0], atoms[1:]
    lo = _condition(rest, [k[1:] for k in keys if not k[0]])
    hi = _condition(rest, [k[1:] for k in keys if k[0]])
    if lo == hi:
        return lo
    if lo is False:
        return atom if hi is True else ['and', atom, hi]
    if hi is False:
        return ['not', atom] if lo is True else ['and', ['not', atom], lo]
    if lo is True:
        return ['or', ['not', atom], hi]
    if hi is True:
        return ['or', atom, lo]
    return ['or', ['and', ['not', atom], lo], ['and', atom, hi]]


def _validate_selection_problem(tt: TruthTable, releases: dict[str, int],
                                candidates: list[Candidate]) -> None:
    """Validate the public finite problem, without constructing a selector.

    This check is shared by synthesis and witness replay. It validates syntax
    only; witness replay does not call or trust the selector search.
    """
    if (not isinstance(tt, TruthTable) or len(set(tt.atoms)) != len(tt.atoms)
            or any(not isinstance(a, str) or not a or len(a) > 64 for a in tt.atoms)):
        raise FormatError('Invalid Boolean atom table')
    if not isinstance(releases, dict) or set(releases) != set(tt.atoms):
        raise FormatError('Selection releases must exactly name the Boolean atoms')
    for x in releases.values():
        integer(x, 0, 4096, 'Boolean release')
    if not isinstance(candidates, (list, tuple)) or len(candidates) > 512:
        raise FormatError('Expected at most 512 selector candidates')
    names = set()
    for c in candidates:
        if (not isinstance(c, Candidate) or not isinstance(c.name, str)
                or not c.name or len(c.name) > 64 or c.name in names):
            raise FormatError('Invalid or duplicate selector candidate')
        integer(c.ready, 0, 8192, 'candidate completion')
        if type(c.good) is not int or c.good < 0 or c.good & ~tt.all:
            raise FormatError('Invalid goodness mask')
        names.add(c.name)


def selection_at(tt: TruthTable, releases: dict[str, int],
                 candidates: list[Candidate], at: int) -> dict | None:
    """Construct a released-information selector, or return None.

    All Boolean valuations indistinguishable at `at` must admit a *common*
    completed good ticket. Picking different tickets using an unreleased atom
    is not permitted. A returned object uses only atoms released by `at`.
    """
    integer(at, 0, 4096, 'selection time')
    _validate_selection_problem(tt, releases, candidates)
    known = tuple(a for a in tt.atoms if releases[a] <= at)
    cells: dict[tuple[bool, ...], int] = defaultdict(int)
    for k, env in enumerate(tt.envs):
        cells[tuple(env[a] for a in known)] |= 1 << k
    available = sorted((c for c in candidates if c.ready <= at),
                       key=lambda c: (c.ready, c.name))
    assigned: dict[str, list[tuple[bool, ...]]] = defaultdict(list)
    for key, mask in cells.items():
        chosen = next((c for c in available if not mask & ~c.good), None)
        if chosen is None:
            return None
        assigned[chosen.name].append(key)
    choices = []
    for name, keys in sorted(assigned.items()):
        expr = _condition(known, keys)
        choices.append({'when': expr, 'attempt': name})
    return {'offset': at, 'choices': choices}


def earliest_selection(tt: TruthTable, releases: dict[str, int],
                       candidates: list[Candidate], latest: int) -> dict:
    """The predicate changes only at releases or candidate completions."""
    integer(latest, 0, 4096, 'latest export')
    # Validate before using values()/candidate fields (same discipline as F1).
    selection_at(tt, releases, candidates, 0)
    critical = sorted({0, *releases.values(), *(c.ready for c in candidates)})
    for at in critical:
        if at <= latest:
            out = selection_at(tt, releases, candidates, at)
            if out is not None:
                return out
    raise NoFrontier('No released-information selector by the retirement offset')


def obstruction_at(tt: TruthTable, releases: dict[str, int],
                   candidates: list[Candidate], at: int) -> dict | None:
    """A finite refutation of a Boolean-only selector at `at`, when none exists.

    For a single observation cell, every completed candidate has an explicit
    bad full valuation; unfinished candidates are excluded by their timestamp.
    The checker below replays this witness without the cell-search algorithm.
    """
    if selection_at(tt, releases, candidates, at) is not None:
        return None
    known = tuple(a for a in tt.atoms if releases[a] <= at)
    cells: dict[tuple[bool, ...], int] = defaultdict(int)
    for k, env in enumerate(tt.envs):
        cells[tuple(env[a] for a in known)] |= 1 << k
    for key, mask in cells.items():
        if any(c.ready <= at and not mask & ~c.good for c in candidates):
            continue
        excluded = {}
        for c in candidates:
            excluded[c.name] = ({'not_ready': c.ready} if c.ready > at
                else {'bad_valuation': tt.witness(mask & ~c.good)})
        return {'time': at, 'known': dict(zip(known, key)), 'excluded': excluded}
    raise AssertionError('Missing obstruction after selector failure')


def verify_obstruction(tt: TruthTable, releases: dict[str, int],
                       candidates: list[Candidate], witness: dict) -> bool:
    """Replay an information-cell obstruction, without invoking selection_at.

    Malformed public problem headers return False, just as malformed witnesses
    do. Unexpected implementation errors are not swallowed.
    """
    try:
        _validate_selection_problem(tt, releases, candidates)
    except FormatError:
        return False
    if not isinstance(witness, dict) or set(witness) != {'time','known','excluded'}:
        return False
    at = witness['time']
    if type(at) is not int or not 0 <= at <= 4096:
        return False
    known = witness['known']; excluded = witness['excluded']
    if (not isinstance(known,dict) or not isinstance(excluded,dict)
            or set(known) != {a for a in tt.atoms if releases[a] <= at}
            or any(type(v) is not bool for v in known.values())
            or set(excluded) != {c.name for c in candidates}):
        return False
    for c in candidates:
        item = excluded[c.name]
        if not isinstance(item,dict):
            return False
        if c.ready > at:
            if set(item) != {'not_ready'} or type(item['not_ready']) is not int or item['not_ready'] != c.ready:
                return False
        else:
            if set(item) != {'bad_valuation'}:
                return False
            env = item['bad_valuation']
            if (not isinstance(env,dict) or set(env) != set(tt.atoms)
                    or any(type(v) is not bool for v in env.values())
                    or any(env[a] != val for a,val in known.items())):
                return False
            k = tt.envs.index(env)
            if c.good & (1 << k):
                return False
    return True


def _candidate_sets(p: dict) -> tuple[TruthTable, dict[str, list[Candidate]]]:
    """Use goodness derived by the checker, never user-asserted masks."""
    verdict = check(p)
    for issue in verdict.issues:
        if issue['code'] == 'resource_capacity':
            continue
        if issue['code'] == 'dependence_time' and 'distance' in issue:
            continue
        raise NoFrontier('Input skeleton fails a non-recurrence obligation: ' + str(issue))
    tt = TruthTable(p['actual'] + p['predicted'])
    indices = {tuple(env[a] for a in tt.atoms): k for k, env in enumerate(tt.envs)}
    src = {v['name']: v for v in p['nodes']}
    groups: dict[str, list[Candidate]] = defaultdict(list)
    for a in p['attempts']:
        mask = 0
        for env in verdict.goodness[a['name']]:
            mask |= 1 << indices[tuple(env[x] for x in tt.atoms)]
        op = src[a['node']]['op'] if a['kind'] == 'op' else a['kind']
        done = a['offset'] + p['costs'][op]['latency']
        groups[a['node']].append(Candidate(a['name'], done, mask))
    return tt, groups


def forwarding_uses(p: dict) -> dict[str, list[dict[str, int | str]]]:
    """Satisfiable uses; fields on permanently inactive attempts do not count."""
    tt = TruthTable(p['actual'] + p['predicted'])
    uses: dict[str, list[dict[str, int | str]]] = defaultdict(list)
    for a in p['attempts']:
        if not tt.bits(a['when']):
            continue
        for r in a.get('args', []):
            if 'forward' in r:
                uses[r['forward']].append({'attempt': a['name'], 'offset': a['offset'],
                                           'distance': r['distance']})
    return uses


def timing_bound(p: dict) -> int:
    """Exact recurrence inequality threshold at the specified export times.

    Other local checks and the nonmonotone resource checks remain separate.
    """
    tt = TruthTable(p['actual'] + p['predicted'])
    bound = 1
    for a in p['attempts']:
        if not tt.bits(a['when']):
            continue
        for r in a.get('args', []):
            if 'forward' in r:
                front = p['exports'][r['forward']]['offset']
            elif 'retired' in r:
                front = p['retire']
            else:
                continue
            d = r['distance']
            bound = max(bound, -(-(front-a['offset'])//d))
    return bound


def bank_layout(p: dict) -> dict[str, dict[str, int]]:
    """Uniform labelled-ring sizes for export-before-issue event priority.

    These sizes cover forwarding storage only, not all target storage. The
    tightness claim concerns the labelled reservation envelope, not necessarily
    executions stopped by an earlier fault, and not globally optimal allocation.
    """
    uses = forwarding_uses(p)
    result = {}
    for v, e in p.get('exports', {}).items():
        first = e['offset']
        last = max([first] + [u['distance']*p['ii'] + u['offset'] for u in uses[v]])
        result[v] = {'export': first, 'last_use': last,
                     'slots': (last-first)//p['ii'] + 1}
    return result


def synthesize(p: dict, *, policy: str = 'earliest',
               interval: int | None = None) -> tuple[dict, dict]:
    """Replace retired operands by proved local exports at fixed offsets.

    `earliest` minimizes each certification time. `latest` chooses the last
    time meeting all consumer deadlines at a tested I; it minimizes the
    sufficient uniform labelled-ring size among feasible export times at I.
    We enumerate I rather than assuming resource feasibility is monotone.
    """
    if policy not in ('earliest', 'latest'):
        raise ValueError('policy must be earliest or latest')
    if p.get('exports'):
        raise ValueError('Expected a baseline skeleton without existing exports')
    if interval is not None:
        integer(interval, 1, 256, 'requested interval')
    tt, groups = _candidate_sets(p)
    q = deepcopy(p)
    needed = sorted({r['retired'] for a in p['attempts'] for r in a.get('args', []) if 'retired' in r})
    earliest = {v: earliest_selection(tt, p['guard_ready'], groups[v], p['retire']) for v in needed}
    q['exports'] = deepcopy(earliest)
    for a in q['attempts']:
        for r in a.get('args', []):
            if 'retired' in r:
                r['forward'] = r.pop('retired')
    minimality = {}
    for v, entry in earliest.items():
        t = entry['offset']
        if t:
            witness = obstruction_at(tt, p['guard_ready'], groups[v], t-1)
            if not verify_obstruction(tt, p['guard_ready'], groups[v], witness):
                raise AssertionError('Earliest-export obstruction did not replay')
            minimality[v] = witness
        else:
            minimality[v] = {'nonnegative_time_boundary': 0}
    bound = timing_bound(q)
    uses = forwarding_uses(q)
    tried = []
    # The finite-cutoff theorem permits complete minimum-period search through C.
    # Explicit requested intervals still allow the cutoff-stability tests.
    cutoff = min(max(1, p['retire']), 256)
    intervals = [interval] if interval is not None else range(bound, cutoff + 1)
    for ii in intervals:
        q['ii'] = ii
        q['exports'] = deepcopy(earliest)
        if ii < bound:
            tried.append({'ii': ii, 'accepted': False, 'codes': ['below_frontier_bound']})
            continue
        if policy == 'latest':
            for v in needed:
                at = min([p['retire']] + [u['offset']+u['distance']*ii for u in uses[v]])
                selection = selection_at(tt, p['guard_ready'], groups[v], at)
                if selection is None:
                    raise AssertionError('A feasible deadline lost a previously available selector')
                q['exports'][v] = selection
        verdict = check(q)
        tried.append({'ii': ii, 'accepted': verdict.accepted,
                      'codes': sorted({x['code'] for x in verdict.issues})})
        if verdict.accepted:
            return q, {'policy': policy, 'timing_lower_bound': bound,
                       'earliest': {v: e['offset'] for v, e in earliest.items()},
                       'selected': {v: e['offset'] for v, e in q['exports'].items()},
                       'bank_layout': bank_layout(q), 'minimality': minimality, 'tried': tried}
    raise NoFrontier('No admitted interval in the requested domain; lower bound=' + str(bound))


def design_space(p: dict, *, cell_budget: int | None = None) -> dict:
    """Enumerate the fixed-skeleton period/bank Pareto set up to a proved cutoff.

    With every active attempt complete by C, all meaningful reservations and
    reads have offsets less than C. At I >= C the resource envelope and latest-
    export ring sizes are constant, and all recurrence timing bounds hold.
    Thus 1..C suffices mathematically. The inherited representation caps I at
    256: `complete_for_unbounded_intervals` is false when that cap truncates C.
    A cell budget counts separate uniform forwarding banks, not all registers.
    """
    if cell_budget is not None:
        integer(cell_budget, 0, 4096, 'forwarding cell budget')
    # Fail malformed/non-recurrence skeletons explicitly before enumeration.
    _candidate_sets(p)
    cutoff = max(1, p['retire'])
    rows = []
    for ii in range(1, min(cutoff, 256)+1):
        try:
            q, meta = synthesize(p, policy='latest', interval=ii)
        except NoFrontier as ex:
            rows.append({'ii': ii, 'admitted': False, 'reason': str(ex)})
            continue
        cells = sum(r['slots'] for r in meta['bank_layout'].values())
        rows.append({'ii': ii, 'admitted': True, 'cells': cells,
                     'fits_budget': cell_budget is None or cells <= cell_budget,
                     'export_times': meta['selected']})
    feasible = [r for r in rows if r['admitted']]
    pareto = [r for r in feasible if not any(
        s['ii'] <= r['ii'] and s['cells'] <= r['cells']
        and (s['ii'] < r['ii'] or s['cells'] < r['cells']) for s in feasible)]
    budget_feasible = [r for r in feasible if r['fits_budget']]
    return {'mathematical_cutoff': cutoff, 'enumerated_through': min(cutoff, 256),
            'complete_for_unbounded_intervals': cutoff <= 256, 'rows': rows,
            'pareto': pareto, 'cell_budget': cell_budget,
            'minimum_budget_feasible_ii': min((r['ii'] for r in budget_feasible), default=None)}


def resource_prefix_witness(p: dict, resource: str, phase: int) -> dict:
    """Realize a nonzero envelope component before the first retirement.

    All non-resource certificate obligations must hold, including completion of
    every active attempt by C. This constructs Boolean inputs, not operand data:
    any well-formed ordinary operand streams suffice because faults stay private
    until C. A witness requires a sufficiently long (explicit) finite trip count.
    It is not a claim about an arbitrary already-fixed or fault-truncated input.
    """
    verdict = check(p)
    if any(x['code'] != 'resource_capacity' for x in verdict.issues):
        raise NoFrontier('A startup witness requires all non-resource obligations')
    matches = [r for r in verdict.resources if r['resource'] == resource and r['phase'] == phase]
    if len(matches) != 1:
        raise ValueError('Unknown resource/phase cell')
    row = matches[0]
    stages = [x for x in row['stages'] if x['peak'] > 0]
    if not stages:
        raise ValueError('Zero envelope cell has no positive startup witness')
    k = max(x['stage'] for x in stages)
    n = k+1; time = k*p['ii']+phase
    if not time < p['retire']:
        raise AssertionError('An active reservation extends to or beyond retirement')
    guards = {a: [False]*n for a in p['actual']+p['predicted']}
    for stage in stages:
        iteration = k-stage['stage']
        for atom, value in stage['valuation'].items():
            guards[atom][iteration] = value
    return {'n': n, 'time': time, 'guards': guards, 'resource': resource,
            'phase': phase, 'expected_occupancy': row['peak'], 'capacity': row['capacity'],
            'before_first_retirement': True}


def hybrid_at(p: dict, interval: int) -> tuple[dict, dict]:
    """Minimum separate-bank cells over *all* carried-operand annotations at I.

    A use whose deadline s+dI is before C must be forwarded; every other use
    can remain retired. Dropping these optional forward uses preserves goodness
    and resource activity while relaxing export deadlines and bank lifetimes.
    For each remaining source, choose the latest feasible causal selector.
    This is exact for this fixed skeleton and certificate language, not for all
    equivalent programs, storage coalescing schemes, or dynamic controllers.
    """
    integer(interval, 1, 256, 'requested interval')
    if p.get('exports'):
        raise ValueError('Expected an unannotated retirement-only skeleton')
    tt, groups = _candidate_sets(p)
    q = deepcopy(p); q['ii'] = interval; q['exports'] = {}
    mandatory: dict[str, list[dict]] = defaultdict(list)
    optional_count = 0
    for a in q['attempts']:
        active = bool(tt.bits(a['when']))
        for index, r in enumerate(a.get('args', [])):
            if 'retired' not in r:
                continue
            deadline = a['offset'] + r['distance']*interval
            if active and deadline < p['retire']:
                name = r.pop('retired'); r['forward'] = name
                mandatory[name].append({'attempt': a['name'], 'argument': index,
                                         'deadline': deadline, 'distance': r['distance']})
            else:
                optional_count += 1
    for name, uses in mandatory.items():
        deadline = min(x['deadline'] for x in uses)
        choice = selection_at(tt, p['guard_ready'], groups[name], deadline)
        if choice is None:
            witness = obstruction_at(tt, p['guard_ready'], groups[name], deadline)
            assert verify_obstruction(tt, p['guard_ready'], groups[name], witness)
            raise NoFrontier('Mandatory forwarding has no causal selector: ' +
                             str({'source': name, 'deadline': deadline, 'obstruction': witness}))
        q['exports'][name] = choice
    verdict = check(q)
    if not verdict.accepted:
        raise NoFrontier('Hybrid certificate rejected: '+str(verdict.issues))
    banks = bank_layout(q)
    return q, {'mandatory_uses': dict(mandatory), 'retired_uses': optional_count,
               'exported_sources': len(q['exports']), 'bank_layout': banks,
               'cells': sum(b['slots'] for b in banks.values()),
               'selected': {v:e['offset'] for v,e in q['exports'].items()}}


def hybrid_design_space(p: dict, *, cell_budget: int | None = None) -> dict:
    """Exact fixed-skeleton period/bank frontier including retirement-only uses.

    At I >= C no active carried use needs a private export, hence the minimum
    forwarding bank count is zero. Active reservations have offsets below C,
    so no period beyond C improves either resource admission or the Pareto set.
    Results explicitly flag truncation by the implementation's I<=256 cap.
    """
    if cell_budget is not None:
        integer(cell_budget, 0, 4096, 'forwarding cell budget')
    _candidate_sets(p)
    cutoff = max(1, p['retire']); rows = []
    for ii in range(1, min(cutoff, 256)+1):
        try:
            _, meta = hybrid_at(p, ii)
        except NoFrontier as ex:
            rows.append({'ii':ii, 'admitted':False, 'reason':str(ex)})
            continue
        cells = meta['cells']
        rows.append({'ii':ii, 'admitted':True, 'cells':cells,
                     'fits_budget':cell_budget is None or cells<=cell_budget,
                     'export_times':meta['selected'], 'exported_sources':meta['exported_sources']})
    feasible = [r for r in rows if r['admitted']]
    pareto = [r for r in feasible if not any(
        s['ii']<=r['ii'] and s['cells']<=r['cells'] and (s['ii']<r['ii'] or s['cells']<r['cells'])
        for s in feasible)]
    budget_feasible = [r for r in feasible if r['fits_budget']]
    return {'mathematical_cutoff':cutoff, 'enumerated_through':min(cutoff,256),
            'complete_for_unbounded_intervals':cutoff<=256, 'rows':rows, 'pareto':pareto,
            'cell_budget':cell_budget,
            'minimum_budget_feasible_ii':min((r['ii'] for r in budget_feasible),default=None)}
