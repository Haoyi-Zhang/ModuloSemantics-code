"""Independent bounded resource oracle, scanning concrete issue reservations.

No quotient, stage grouping, certificate goodness, or checker routines are used.
The global valuation enumerator has an explicit 18-bit bound.
"""
from itertools import product
from collections import Counter


def boolean(expr, assignment):
    if expr is True or expr is False: return expr
    if isinstance(expr,str): return assignment[expr]
    if expr[0] == 'not': return not boolean(expr[1],assignment)
    vals = [boolean(x,assignment) for x in expr[1:]]
    return (False not in vals) if expr[0] == 'and' else (True in vals)


def scan(p, guards, n):
    counts = Counter()
    nodes = {v['name']:v for v in p['nodes']}
    for i in range(n):
        environment = {k:guards[k][i] for k in p['actual']+p['predicted']}
        for a in p['attempts']:
            if not boolean(a['when'],environment): continue
            key = nodes[a['node']]['op'] if a['kind']=='op' else a['kind']
            c = p['costs'][key]
            for z in c['reserve']:
                counts[(c['resource'],i*p['ii']+a['offset']+z)] += 1
    return dict(counts)


def exhaustive_peak(p, n):
    names = p['actual']+p['predicted']
    if len(names)*n > 18: raise ValueError('Bounded oracle exceeds 18 input bits')
    peaks, witnesses = {}, {}
    count = 0
    for bits in product((False,True),repeat=len(names)*n):
        guards = {key:list(bits[k*n:(k+1)*n]) for k,key in enumerate(names)}
        counts = scan(p,guards,n)
        count += 1
        for (resource,t),number in counts.items():
            phase = t%p['ii']
            if number > peaks.get((resource,phase),0):
                peaks[(resource,phase)] = number
                witnesses[(resource,phase)] = {'time':t,'guards':guards}
    return {'peaks':peaks,'witnesses':witnesses,'assignments':count}
