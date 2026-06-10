import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "gen_synth", os.path.join(HERE, "..", "scripts", "gen-synth-vault.py"))
G = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G)


def md_count(d):
    n = 0
    for _root, _dirs, files in os.walk(d):
        n += sum(1 for f in files if f.endswith(".md"))
    return n


class GenTest(unittest.TestCase):
    def test_generates_domains_with_fact_counts_in_range(self):
        with tempfile.TemporaryDirectory() as dest:
            counts = G.generate(dest, source=None, domains=3, fmin=5, fmax=8, seed=1)
            self.assertEqual(len(counts), 3)
            for dom, n in counts.items():
                self.assertTrue(5 <= n <= 8)
                self.assertEqual(md_count(os.path.join(dest, dom)), n)

    def test_seed_is_reproducible(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            c1 = G.generate(d1, source=None, domains=4, fmin=5, fmax=20, seed=42)
            c2 = G.generate(d2, source=None, domains=4, fmin=5, fmax=20, seed=42)
            self.assertEqual(c1, c2)

    def test_copies_source_facts(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dest:
            os.makedirs(os.path.join(src, "mailing"))
            with open(os.path.join(src, "mailing", "real.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: real\ndescription: vrai\nmetadata:\n  type: project\n---\nx")
            os.makedirs(os.path.join(src, ".git"))
            with open(os.path.join(src, ".git", "config"), "w") as f:
                f.write("[core]")
            G.generate(dest, source=src, domains=2, fmin=5, fmax=8, seed=1)
            self.assertTrue(os.path.isfile(os.path.join(dest, "mailing", "real.md")))
            self.assertFalse(os.path.exists(os.path.join(dest, ".git")))


if __name__ == "__main__":
    unittest.main()
