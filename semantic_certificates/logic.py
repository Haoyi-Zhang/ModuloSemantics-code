"""A deliberately small propositional language; no solver or external dependency."""
from itertools import product
from typing import Any, Iterable


class FormatError(ValueError):
    pass


def support(expr: Any, depth: int = 0) -> frozenset[str]:
    if depth > 32:
        raise FormatError('Boolean expression nesting exceeds 32')
    if isinstance(expr, bool):
        return frozenset()
    if isinstance(expr, str) and expr and len(expr) <= 64:
        return frozenset((expr,))
    if not isinstance(expr, list) or not expr:
        raise FormatError('Expected a Boolean constant, atom, or expression')
    tag, *args = expr
    if tag == 'not' and len(args) == 1:
        return support(args[0], depth + 1)
    if tag in ('and', 'or') and 1 <= len(args) <= 32:
        return frozenset().union(*(support(a, depth + 1) for a in args))
    raise FormatError('Malformed Boolean operator')


def evaluate(expr: Any, env: dict[str, bool]) -> bool:
    if isinstance(expr, bool):
        return expr
    if isinstance(expr, str):
        return env[expr]
    if expr[0] == 'not':
        return not evaluate(expr[1], env)
    if expr[0] == 'and':
        return all(evaluate(e, env) for e in expr[1:])
    if expr[0] == 'or':
        return any(evaluate(e, env) for e in expr[1:])
    raise FormatError('Unknown Boolean operator')


class TruthTable:
    def __init__(self, atoms: Iterable[str]):
        self.atoms = tuple(sorted(atoms))
        if len(self.atoms) > 10:
            raise FormatError('At most 10 local Boolean atoms are supported')
        self.envs = tuple(dict(zip(self.atoms, bits))
                          for bits in product((False, True), repeat=len(self.atoms)))
        self.all = (1 << len(self.envs)) - 1

    def bits(self, expr: Any) -> int:
        if not support(expr) <= set(self.atoms):
            raise FormatError('Unknown Boolean atom')
        out = 0
        for k, env in enumerate(self.envs):
            if evaluate(expr, env):
                out |= 1 << k
        return out

    def witness(self, bits: int) -> dict[str, bool] | None:
        if not bits:
            return None
        return self.envs[(bits & -bits).bit_length() - 1].copy()
