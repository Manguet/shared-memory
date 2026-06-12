import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "scripts", "eval-recall.py")
SPEC = importlib.util.spec_from_file_location("eval_recall", SCRIPT)
er = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(er)


class MetricsTest(unittest.TestCase):
    def test_recall_at_k(self):
        self.assertTrue(er.recall_at_k(["a", "b", "c"], "b", 2))
        self.assertFalse(er.recall_at_k(["a", "b", "c"], "c", 2))   # au-delà de k
        self.assertFalse(er.recall_at_k(["a", "b"], "z", 2))         # absent

    def test_reciprocal_rank(self):
        self.assertEqual(er.reciprocal_rank(["a", "b", "c"], "a"), 1.0)
        self.assertAlmostEqual(er.reciprocal_rank(["a", "b", "c"], "c"), 1.0 / 3)
        self.assertEqual(er.reciprocal_rank(["a", "b"], "z"), 0.0)


class EvalCasesTest(unittest.TestCase):
    def test_aggregate(self):
        cases = [{"query": "q1", "expect": "a"}, {"query": "q2", "expect": "z"}]
        ranks = {"q1": ["a", "b"], "q2": ["x", "y"]}   # q1 -> rang 1 ; q2 -> raté
        rep = er.eval_cases(cases, lambda q: ranks[q], k=2)
        self.assertEqual(rep["n"], 2)
        self.assertEqual(rep["hits"], 1)
        self.assertEqual(rep["recall_pct"], 50)
        self.assertEqual(rep["mrr"], 0.5)            # (1.0 + 0) / 2
        self.assertEqual(rep["rank1"], 1)
        self.assertEqual(rep["misses"], [{"query": "q2", "expect": "z"}])

    def test_empty(self):
        rep = er.eval_cases([], lambda q: [], k=8)
        self.assertEqual(rep["n"], 0)
        self.assertEqual(rep["recall_pct"], 0)
        self.assertEqual(rep["mrr"], 0.0)


class AutoCasesTest(unittest.TestCase):
    def test_builds_cases_and_skips_no_description(self):
        facts = [{"name": "a", "description": "desc a"},
                 {"name": "b", "description": ""},        # ignoré
                 {"name": "c", "description": "desc c"}]
        cases = er.auto_cases(facts)
        self.assertEqual(cases, [{"query": "desc a", "expect": "a"},
                                 {"query": "desc c", "expect": "c"}])


class ReportTest(unittest.TestCase):
    def test_grep_warning_present(self):
        rep = {"n": 1, "hits": 1, "recall_pct": 100, "mrr": 1.0, "rank1": 1, "misses": []}
        out = er._format_report(rep, 8, vector_inactive=True)
        self.assertIn("fastembed absent", out)
        self.assertIn("recall@k", out)

    def test_semantic_no_warning_lists_misses(self):
        rep = {"n": 2, "hits": 1, "recall_pct": 50, "mrr": 0.5, "rank1": 1,
               "misses": [{"query": "q2", "expect": "z"}]}
        out = er._format_report(rep, 8, vector_inactive=False)
        self.assertNotIn("fastembed absent", out)
        self.assertIn("sémantique", out)
        self.assertIn("`z`", out)


if __name__ == "__main__":
    unittest.main()
