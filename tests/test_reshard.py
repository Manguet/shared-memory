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

    def test_split_tree_rejects_threshold_below_two(self):
        with self.assertRaises(ValueError):
            R.split_tree([1, 2, 3], 1)


import tempfile


def write_fact(vault, relpath, name, desc="desc discriminante", body="corps"):
    p = os.path.join(vault, relpath)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("---\nname: %s\ndescription: %s\nmetadata:\n  type: project\n---\n%s"
                % (name, desc, body))


def md_files_under(d):
    out = []
    for root, _dirs, files in os.walk(d):
        for fn in files:
            if fn.endswith(".md"):
                out.append(os.path.join(root, fn))
    return out


class ReshardCoreTest(unittest.TestCase):
    def test_small_domain_stays_flat(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(3):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=5)
            subdirs = [e for e in os.listdir(os.path.join(v, "mailing"))
                       if os.path.isdir(os.path.join(v, "mailing", e))]
            self.assertEqual(subdirs, [])
            with open(os.path.join(v, "index", "mailing.md"), encoding="utf-8") as f:
                lines = [l for l in f.read().splitlines() if l.startswith("- ")]
            self.assertEqual(len(lines), 3)

    def test_large_domain_splits_into_subdomains(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(4):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=2)
            mailing = os.path.join(v, "mailing")
            subdirs = sorted(e for e in os.listdir(mailing)
                             if os.path.isdir(os.path.join(mailing, e)))
            self.assertTrue(len(subdirs) >= 2)
            direct = [e for e in os.listdir(mailing) if e.endswith(".md")]
            self.assertEqual(direct, [])
            with open(os.path.join(v, "index", "mailing.md"), encoding="utf-8") as f:
                txt = f.read()
            self.assertIn("faits) → index/mailing/", txt)

    def test_no_fact_lost(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(7):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=2)
            self.assertEqual(len(md_files_under(os.path.join(v, "mailing"))), 7)

    def test_root_facts_untouched(self):
        with tempfile.TemporaryDirectory() as v:
            write_fact(v, "feedback_x.md", "feedback-x")
            for i in range(3):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=2)
            self.assertTrue(os.path.isfile(os.path.join(v, "feedback_x.md")))
            for f in md_files_under(os.path.join(v, "index")):
                self.assertNotIn("feedback-x", open(f, encoding="utf-8").read())

    def test_misplaced_perso_fact_relocated_to_root(self):
        with tempfile.TemporaryDirectory() as v:
            p = os.path.join(v, "mailing", "feedback_oops.md")
            os.makedirs(os.path.dirname(p))
            with open(p, "w", encoding="utf-8") as f:
                f.write("---\nname: feedback-oops\ndescription: d\nmetadata:\n  type: feedback\n---\nx")
            for i in range(3):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=5)
            self.assertTrue(os.path.isfile(os.path.join(v, "feedback-oops.md")))           # relogé racine
            self.assertFalse(os.path.isfile(os.path.join(v, "mailing", "feedback_oops.md")))
            for f in md_files_under(os.path.join(v, "index")):
                self.assertNotIn("feedback-oops", open(f, encoding="utf-8").read())          # hors index

    def test_memory_lists_domains(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(3):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            write_fact(v, "ui/a.md", "a")
            R.reshard(v, max_entries=5)
            mem = open(os.path.join(v, "MEMORY.md"), encoding="utf-8").read()
            self.assertIn("- mailing (3 faits) → index/mailing.md", mem)
            self.assertIn("- ui (1 faits) → index/ui.md", mem)


def index_files_under(vault):
    return md_files_under(os.path.join(vault, "index"))


def index_depth(vault):
    idx = os.path.join(vault, "index")
    return max(len(os.path.relpath(f, idx).split(os.sep)) for f in index_files_under(vault))


def leaf_pointer_targets(vault):
    targets = []
    for f in index_files_under(vault):
        for line in open(f, encoding="utf-8").read().splitlines():
            if line.startswith("- `"):                  # ligne de fait (feuille)
                targets.append(line.split("→")[1].strip().strip("`"))
    return targets


class ReshardRecursionTest(unittest.TestCase):
    def test_two_levels_when_exceeds_n_squared(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(5):                            # 5 > 2*2 => 2 niveaux à n=2
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=2)
            self.assertGreaterEqual(index_depth(v), 3)    # index/mailing/part-xx/part-yy.md
            self.assertEqual(_leaf_count(v), 5)

    def test_each_fact_reachable_by_exactly_one_leaf_pointer(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(7):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=2)
            targets = leaf_pointer_targets(v)
            actual = sorted(os.path.relpath(p, v) for p in md_files_under(os.path.join(v, "mailing")))
            self.assertEqual(sorted(targets), actual)     # bijection pointeurs <-> faits
            self.assertEqual(len(targets), len(set(targets)))

    def test_every_index_within_threshold(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(30):
                write_fact(v, "mailing/f%02d.md" % i, "f%02d" % i)
            R.reshard(v, max_entries=4)
            for f in index_files_under(v):
                entries = [l for l in open(f, encoding="utf-8").read().splitlines()
                           if l.startswith("- ")]
                self.assertLessEqual(len(entries), 4)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(9):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=2)
            snap1 = {os.path.relpath(f, v): open(f, encoding="utf-8").read()
                     for f in index_files_under(v)}
            R.reshard(v, max_entries=2)
            snap2 = {os.path.relpath(f, v): open(f, encoding="utf-8").read()
                     for f in index_files_under(v)}
            self.assertEqual(snap1, snap2)


def _leaf_count(v):
    return len(md_files_under(os.path.join(v, "mailing")))


import subprocess
import sys

RESHARD_PY = os.path.join(HERE, "..", "scripts", "reshard.py")


class CliTest(unittest.TestCase):
    def test_cli_reshards_with_max_entries(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(4):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            r = subprocess.run([sys.executable, RESHARD_PY, v, "--max-entries", "2"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            mailing = os.path.join(v, "mailing")
            subdirs = [e for e in os.listdir(mailing)
                       if os.path.isdir(os.path.join(mailing, e))]
            self.assertTrue(len(subdirs) >= 2)


if __name__ == "__main__":
    unittest.main()
