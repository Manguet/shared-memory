import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(__file__)
LIB = os.path.join(HERE, "..", "scripts", "lib.sh")
UNLINK = os.path.join(HERE, "..", "scripts", "unlink-vault.sh")
UNINSTALL = os.path.join(HERE, "..", "scripts", "uninstall.sh")


def call(reg, *argv):
    """Source lib.sh (avec SM_REGISTRY=reg) puis exécute `argv` (func + args). Renvoie le résultat."""
    env = dict(os.environ, SM_REGISTRY=reg)
    return subprocess.run(["bash", "-c", 'source "$1"; shift; "$@"', "_", LIB, *argv],
                          capture_output=True, text=True, env=env)


def slug_of(path):
    return subprocess.run(["bash", "-c", 'source "$1"; sm_slug "$2"', "_", LIB, path],
                          capture_output=True, text=True).stdout.strip()


class RegistryFnTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.reg = os.path.join(self._t.name, "registry.json")

    def tearDown(self):
        self._t.cleanup()

    def _reg(self, projets):
        with open(self.reg, "w") as f:
            json.dump({"projets": projets}, f)

    def test_symlink_for_slug(self):
        self._reg([{"slug": "-a", "symlink": "/sym/a", "clone": "/cl/a"},
                   {"slug": "-b", "symlink": "/sym/b", "clone": "/cl/b"}])
        self.assertEqual(call(self.reg, "sm_symlink_for_slug", "-b").stdout.strip(), "/sym/b")

    def test_symlink_unknown_slug_empty(self):
        self._reg([{"slug": "-a", "symlink": "/sym/a"}])
        self.assertEqual(call(self.reg, "sm_symlink_for_slug", "-zzz").stdout.strip(), "")

    def test_registry_slugs_lists_all(self):
        self._reg([{"slug": "-a"}, {"slug": "-b"}])
        self.assertEqual(sorted(call(self.reg, "sm_registry_slugs").stdout.split()), ["-a", "-b"])

    def test_unregister_removes_one_keeps_other(self):
        self._reg([{"slug": "-a"}, {"slug": "-b"}])
        call(self.reg, "sm_unregister", "-a")
        with open(self.reg) as f:
            self.assertEqual([p["slug"] for p in json.load(f)["projets"]], ["-b"])

    def test_unregister_idempotent(self):
        self._reg([{"slug": "-b"}])
        call(self.reg, "sm_unregister", "-a")
        call(self.reg, "sm_unregister", "-a")
        with open(self.reg) as f:
            self.assertEqual([p["slug"] for p in json.load(f)["projets"]], ["-b"])

    def test_no_registry_no_error(self):
        missing = os.path.join(self._t.name, "none.json")
        r = call(missing, "sm_registry_slugs")
        self.assertEqual(r.stdout.strip(), "")
        call(missing, "sm_unregister", "-a")   # ne doit pas planter


if __name__ == "__main__":
    unittest.main()
