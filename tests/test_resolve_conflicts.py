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


FACT = ("---\nname: %s\ndescription: %s\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\n%s\n")


def git(clone, *args):
    subprocess.run(["git", "-C", clone, *args], capture_output=True, check=True)


def write(clone, rel, content):
    p = os.path.join(clone, rel)
    os.makedirs(os.path.dirname(p) or clone, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)


def init_repo(clone):
    git(clone, "init", "-q")
    # Branche par défaut = main (un runner CI peut défaulter sur master) — avant le 1er commit.
    git(clone, "symbolic-ref", "HEAD", "refs/heads/main")
    git(clone, "config", "user.email", "t@t")
    git(clone, "config", "user.name", "t")


def run_script(clone):
    return subprocess.run([sys.executable, SCRIPT, clone], capture_output=True, text=True)


def conflicted(clone):
    r = subprocess.run(["git", "-C", clone, "diff", "--name-only", "--diff-filter=U"],
                       capture_output=True, text=True)
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


class ResolveIntegrationTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.c = self._t.name
        init_repo(self.c)
        write(self.c, "MEMORY.md", "# Carte\n\n## Domaines\n- mailing\n")
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "base")

    def tearDown(self):
        self._t.cleanup()

    def test_derived_only_conflict_auto_resolved(self):
        # branche A : ajoute fait-a + un index/mailing.md "version A"
        git(self.c, "checkout", "-qb", "a")
        write(self.c, "mailing/fait-a.md", FACT % ("fait-a", "premier fait", "corps a"))
        write(self.c, "index/mailing.md", "- `fait-a` — premier fait · project\n")
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "a")
        # branche B (depuis base) : ajoute fait-b + un index/mailing.md "version B"
        git(self.c, "checkout", "-q", "main")
        git(self.c, "checkout", "-qb", "b")
        write(self.c, "mailing/fait-b.md", FACT % ("fait-b", "second fait", "corps b"))
        write(self.c, "index/mailing.md", "- `fait-b` — second fait · project\n")
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "b")
        # fusion -> conflit sur index/mailing.md uniquement (faits = fichiers séparés)
        git(self.c, "checkout", "-q", "a")
        subprocess.run(["git", "-C", self.c, "merge", "--no-ff", "-m", "merge", "b"],
                       capture_output=True)
        self.assertIn("index/mailing.md", conflicted(self.c))
        # l'outil régénère index/mailing.md depuis les deux faits
        r = run_script(self.c)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(conflicted(self.c), [])     # plus aucun chemin non-mergé
        with open(os.path.join(self.c, "index", "mailing.md"), encoding="utf-8") as fh:
            idx = fh.read()
        self.assertNotIn("<<<<<<<", idx)   # marqueurs de conflit disparus = vraie régénération
        self.assertNotIn(">>>>>>>", idx)
        self.assertIn("fait-a", idx)
        self.assertIn("fait-b", idx)

    def test_real_fact_conflict_needs_human(self):
        # base : un fait partagé
        write(self.c, "mailing/partage.md", FACT % ("partage", "fait partagé", "version base"))
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "fact")
        # A et B modifient le MÊME fait différemment
        git(self.c, "checkout", "-qb", "va")
        write(self.c, "mailing/partage.md", FACT % ("partage", "fait partagé", "version A"))
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "va")
        git(self.c, "checkout", "-q", "main")
        git(self.c, "checkout", "-qb", "vb")
        write(self.c, "mailing/partage.md", FACT % ("partage", "fait partagé", "version B"))
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "vb")
        git(self.c, "checkout", "-q", "va")
        subprocess.run(["git", "-C", self.c, "merge", "--no-ff", "-m", "merge", "vb"],
                       capture_output=True)
        self.assertIn("mailing/partage.md", conflicted(self.c))
        # l'outil signale le fait, ne stage rien, sort 1
        r = run_script(self.c)
        self.assertEqual(r.returncode, 1)
        self.assertIn("partage.md", r.stdout)
        self.assertIn("mailing/partage.md", conflicted(self.c))   # toujours en conflit

    def test_map_conflict_needs_human(self):
        # A et B modifient la carte MEMORY.md de façon incompatible (même ligne)
        git(self.c, "checkout", "-qb", "ma")
        write(self.c, "MEMORY.md", "# Carte\n\n## Domaines (vue A)\n- mailing\n")
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "ma")
        git(self.c, "checkout", "-q", "main")
        git(self.c, "checkout", "-qb", "mb")
        write(self.c, "MEMORY.md", "# Carte\n\n## Domaines (vue B)\n- mailing\n")
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "mb")
        git(self.c, "checkout", "-q", "ma")
        subprocess.run(["git", "-C", self.c, "merge", "--no-ff", "-m", "merge", "mb"],
                       capture_output=True)
        self.assertIn("MEMORY.md", conflicted(self.c))
        r = run_script(self.c)
        self.assertEqual(r.returncode, 1)
        self.assertIn("MEMORY.md", r.stdout)
        self.assertIn("MEMORY.md", conflicted(self.c))   # toujours en conflit, rien touché


if __name__ == "__main__":
    unittest.main()
