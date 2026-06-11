import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location("similar", os.path.join(HERE, "..", "scripts", "similar.py"))
S = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(S)


def fe(texts):
    return [[1.0, 0.0] if "grp1" in t else [0.0, 1.0] for t in texts]


def write_fact(vault, rel, name, desc):
    p = os.path.join(vault, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("---\nname: %s\ndescription: %s\nmetadata:\n  type: project\n---\ncorps" % (name, desc))


class SimilarRunTest(unittest.TestCase):
    def test_run_detects_near_dup(self):
        with tempfile.TemporaryDirectory() as v:
            write_fact(v, "mailing/a.md", "a", "grp1 alpha")
            res = S.run(v, "grp1 candidat", embed_fn=fe)
            self.assertIn("mailing/a.md", [r["file"] for r in res["similar"]])
            self.assertFalse(res["vector_inactive"])

    def test_run_inactive_without_embed(self):
        with tempfile.TemporaryDirectory() as v:
            write_fact(v, "mailing/a.md", "a", "desc")
            res = S.run(v, "x", embed_fn=None)
            self.assertTrue(res["vector_inactive"])
            self.assertEqual(res["similar"], [])


if __name__ == "__main__":
    unittest.main()
