"""Structural checker for the restricted periodic ticket language.

It never executes arithmetic operations, asks the interpreter for a source result,
or trusts a supplied goodness formula. Goodness is constructed from source identities.
All rejection diagnostics are data; no certificate text is executed.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from .logic import TruthTable, FormatError, support


@dataclass
class Verdict:
    accepted: bool
    issues: list[dict[str, Any]] = field(default_factory=list)
    goodness: dict[str, list[dict[str, bool]]] = field(default_factory=dict)
    resources: list[dict[str, Any]] = field(default_factory=list)
    checks: int = 0


def integer(x: Any, lo: int, hi: int, label: str) -> int:
    if type(x) is not int or not lo <= x <= hi:
        raise FormatError(f'{label} must be an integer in [{lo}, {hi}]')
    return x


def _release_map(value: Any, expected: set[str], label: str) -> None:
    """Validate a JSON availability object before using mapping methods."""
    if not isinstance(value, dict):
        raise FormatError(f'{label} must be an object')
    if set(value) != expected:
        raise FormatError(f'{label} keys must exactly match declarations')
    for name in sorted(expected):
        integer(value[name], 0, 4096, f'{label}[{name}] release time')


def _source_identity(ref: dict[str, Any]) -> tuple:
    if not isinstance(ref, dict):
        raise FormatError('Reference must be an object')
    if set(ref) == {'input'} and isinstance(ref['input'], str):
        return ('input', ref['input'])
    if set(ref) == {'constant'} and type(ref['constant']) is int:
        return ('constant', ref['constant'])
    if set(ref) == {'node', 'distance'} and isinstance(ref['node'], str):
        return ('node', ref['node'], integer(ref['distance'], 0, 64, 'distance'))
    raise FormatError('Malformed source reference')


def _shape(p: dict[str, Any]) -> None:
    if not isinstance(p, dict):
        raise FormatError('Certificate must be an object')
    required = {'actual', 'predicted', 'guard_ready', 'inputs', 'input_ready',
                'nodes', 'costs', 'resources', 'ii', 'retire', 'attempts', 'retirement'}
    if set(p) not in (required, required | {'exports'}):
        raise FormatError('Missing or unknown top-level field')
    integer(p['ii'], 1, 256, 'initiation interval')
    integer(p['retire'], 0, 4096, 'retirement offset')
    for label in ('actual', 'predicted', 'inputs'):
        a = p[label]
        if not isinstance(a, list) or any(not isinstance(x, str) or not x or len(x) > 64 for x in a):
            raise FormatError(f'Invalid {label}')
        if len(a) != len(set(a)) or len(a) > 32:
            raise FormatError(f'Duplicate or excessive {label}')
    if set(p['actual']) & set(p['predicted']):
        raise FormatError('Actual and predicted atoms must be disjoint')
    atoms = set(p['actual']) | set(p['predicted'])
    if len(atoms) > 10:
        raise FormatError('At most 10 Boolean atoms are supported')
    _release_map(p['guard_ready'], atoms, 'guard_ready')
    _release_map(p['input_ready'], set(p['inputs']), 'input_ready')
    if not isinstance(p['resources'], dict) or not p['resources']:
        raise FormatError('Nonempty capacity map required')
    for x in p['resources'].values():
        integer(x, 1, 256, 'resource capacity')
    if not isinstance(p['costs'], dict) or not {'copy', 'mux'} <= set(p['costs']):
        raise FormatError('Cost table must contain copy and mux')
    for op, cost in p['costs'].items():
        if not isinstance(op, str) or set(cost) != {'latency', 'resource', 'reserve'}:
            raise FormatError('Malformed cost record')
        integer(cost['latency'], 1, 128, 'latency')
        if cost['resource'] not in p['resources']:
            raise FormatError('Unknown resource')
        if not isinstance(cost['reserve'], list) or len(cost['reserve']) > 128:
            raise FormatError('Malformed reservation')
        if len(set(cost['reserve'])) != len(cost['reserve']):
            raise FormatError('Duplicate reservation position')
        for d in cost['reserve']:
            integer(d, 0, cost['latency'] - 1, 'reservation position')
    if not isinstance(p['nodes'], list) or not 1 <= len(p['nodes']) <= 64:
        raise FormatError('Expected between 1 and 64 source nodes')
    names = []
    for v in p['nodes']:
        if set(v) != {'name', 'guard', 'op', 'args', 'fallback', 'emit'}:
            raise FormatError('Malformed source node')
        if not isinstance(v['name'], str) or not v['name'] or v['name'] in names:
            raise FormatError('Duplicate or invalid source identity')
        names.append(v['name'])
        if not support(v['guard']) <= set(p['actual']):
            raise FormatError('Source guard uses a prediction or unknown atom')
        if v['op'] not in p['costs'] or v['op'] in ('copy', 'mux'):
            raise FormatError('Unknown source primitive')
        if type(v['emit']) is not bool or not isinstance(v['args'], list) or len(v['args']) > 8:
            raise FormatError('Malformed source arguments or emission flag')
    ranks = {n: i for i, n in enumerate(names)}
    for v in p['nodes']:
        for r in v['args'] + [v['fallback']]:
            k = _source_identity(r)
            if k[0] == 'input' and k[1] not in p['inputs']:
                raise FormatError('Unknown source input')
            if k[0] == 'node':
                if k[1] not in ranks or (k[2] == 0 and ranks[k[1]] >= ranks[v['name']]):
                    raise FormatError('Source dependence is not well founded')
    if not isinstance(p['attempts'], list) or not 1 <= len(p['attempts']) <= 512:
        raise FormatError('Expected between 1 and 512 attempts')
    if not isinstance(p['retirement'], dict) or set(p['retirement']) != set(names):
        raise FormatError('Retirement must cover exactly the source nodes')
    exports = p.get('exports', {})
    if not isinstance(exports, dict) or not set(exports) <= set(names):
        raise FormatError('exports must be an object indexed by source identities')
    for name, entry in exports.items():
        if not isinstance(entry, dict) or set(entry) != {'offset', 'choices'}:
            raise FormatError('An export must contain exactly offset and choices')
        integer(entry['offset'], 0, p['retire'], 'export offset')
        if not isinstance(entry['choices'], list) or not 1 <= len(entry['choices']) <= 512:
            raise FormatError('Empty or excessive export choices')


def check(p: dict[str, Any]) -> Verdict:
    out = Verdict(False)
    try:
        _shape(p)
        tt = TruthTable(p['actual'] + p['predicted'])
        nodes = {v['name']: v for v in p['nodes']}
        attempts: dict[str, dict] = {}
        good: dict[str, int] = {}
        active: dict[str, int] = {}
        costs: dict[str, dict] = {}
        end: dict[str, int] = {}
        allbits = tt.all
        def issue(code: str, location: str, bad: int = allbits, **details: Any) -> None:
            out.checks += 1
            if bad:
                out.issues.append({'code': code, 'location': location,
                                   'valuation': tt.witness(bad), **details})
        def ready(expr: Any, at: int, loc: str, needed: int) -> None:
            for atom in support(expr):
                issue('guard_availability', loc, needed if p['guard_ready'][atom] > at else 0,
                      atom=atom, release=p['guard_ready'][atom], use=at)
        def ref_good(r: dict, expected: tuple, consumer: dict, use: int) -> int:
            loc, t = consumer['name'], consumer['offset']
            if not isinstance(r, dict):
                raise FormatError('Attempt reference must be an object')
            if set(r) == {'attempt'}:
                parent = r['attempt']
                if parent not in attempts:
                    raise FormatError('Attempt references must point backwards in the list')
                identity = ('node', attempts[parent]['node'], 0)
                issue('identity', loc, use if identity != expected else 0,
                      expected=expected, actual=identity)
                issue('producer_activation', loc, use & ~active[parent], parent=parent)
                issue('dependence_time', loc, use if end[parent] > t else 0,
                      parent=parent, ready=end[parent], use=t)
                return good[parent]
            if set(r) == {'forward', 'distance'}:
                d = integer(r['distance'], 1, 64, 'forward distance')
                parent = r['forward']
                if not isinstance(parent, str) or parent not in p.get('exports', {}):
                    raise FormatError('Forward reference requires a declared export')
                identity = ('node', parent, d)
                issue('identity', loc, use if identity != expected else 0,
                      expected=expected, actual=identity)
                rt = p['exports'][parent]['offset'] - d * p['ii']
                issue('forward_time', loc, use if rt > t else 0,
                      parent=parent, distance=d, ready=rt, use=t)
                # This is justified by the separate export obligations below,
                # not by trusting a supplied correctness assertion.
                return allbits
            if set(r) == {'retired', 'distance'}:
                d = integer(r['distance'], 1, 64, 'retired distance')
                if r['retired'] not in nodes:
                    raise FormatError('Unknown retired source identity')
                identity = ('node', r['retired'], d)
                issue('identity', loc, use if identity != expected else 0,
                      expected=expected, actual=identity)
                rt = p['retire'] - d * p['ii']
                issue('dependence_time', loc, use if rt > t else 0,
                      parent=r['retired'], distance=d, ready=rt, use=t)
                return allbits
            identity = _source_identity(r)
            if identity[0] not in ('constant', 'input'):
                raise FormatError('Local source values require an attempt reference')
            if identity[0] == 'input':
                if identity[1] not in p['inputs']:
                    raise FormatError('Unknown attempt input')
                issue('input_availability', loc,
                      use if p['input_ready'][identity[1]] > t else 0)
            issue('identity', loc, use if identity != expected else 0,
                  expected=expected, actual=identity)
            return allbits
        for a in p['attempts']:
            if not isinstance(a, dict) or not {'name','node','kind','when','offset'} <= set(a):
                raise FormatError('Malformed attempt')
            name = a['name']
            if not isinstance(name, str) or not name or name in attempts:
                raise FormatError('Duplicate or invalid attempt name')
            if a['node'] not in nodes or a['kind'] not in ('op','copy','mux'):
                raise FormatError('Unknown attempt kind or source identity')
            v = nodes[a['node']]
            integer(a['offset'], 0, 4096, 'attempt offset')
            act = tt.bits(a['when'])
            ready(a['when'], a['offset'], name, allbits)
            c = p['costs'][v['op'] if a['kind'] == 'op' else a['kind']]
            issue('retirement_time', name,
                  act if a['offset'] + c['latency'] > p['retire'] else 0)
            if a['kind'] in ('op','copy'):
                if set(a) != {'name','node','kind','when','offset','args'}:
                    raise FormatError('Unknown or missing computation field')
                expected = v['args'] if a['kind'] == 'op' else [v['fallback']]
                if not isinstance(a['args'], list) or len(a['args']) != len(expected):
                    raise FormatError('Incorrect attempt arity')
                g = act
                for actual, source in zip(a['args'], expected):
                    g &= ref_good(actual, _source_identity(source), a, act)
                src = tt.bits(v['guard'])
                g &= src if a['kind'] == 'op' else allbits ^ src
            else:
                if set(a) != {'name','node','kind','when','offset','choices'}:
                    raise FormatError('Unknown or missing mux field')
                if not isinstance(a['choices'], list) or not 1 <= len(a['choices']) <= 64:
                    raise FormatError('Empty or excessive mux choices')
                union, g = 0, 0
                for b in a['choices']:
                    if set(b) != {'when','attempt'} or b['attempt'] not in attempts:
                        raise FormatError('Invalid mux choice')
                    mask = tt.bits(b['when'])
                    ready(b['when'], a['offset'], name, act)
                    issue('choice_overlap', name, act & union & mask)
                    union |= mask
                    pg = ref_good({'attempt':b['attempt']}, ('node',a['node'],0), a, act & mask)
                    g |= mask & pg
                issue('choice_coverage', name, act & ~union)
                g &= act
            attempts[name], active[name], good[name] = a, act, g
            costs[name], end[name] = c, a['offset'] + c['latency']
        for v in p['nodes']:
            name, union = v['name'], 0
            ready(v['guard'], p['retire'], 'retire:'+name, allbits)
            choices = p['retirement'][name]
            if not isinstance(choices, list) or not 1 <= len(choices) <= 64:
                raise FormatError('Empty or excessive retirement choices')
            for b in choices:
                if set(b) != {'when','attempt'} or b['attempt'] not in attempts:
                    raise FormatError('Invalid retirement choice')
                mask, a = tt.bits(b['when']), b['attempt']
                ready(b['when'], p['retire'], 'retire:'+name, allbits)
                issue('choice_overlap', 'retire:'+name, union & mask)
                union |= mask
                issue('identity', 'retire:'+name,
                      mask if attempts[a]['node'] != name else 0)
                issue('retirement_goodness', 'retire:'+name, mask & ~good[a], selected=a)
                issue('retirement_time', 'retire:'+name,
                      mask if end[a] > p['retire'] else 0)
            issue('choice_coverage', 'retire:'+name, allbits & ~union)
        for name, entry in p.get('exports', {}).items():
            union, at, loc = 0, entry['offset'], 'export:' + name
            for b in entry['choices']:
                if (not isinstance(b, dict) or set(b) != {'when', 'attempt'}
                        or not isinstance(b['attempt'], str) or b['attempt'] not in attempts):
                    raise FormatError('Invalid export choice')
                mask, parent = tt.bits(b['when']), b['attempt']
                # Every selector is evaluated, including a false selector.
                ready(b['when'], at, loc, allbits)
                issue('choice_overlap', loc, union & mask)
                union |= mask
                issue('identity', loc, mask if attempts[parent]['node'] != name else 0)
                issue('export_goodness', loc, mask & ~good[parent], selected=parent)
                issue('export_time', loc, mask if end[parent] > at else 0,
                      selected=parent, ready=end[parent], use=at)
            issue('choice_coverage', loc, allbits & ~union)
        # Exact on the activation envelope: different stages at a fixed phase
        # belong to different logical iterations and have independent valuations.
        buckets: dict[tuple, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
        for name, a in attempts.items():
            c = costs[name]
            for delta in c['reserve']:
                stage, phase = divmod(a['offset'] + delta, p['ii'])
                buckets[(c['resource'], phase)][stage].append(name)
        for (resource, phase), stages in sorted(buckets.items()):
            peak, contributions = 0, []
            for stage, names in sorted(stages.items()):
                counts = [sum(bool(active[n] & (1 << k)) for n in names)
                          for k in range(len(tt.envs))]
                maximum = max(counts, default=0)
                witness = tt.envs[counts.index(maximum)]
                peak += maximum
                contributions.append({'stage':stage,'peak':maximum,
                                      'valuation':witness,'attempts':names})
            row = {'resource':resource,'phase':phase,'peak':peak,
                   'capacity':p['resources'][resource],'stages':contributions}
            out.resources.append(row)
            issue('resource_capacity', f'{resource}@{phase}',
                  allbits if peak > p['resources'][resource] else 0,
                  peak=peak, capacity=p['resources'][resource])
        out.goodness = {n:[env for k,env in enumerate(tt.envs) if g & (1<<k)]
                        for n,g in good.items()}
        out.accepted = not out.issues
    except (FormatError, KeyError, TypeError, ValueError, IndexError) as exc:
        out.issues.append({'code':'format','message':str(exc)})
        out.accepted = False
    return out
