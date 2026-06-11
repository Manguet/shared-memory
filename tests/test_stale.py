import datetime
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "scripts", "stale.py")
SPEC = importlib.util.spec_from_file_location("stale", SCRIPT)
st = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(st)

TODAY = datetime.date(2026, 6, 11)


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def fact_md(name, desc, reviewed):
    rev = ("  reviewed: %s\n" % reviewed) if reviewed else ""
    return "---\nname: %s\ndescription: %s\nmetadata:\n  type: project\n%s---\ncorps\n" % (
        name, desc, rev)


class IsStaleTest(unittest.TestCase):
    def test_absent_is_stale(self):
        self.assertTrue(st.is_stale("", TODAY))

    def test_recent_is_fresh(self):
        self.assertFalse(st.is_stale("2026-06-01", TODAY))   # 10 j

    def test_boundary_90_stale_89_fresh(self):
        self.assertTrue(st.is_stale("2026-03-13", TODAY))    # 90 j -> périmé
        self.assertFalse(st.is_stale("2026-03-14", TODAY))   # 89 j -> frais

    def test_unparseable_is_stale(self):
        self.assertTrue(st.is_stale("pas-une-date", TODAY))


class DaysOldTest(unittest.TestCase):
    def test_recent(self):
        self.assertEqual(st.days_old("2026-06-01", TODAY), 10)

    def test_absent_is_sentinel(self):
        self.assertGreaterEqual(st.days_old("", TODAY), 10 ** 9)


class StaleFactsTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.v = self._t.name

    def tearDown(self):
        self._t.cleanup()

    def test_only_stale_sorted_oldest_first(self):
        write(os.path.join(self.v, "a", "frais.md"), fact_md("frais", "frais", "2026-06-01"))
        write(os.path.join(self.v, "a", "vieux.md"), fact_md("vieux", "vieux", "2026-01-01"))
        write(os.path.join(self.v, "a", "sansdate.md"), fact_md("sansdate", "sans date", ""))
        res = st.stale_facts(self.v, today=TODAY)
        names = [f["name"] for f in res]
        self.assertNotIn("frais", names)                 # frais exclu
        self.assertEqual(names, ["sansdate", "vieux"])   # non-daté en tête, puis le plus vieux


class SetReviewedTest(unittest.TestCase):
    def test_updates_existing_reviewed(self):
        text = fact_md("x", "une description", "2026-01-01")
        out = st.set_reviewed(text, "2026-06-11")
        self.assertIn("  reviewed: 2026-06-11", out)
        self.assertNotIn("2026-01-01", out)
        self.assertIn("name: x", out)
        self.assertIn("corps", out)

    def test_adds_missing_reviewed(self):
        text = fact_md("x", "une description", "")   # metadata sans reviewed
        out = st.set_reviewed(text, "2026-06-11")
        self.assertIn("  reviewed: 2026-06-11", out)
        self.assertIn("  type: project", out)
        self.assertIn("une description", out)


class RestampCliTest(unittest.TestCase):
    def test_restamp_writes_date(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "f.md")
            write(p, fact_md("f", "une description", "2026-01-01"))
            subprocess.run([sys.executable, SCRIPT, "--restamp", p, "2026-06-11"], check=True)
            with open(p, encoding="utf-8") as fh:
                out = fh.read()
            self.assertIn("  reviewed: 2026-06-11", out)
            self.assertNotIn("2026-01-01", out)


if __name__ == "__main__":
    unittest.main()
