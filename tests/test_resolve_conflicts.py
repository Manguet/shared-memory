import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "scripts", "resolve-conflicts.py")
SPEC = importlib.util.spec_from_file_location("resolve_conflicts", SCRIPT)
rc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rc)


class ClassifyConflictsTest(unittest.TestCase):
    def test_index_paths_are_derived(self):
        c = rc.classify_conflicts(["index/mailing.md", "index/mailing/sous.md"])
        self.assertEqual(c["derived"], ["index/mailing.md", "index/mailing/sous.md"])
        self.assertEqual(c["facts"], [])

    def test_memory_is_map(self):
        c = rc.classify_conflicts(["MEMORY.md"])
        self.assertEqual(c["map"], ["MEMORY.md"])

    def test_fact_md_is_fact(self):
        c = rc.classify_conflicts(["mailing/relance.md", "feedback_x.md"])
        self.assertEqual(sorted(c["facts"]), ["feedback_x.md", "mailing/relance.md"])

    def test_non_md_is_other(self):
        c = rc.classify_conflicts(["notes.txt"])
        self.assertEqual(c["other"], ["notes.txt"])

    def test_mixed_partition_total(self):
        paths = ["index/mailing.md", "MEMORY.md", "mailing/relance.md", "notes.txt"]
        c = rc.classify_conflicts(paths)
        self.assertEqual(c["derived"], ["index/mailing.md"])
        self.assertEqual(c["map"], ["MEMORY.md"])
        self.assertEqual(c["facts"], ["mailing/relance.md"])
        self.assertEqual(c["other"], ["notes.txt"])
        # partition totale : pas de perte, pas de doublon
        self.assertEqual(sum(len(v) for v in c.values()), len(paths))

    def test_empty(self):
        c = rc.classify_conflicts([])
        self.assertEqual(c, {"derived": [], "map": [], "facts": [], "other": []})


if __name__ == "__main__":
    unittest.main()
