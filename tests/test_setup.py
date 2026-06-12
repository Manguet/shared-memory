import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(__file__)
LIB = os.path.join(HERE, "..", "scripts", "lib.sh")


def git(clone, *args):
    subprocess.run(["git", "-C", clone, *args], capture_output=True, check=True)


def status(clone):
    return subprocess.run(["git", "-C", clone, "status", "--porcelain"],
                          capture_output=True, text=True).stdout


def ensure_ignore(clone):
    subprocess.run(["bash", "-c", 'source "$1"; sm_ensure_personal_ignore "$2"', "_", LIB, clone],
                   capture_output=True, check=True)


class PersonalIgnoreTest(unittest.TestCase):
    def test_feedback_ignored_and_idempotent(self):
        with tempfile.TemporaryDirectory() as c:
            git(c, "init", "-q")
            git(c, "config", "user.email", "t@t")
            git(c, "config", "user.name", "t")
            with open(os.path.join(c, "feedback_x.md"), "w") as f:
                f.write("perso")
            self.assertIn("feedback_x.md", status(c))      # avant : non suivi, visible
            ensure_ignore(c)
            self.assertNotIn("feedback_x.md", status(c))   # après : ignoré
            excl = Path(os.path.join(c, ".git", "info", "exclude")).read_text()
            self.assertEqual(excl.count("feedback_*.md"), 1)
            ensure_ignore(c)                               # idempotent
            excl2 = Path(os.path.join(c, ".git", "info", "exclude")).read_text()
            self.assertEqual(excl2.count("feedback_*.md"), 1)

    def test_no_repo_is_noop(self):
        with tempfile.TemporaryDirectory() as d:
            ensure_ignore(d)                               # pas un dépôt git -> ne casse pas
            self.assertFalse(os.path.exists(os.path.join(d, ".git", "info", "exclude")))


class CiWorkflowTest(unittest.TestCase):
    def test_workflow_runs_unittest_on_push_and_pr(self):
        p = os.path.join(HERE, "..", ".github", "workflows", "tests.yml")
        txt = Path(p).read_text(encoding="utf-8")
        self.assertIn("unittest discover", txt)
        self.assertIn("pull_request", txt)
        self.assertIn("push", txt)


if __name__ == "__main__":
    unittest.main()
