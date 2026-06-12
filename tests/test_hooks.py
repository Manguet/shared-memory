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


def health_issues(clone, project_dir, pull_failed="0", home=None):
    env = dict(os.environ)
    if home:
        env["HOME"] = home
    r = subprocess.run(
        ["bash", "-c", 'source "$1"; sm_health_issues "$2" "$3" "$4"',
         "_", LIB, clone, project_dir, pull_failed],
        capture_output=True, text=True, env=env)
    return r.returncode, r.stdout.strip()


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

    def test_counts_accented_and_spaced_names(self):
        write(self.c, "mailing/modèle.md", FACT % ("modele", "project"))
        write(self.c, "mailing/résumé été.md", FACT % ("resume", "project"))
        self.assertEqual(count_unpromoted(self.c), "2")

    def test_counts_staged_rename_once(self):
        git(self.c, "mv", "mailing/a.md", "mailing/a2.md")
        self.assertEqual(count_unpromoted(self.c), "1")


def run_hook(mode, project_dir, registry, home=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project_dir, SM_REGISTRY=registry)
    if home:
        env["HOME"] = home
    r = subprocess.run(["bash", HOOK, mode], capture_output=True, text=True, env=env)
    return r.returncode, r.stdout.strip()


class HookScriptTest(unittest.TestCase):
    def test_noop_when_not_branched(self):
        with tempfile.TemporaryDirectory() as d:
            reg = os.path.join(d, "registry.json")
            with open(reg, "w") as f:
                f.write('{"projets": []}')
            rc, out = run_hook("start", "/no/such/project", reg)
            self.assertEqual(rc, 0)
            self.assertEqual(out, "")

    def test_end_reminds_when_unpromoted(self):
        with tempfile.TemporaryDirectory() as d:
            clone = os.path.join(d, "clone")
            os.makedirs(clone)
            init_repo(clone)
            write(clone, "mailing/a.md", FACT % ("a", "project"))
            git(clone, "add", "-A")
            git(clone, "commit", "-qm", "base")
            write(clone, "mailing/b.md", FACT % ("b", "project"))
            reg = os.path.join(d, "registry.json")
            with open(reg, "w") as f:
                json.dump({"projets": [{"slug": "-tmp-proj", "clone": clone}]}, f)
            rc, out = run_hook("end", "/tmp/proj", reg)
            self.assertEqual(rc, 0)
            self.assertIn("/memory-promote", out)

    def test_start_emits_digest_with_fact_description(self):
        with tempfile.TemporaryDirectory() as d:
            clone = os.path.join(d, "clone")
            os.makedirs(clone)
            init_repo(clone)
            write(clone, "mailing/relance.md",
                  "---\nname: relance\ndescription: Relancer apres trois jours\n"
                  "metadata:\n  type: project\n  reviewed: 2026-06-01\n---\nx\n")
            git(clone, "add", "-A")
            git(clone, "commit", "-qm", "base")
            reg = os.path.join(d, "registry.json")
            with open(reg, "w") as f:
                json.dump({"projets": [{"slug": "-tmp-proj", "clone": clone}]}, f)
            rc, out = run_hook("start", "/tmp/proj", reg)
            self.assertEqual(rc, 0)
            self.assertIn("Relancer apres trois jours", out)
            self.assertIn("Mémoire d'équipe", out)

    def test_end_silent_when_clean(self):
        with tempfile.TemporaryDirectory() as d:
            clone = os.path.join(d, "clone")
            os.makedirs(clone)
            init_repo(clone)
            write(clone, "mailing/a.md", FACT % ("a", "project"))
            git(clone, "add", "-A")
            git(clone, "commit", "-qm", "base")
            reg = os.path.join(d, "registry.json")
            with open(reg, "w") as f:
                json.dump({"projets": [{"slug": "-tmp-proj", "clone": clone}]}, f)
            rc, out = run_hook("end", "/tmp/proj", reg)
            self.assertEqual(rc, 0)
            self.assertEqual(out, "")


class PluginHooksTest(unittest.TestCase):
    def test_plugin_declares_session_hooks(self):
        with open(os.path.join(HERE, "..", ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        hooks = cfg.get("hooks", {})
        start = json.dumps(hooks.get("SessionStart"))
        end = json.dumps(hooks.get("SessionEnd"))
        self.assertIn("hook-memory.sh", start)
        self.assertIn("start", start)
        self.assertIn("hook-memory.sh", end)
        self.assertIn("end", end)
        self.assertIn("CLAUDE_PLUGIN_ROOT", start)


class HealthIssuesTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = self._t.name
        self.clone = os.path.join(self.d, "clone")
        os.makedirs(self.clone)
        init_repo(self.clone)
        self.home = os.path.join(self.d, "home")
        self.memdir = os.path.join(self.home, ".claude", "projects", "-tmp-proj")
        os.makedirs(self.memdir)

    def tearDown(self):
        self._t.cleanup()

    def _wire_link(self):
        os.symlink(self.clone, os.path.join(self.memdir, "memory"))

    def test_silent_when_healthy(self):
        self._wire_link()
        rc, out = health_issues(self.clone, "/tmp/proj", "0", home=self.home)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_flags_missing_clone(self):
        self._wire_link()
        rc, out = health_issues(os.path.join(self.d, "nope"), "/tmp/proj", "0", home=self.home)
        self.assertNotEqual(out, "")

    def test_flags_unwired_memory_link(self):
        rc, out = health_issues(self.clone, "/tmp/proj", "0", home=self.home)
        self.assertNotEqual(out, "")

    def test_flags_pull_failure(self):
        self._wire_link()
        rc, out = health_issues(self.clone, "/tmp/proj", "1", home=self.home)
        self.assertNotEqual(out, "")

    def test_flags_broken_symlink(self):
        # symlink créé puis cible supprimée -> lien cassé -> signalé
        import shutil
        target = os.path.join(self.d, "disparu")
        os.makedirs(target)
        os.symlink(target, os.path.join(self.memdir, "memory"))
        shutil.rmtree(target)
        rc, out = health_issues(self.clone, "/tmp/proj", "0", home=self.home)
        self.assertEqual(rc, 0)
        self.assertNotEqual(out, "")


class StartRecallTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.d = self._t.name
        self.clone = os.path.join(self.d, "clone")
        os.makedirs(self.clone)
        init_repo(self.clone)
        write(self.clone, "mailing/relance.md",
              "---\nname: relance\ndescription: Relancer apres trois jours\n"
              "metadata:\n  type: project\n  reviewed: 2026-06-01\n---\nx\n")
        git(self.clone, "add", "-A")
        git(self.clone, "commit", "-qm", "base")
        self.reg = os.path.join(self.d, "registry.json")
        with open(self.reg, "w") as f:
            json.dump({"projets": [{"slug": "-tmp-proj", "clone": self.clone}]}, f)
        self.home = os.path.join(self.d, "home")
        self.memdir = os.path.join(self.home, ".claude", "projects", "-tmp-proj")
        os.makedirs(self.memdir)

    def tearDown(self):
        self._t.cleanup()

    def _wire_link(self):
        os.symlink(self.clone, os.path.join(self.memdir, "memory"))

    def test_emits_display_instruction(self):
        self._wire_link()
        rc, out = run_hook("start", "/tmp/proj", self.reg, home=self.home)
        self.assertEqual(rc, 0)
        self.assertIn("affiche", out.lower())

    def test_compact_recall_present(self):
        self._wire_link()
        rc, out = run_hook("start", "/tmp/proj", self.reg, home=self.home)
        self.assertIn("Mémoire d'équipe", out)
        self.assertIn("mailing", out)

    def test_full_digest_still_in_context(self):
        self._wire_link()
        rc, out = run_hook("start", "/tmp/proj", self.reg, home=self.home)
        self.assertIn("Relancer apres trois jours", out)

    def test_doctor_nudge_when_link_broken(self):
        rc, out = run_hook("start", "/tmp/proj", self.reg, home=self.home)
        self.assertEqual(rc, 0)
        self.assertIn("/doctor", out)

    def test_no_doctor_nudge_when_healthy(self):
        self._wire_link()
        rc, out = run_hook("start", "/tmp/proj", self.reg, home=self.home)
        self.assertNotIn("/doctor", out)

    def test_no_ahead_line_without_remote(self):
        self._wire_link()
        rc, out = run_hook("start", "/tmp/proj", self.reg, home=self.home)
        self.assertEqual(rc, 0)
        self.assertNotIn("à récupérer", out)   # vault local sans remote -> pas de ligne amont


if __name__ == "__main__":
    unittest.main()
