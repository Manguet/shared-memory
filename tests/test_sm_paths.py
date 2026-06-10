import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "sm_paths", os.path.join(HERE, "..", "scripts", "sm_paths.py"))
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


class SlugTest(unittest.TestCase):
    def test_slug_matches_libsh_rule(self):
        self.assertEqual(P.slug("/var/www/newnegocian-workspace"),
                         "-var-www-newnegocian-workspace")


class RegistryTest(unittest.TestCase):
    def test_vault_clone_for_slug_found(self):
        with tempfile.TemporaryDirectory() as d:
            reg = os.path.join(d, "registry.json")
            with open(reg, "w", encoding="utf-8") as f:
                json.dump({"projets": [{"slug": "-p", "clone": "/clones/p"}]}, f)
            self.assertEqual(P.vault_clone_for_slug("-p", registry=reg), "/clones/p")

    def test_vault_clone_for_slug_absent_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            reg = os.path.join(d, "registry.json")
            with open(reg, "w", encoding="utf-8") as f:
                json.dump({"projets": []}, f)
            self.assertIsNone(P.vault_clone_for_slug("-x", registry=reg))

    def test_missing_registry_returns_none(self):
        self.assertIsNone(P.vault_clone_for_slug("-p", registry="/no/such/file.json"))


class StorePathTest(unittest.TestCase):
    def test_store_path_under_shared_memory(self):
        sp = P.store_path_for_slug("-p")
        self.assertTrue(sp.endswith(os.path.join(".shared-memory", "embeddings", "-p", "index.json")))


if __name__ == "__main__":
    unittest.main()
