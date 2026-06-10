import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(__file__)
LIB = os.path.join(HERE, "..", "scripts", "lib.sh")
HOOK = os.path.join(HERE, "..", "scripts", "hook-memory.sh")

FACT = "---\nname: %s\ndescription: d\nmetadata:\n  type: %s\n---\nx\n"


def git(clone, *args):
    subprocess.run(["git", "-C", clone, *args], capture_output=True, check=True)


def write(clone, rel, content):
    p = os.path.join(clone, rel)
    os.makedirs(os.path.dirname(p) or clone, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)


def init_repo(clone):
    git(clone, "init", "-q")
    git(clone, "config", "user.email", "t@t")
    git(clone, "config", "user.name", "t")


def count_unpromoted(clone):
    r = subprocess.run(["bash", "-c", 'source "$1"; sm_count_unpromoted "$2"', "_", LIB, clone],
                       capture_output=True, text=True)
    return r.stdout.strip()


class CountUnpromotedTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.c = self._t.name
        init_repo(self.c)
        write(self.c, "mailing/a.md", FACT % ("a", "project"))
        git(self.c, "add", "-A")
        git(self.c, "commit", "-qm", "base")

    def tearDown(self):
        self._t.cleanup()

    def test_counts_new_shareable_fact(self):
        write(self.c, "mailing/b.md", FACT % ("b", "project"))
        self.assertEqual(count_unpromoted(self.c), "1")

    def test_modified_shareable_counts(self):
        write(self.c, "mailing/a.md", FACT % ("a", "project") + "modifié\n")
        self.assertEqual(count_unpromoted(self.c), "1")

    def test_excludes_personal_index_memory(self):
        write(self.c, "feedback_x.md", FACT % ("fx", "feedback"))
        write(self.c, "ui/perso.md", FACT % ("p", "user"))
        write(self.c, "index/mailing.md", "- a\n")
        write(self.c, "MEMORY.md", "# carte\n")
        self.assertEqual(count_unpromoted(self.c), "0")

    def test_no_repo_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(count_unpromoted(d), "0")


if __name__ == "__main__":
    unittest.main()
