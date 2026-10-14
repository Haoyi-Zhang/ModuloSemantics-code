"""Exhaustive two-atom causal selection controls, independent of bitset search."""
from itertools import product
import unittest

from semantic_certificates.frontiers import Candidate, selection_at, obstruction_at, verify_obstruction
from semantic_certificates.logic import TruthTable, support, evaluate


class TwoAtomSelectionTests(unittest.TestCase):
    def test_all_goodness_pairs_and_information_release_boundaries(self):
        table = TruthTable(['p','q'])
        checked = 0
        for first, second, rp, rq, at in product(range(16), range(16), (0,2), (0,2), range(3)):
            releases = {'p':rp,'q':rq}
            candidates = [Candidate('a',0,first), Candidate('b',1,second)]
            known = [atom for atom in table.atoms if releases[atom] <= at]
            classes = {}
            for index, env in enumerate(table.envs):
                classes.setdefault(tuple(env[a] for a in known),[]).append(index)
            expected = all(any(c.ready <= at and all(c.good & (1 << i) for i in indices)
                               for c in candidates) for indices in classes.values())
            result = selection_at(table,releases,candidates,at)
            self.assertEqual(result is not None, expected)
            if result is not None:
                by_name = {c.name:c for c in candidates}
                for choice in result['choices']:
                    self.assertLessEqual(support(choice['when']),set(known))
                for index, env in enumerate(table.envs):
                    selected = [by_name[c['attempt']] for c in result['choices'] if evaluate(c['when'],env)]
                    self.assertEqual(len(selected),1)
                    self.assertLessEqual(selected[0].ready,at)
                    self.assertTrue(selected[0].good & (1 << index))
            else:
                witness = obstruction_at(table,releases,candidates,at)
                self.assertIsNotNone(witness)
                self.assertTrue(verify_obstruction(table,releases,candidates,witness))
            checked += 1
        self.assertEqual(checked,3072)


if __name__ == '__main__':
    unittest.main()
