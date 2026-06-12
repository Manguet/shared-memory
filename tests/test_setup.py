import glob
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(__file__)
LIB = os.path.join(HERE, "..", "scripts", "lib.sh")
SETUP = os.path.join(HERE, "..", "scripts", "setup-vault.sh")


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


def _git(cwd, *args):
    subprocess.run(["git", "-C", cwd, *args], capture_output=True, check=True)


def _slug_of(path):
    return subprocess.run(["bash", "-c", 'source "$1"; sm_slug "$2"', "_", LIB, path],
                          capture_output=True, text=True).stdout.strip()


class SetupVaultTest(unittest.TestCase):
    """E2E du vrai setup-vault.sh (symétrique de UnlinkVaultTest). Isolation totale :
    HOME, SM_REGISTRY surchargés ; le « remote » est un dépôt bare local seedé sur main."""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = self._t.name
        self.home = os.path.join(self.d, "home")
        os.makedirs(self.home)
        self.reg = os.path.join(self.d, "registry.json")
        self.project_dir = os.path.join(self.d, "myproject")
        os.makedirs(self.project_dir)
        self.clone = os.path.join(self.d, "clone")
        # « Remote » = dépôt bare seedé avec un commit initial sur main (portable).
        self.remote = os.path.join(self.d, "remote.git")
        self._seed_remote()
        self.slug = _slug_of(self.project_dir)
        self.memory_dir = os.path.join(
            self.home, ".claude", "projects", self.slug, "memory")

    def tearDown(self):
        self._t.cleanup()

    def _seed_remote(self):
        seed = os.path.join(self.d, "seed")
        os.makedirs(seed)
        _git(seed, "init", "-q")
        # Branche par défaut = main, indépendamment de init.defaultBranch de l'hôte.
        _git(seed, "symbolic-ref", "HEAD", "refs/heads/main")
        _git(seed, "config", "user.email", "t@t")
        _git(seed, "config", "user.name", "t")
        with open(os.path.join(seed, "MEMORY.md"), "w", encoding="utf-8") as f:
            f.write("# Carte\n")
        _git(seed, "add", "-A")
        _git(seed, "commit", "-qm", "seed")
        _git(seed, "clone", "-q", "--bare", seed, self.remote)

    def _run(self):
        env = dict(os.environ, HOME=self.home, SM_REGISTRY=self.reg)
        env.pop("SHARED_MEMORY_HOME", None)
        return subprocess.run(["bash", SETUP, self.remote, self.clone, self.project_dir],
                              capture_output=True, text=True, env=env)

    def _registry_entry(self):
        with open(self.reg, encoding="utf-8") as f:
            reg = json.load(f)
        for p in reg.get("projets", []):
            if p.get("slug") == self.slug:
                return p
        return None

    def test_fresh_setup_clones_symlinks_and_registers(self):
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # 1. Le clone existe (dépôt git + MEMORY.md récupéré).
        self.assertTrue(os.path.isdir(os.path.join(self.clone, ".git")))
        self.assertTrue(os.path.isfile(os.path.join(self.clone, "MEMORY.md")))
        # 2. Le symlink mémoire pointe vers le clone.
        self.assertTrue(os.path.islink(self.memory_dir))
        self.assertEqual(os.path.realpath(self.memory_dir),
                         os.path.realpath(self.clone))
        # 3. Le registre a l'entrée du projet avec clone/symlink corrects.
        entry = self._registry_entry()
        self.assertIsNotNone(entry)
        self.assertEqual(entry["clone"], self.clone)
        self.assertEqual(entry["symlink"], self.memory_dir)
        self.assertEqual(entry["project_dir"], self.project_dir)
        self.assertEqual(entry["vault"], self.remote)

    def test_existing_real_memory_dir_is_backed_up_not_destroyed(self):
        # Pré-crée un VRAI dossier mémoire (pas un symlink) avec un fichier dedans.
        os.makedirs(self.memory_dir)
        sentinel = os.path.join(self.memory_dir, "local-fait.md")
        with open(sentinel, "w", encoding="utf-8") as f:
            f.write("mémoire locale précieuse")
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # Le dossier mémoire est désormais un symlink vers le clone.
        self.assertTrue(os.path.islink(self.memory_dir))
        self.assertEqual(os.path.realpath(self.memory_dir),
                         os.path.realpath(self.clone))
        # L'ancien dossier a été DÉPLACÉ vers un sibling *.local-backup-* (non détruit).
        backups = glob.glob(self.memory_dir + ".local-backup-*")
        self.assertEqual(len(backups), 1, backups)
        preserved = os.path.join(backups[0], "local-fait.md")
        self.assertTrue(os.path.isfile(preserved))
        self.assertEqual(Path(preserved).read_text(encoding="utf-8"),
                         "mémoire locale précieuse")


class CiWorkflowTest(unittest.TestCase):
    def test_workflow_runs_unittest_on_push_and_pr(self):
        p = os.path.join(HERE, "..", ".github", "workflows", "tests.yml")
        txt = Path(p).read_text(encoding="utf-8")
        self.assertIn("unittest discover", txt)
        self.assertIn("pull_request", txt)
        self.assertIn("push", txt)


if __name__ == "__main__":
    unittest.main()
