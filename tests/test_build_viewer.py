import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "build_viewer", os.path.join(HERE, "..", "scripts", "build-viewer.py")
)
bv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bv)


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class CollectFactsBaselineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_flat_fact_is_collected(self):
        write(os.path.join(self.vault, "regle.md"),
              "---\nname: regle\ndescription: une regle\nmetadata:\n  type: project\n---\ncorps du fait")
        facts, index = bv.collect_facts(self.vault)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["name"], "regle")
        self.assertEqual(facts[0]["description"], "une regle")
        self.assertEqual(facts[0]["type"], "project")
        self.assertEqual(facts[0]["body"], "corps du fait")

    def test_memory_md_is_index_not_a_fact(self):
        write(os.path.join(self.vault, "MEMORY.md"), "# Carte\n- mailing")
        write(os.path.join(self.vault, "regle.md"), "---\nname: regle\n---\nx")
        facts, index = bv.collect_facts(self.vault)
        self.assertEqual([f["name"] for f in facts], ["regle"])
        self.assertIn("Carte", index)


class DomainTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_fact_in_subfolder_gets_domain(self):
        write(os.path.join(self.vault, "mailing", "audit.md"),
              "---\nname: audit\nmetadata:\n  type: project\n---\ncorps")
        write(os.path.join(self.vault, "ui", "ux.md"),
              "---\nname: ux\nmetadata:\n  type: project\n---\ncorps")
        facts, _ = bv.collect_facts(self.vault)
        by_name = {f["name"]: f for f in facts}
        self.assertEqual(by_name["audit"]["domain"], "mailing")
        self.assertEqual(by_name["ux"]["domain"], "ui")
        self.assertEqual(by_name["audit"]["file"], os.path.join("mailing", "audit.md"))

    def test_root_fact_domain_is_general(self):
        write(os.path.join(self.vault, "feedback_no_commit.md"),
              "---\nname: fb\ntype: feedback\n---\nx")
        facts, _ = bv.collect_facts(self.vault)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["domain"], "général")
        self.assertEqual(facts[0]["type"], "feedback")

    def test_index_subfolder_is_ignored(self):
        write(os.path.join(self.vault, "index", "mailing.md"), "# sous-index mailing")
        write(os.path.join(self.vault, "mailing", "audit.md"), "---\nname: audit\n---\nx")
        facts, _ = bv.collect_facts(self.vault)
        self.assertEqual([f["name"] for f in facts], ["audit"])

    def test_memory_md_index_in_mixed_mode(self):
        write(os.path.join(self.vault, "MEMORY.md"), "# Carte\n- mailing")
        write(os.path.join(self.vault, "mailing", "audit.md"), "---\nname: audit\n---\nx")
        facts, index = bv.collect_facts(self.vault)
        self.assertIn("Carte", index)
        self.assertEqual([f["name"] for f in facts], ["audit"])


class PathTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_path_is_folder_segments(self):
        write(os.path.join(self.vault, "mailing", "transactionnel", "relances.md"),
              "---\nname: relances\nmetadata:\n  type: project\n---\nx")
        facts, _ = bv.collect_facts(self.vault)
        f = facts[0]
        self.assertEqual(f["path"], ["mailing", "transactionnel"])
        self.assertEqual(f["domain"], "mailing")

    def test_root_fact_path_empty(self):
        write(os.path.join(self.vault, "note.md"), "---\nname: note\n---\nx")
        facts, _ = bv.collect_facts(self.vault)
        self.assertEqual(facts[0]["path"], [])
        self.assertEqual(facts[0]["domain"], "général")

    def test_metadata_only_omits_body(self):
        write(os.path.join(self.vault, "mailing", "audit.md"),
              "---\nname: audit\nmetadata:\n  type: project\n---\nle corps")
        facts, _ = bv.collect_facts(self.vault, include_body=False)
        self.assertNotIn("body", facts[0])
        self.assertEqual(facts[0]["name"], "audit")
        self.assertEqual(facts[0]["path"], ["mailing"])

    def test_default_includes_body(self):
        write(os.path.join(self.vault, "mailing", "audit.md"),
              "---\nname: audit\n---\nle corps")
        facts, _ = bv.collect_facts(self.vault)
        self.assertEqual(facts[0]["body"], "le corps")


class ReviewedFieldTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_reviewed_exposed_present_and_empty(self):
        write(os.path.join(self.vault, "mailing", "a.md"),
              "---\nname: a\ndescription: d\nmetadata:\n  type: project\n  reviewed: 2026-06-11\n---\nx")
        write(os.path.join(self.vault, "mailing", "b.md"),
              "---\nname: b\ndescription: d\nmetadata:\n  type: project\n---\ny")
        facts, _ = bv.collect_facts(self.vault, include_body=False)
        by = {f["name"]: f for f in facts}
        self.assertEqual(by["a"]["reviewed"], "2026-06-11")
        self.assertEqual(by["b"]["reviewed"], "")


class CollectFactsLocalTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_local_true_is_carried(self):
        write(os.path.join(self.vault, "mailing", "x.md"),
              "---\nname: x\ndescription: un fait local\nmetadata:\n  type: project\n  local: true\n---\nc")
        facts, _ = bv.collect_facts(self.vault)
        self.assertTrue(facts[0]["local"])

    def test_absent_flag_is_false(self):
        write(os.path.join(self.vault, "mailing", "y.md"),
              "---\nname: y\ndescription: un fait normal\nmetadata:\n  type: project\n---\nc")
        facts, _ = bv.collect_facts(self.vault)
        self.assertFalse(facts[0]["local"])

    def test_local_false_is_false(self):
        write(os.path.join(self.vault, "mailing", "z.md"),
              "---\nname: z\ndescription: explicitement partageable\nmetadata:\n  type: project\n  local: false\n---\nc")
        facts, _ = bv.collect_facts(self.vault)
        self.assertFalse(facts[0]["local"])


if __name__ == "__main__":
    unittest.main()
