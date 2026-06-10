import importlib.util
import os
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "reshard", os.path.join(HERE, "..", "scripts", "reshard.py"))
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


class HelpersTest(unittest.TestCase):
    def test_balanced_chunks_even_and_remainder(self):
        self.assertEqual(R.balanced_chunks([0, 1, 2, 3, 4], 2), [[0, 1, 2], [3, 4]])
        self.assertEqual(R.balanced_chunks(list(range(10)), 3),
                         [[0, 1, 2, 3], [4, 5, 6], [7, 8, 9]])

    def test_balanced_chunks_preserves_all_items(self):
        chunks = R.balanced_chunks(list(range(23)), 4)
        self.assertEqual([x for c in chunks for x in c], list(range(23)))
        self.assertEqual(len(chunks), 4)

    def test_split_tree_leaf_when_small(self):
        self.assertEqual(R.split_tree([1, 2], 3), {"leaf": [1, 2]})

    def test_split_tree_one_level(self):
        t = R.split_tree(list(range(4)), 3)
        self.assertIn("children", t)
        self.assertTrue(all("leaf" in c for c in t["children"]))
        self.assertTrue(all(len(c["leaf"]) <= 3 for c in t["children"]))

    def test_split_tree_recurses_when_needed(self):
        t = R.split_tree(list(range(10)), 3)   # 10 > 3*3 => 2 niveaux
        self.assertIn("children", t)
        self.assertTrue(any("children" in c for c in t["children"]))
        self.assertLessEqual(len(t["children"]), 3)


if __name__ == "__main__":
    unittest.main()
