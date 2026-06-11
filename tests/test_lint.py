import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "lint", os.path.join(HERE, "..", "scripts", "lint.py")
)
lint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lint)


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


CLEAN = ("---\nname: relance-j3\n"
         "description: Relancer les paniers abandonnés après 72 heures\n"
         "metadata:\n  type: project\n  reviewed: 2026-06-01\n---\nCorps du fait.\n")


def rules_for(findings, rel=None):
    return {f["rule"] for f in findings if rel is None or f["file"] == rel}


class LintDetectionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_fact_no_findings(self):
        write(os.path.join(self.vault, "mailing", "relance-j3.md"), CLEAN)
        self.assertEqual(lint.lint_vault(self.vault), [])

    def test_frontmatter_invalid(self):
        write(os.path.join(self.vault, "mailing", "x.md"), "pas de frontmatter ici\n")
        self.assertIn("frontmatter_invalid", rules_for(lint.lint_vault(self.vault)))

    def test_missing_name_and_description(self):
        write(os.path.join(self.vault, "mailing", "x.md"),
              "---\ndescription:\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nc\n")
        rules = rules_for(lint.lint_vault(self.vault))
        self.assertIn("missing_name", rules)
        self.assertIn("missing_description", rules)

    def test_short_description(self):
        write(os.path.join(self.vault, "mailing", "x.md"),
              "---\nname: x\ndescription: trop court\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nc\n")
        self.assertIn("short_description", rules_for(lint.lint_vault(self.vault)))

    def test_missing_and_invalid_type(self):
        write(os.path.join(self.vault, "a.md"),
              "---\nname: a-fact\ndescription: une description assez longue pour passer\nmetadata:\n  reviewed: 2026-06-01\n---\nc\n")
        write(os.path.join(self.vault, "b.md"),
              "---\nname: b-fact\ndescription: une description assez longue pour passer\nmetadata:\n  type: bogus\n  reviewed: 2026-06-01\n---\nc\n")
        findings = lint.lint_vault(self.vault)
        self.assertIn("missing_type", rules_for(findings, "a.md"))
        self.assertIn("invalid_type", rules_for(findings, "b.md"))

    def test_flat_frontmatter_detected_fixable(self):
        write(os.path.join(self.vault, "mailing", "x.md"),
              "---\nname: x-fact\ndescription: une description assez longue pour passer\ntype: project\nreviewed: 2026-06-01\n---\nc\n")
        findings = lint.lint_vault(self.vault)
        flat = [f for f in findings if f["rule"] == "flat_frontmatter"]
        self.assertEqual(len(flat), 1)
        self.assertTrue(flat[0]["fixable"])
        self.assertEqual(flat[0]["severity"], "warn")
        self.assertNotIn("missing_type", rules_for(findings))

    def test_reviewed_missing_and_malformed(self):
        write(os.path.join(self.vault, "a.md"),
              "---\nname: a-fact\ndescription: une description assez longue pour passer\nmetadata:\n  type: project\n---\nc\n")
        write(os.path.join(self.vault, "b.md"),
              "---\nname: b-fact\ndescription: une description assez longue pour passer\nmetadata:\n  type: project\n  reviewed: 01/06/2026\n---\nc\n")
        findings = lint.lint_vault(self.vault)
        self.assertIn("reviewed_missing", rules_for(findings, "a.md"))
        self.assertIn("reviewed_malformed", rules_for(findings, "b.md"))

    def test_name_not_slug(self):
        write(os.path.join(self.vault, "x.md"),
              "---\nname: Pas un slug\ndescription: une description assez longue pour passer\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nc\n")
        self.assertIn("name_not_slug", rules_for(lint.lint_vault(self.vault)))

    def test_broken_and_valid_wikilink(self):
        write(os.path.join(self.vault, "alpha.md"),
              "---\nname: alpha\ndescription: une description assez longue pour passer\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nvoir [[beta]] et [[alpha]]\n")
        findings = lint.lint_vault(self.vault)
        broken = [f for f in findings if f["rule"] == "broken_wikilink"]
        self.assertEqual(len(broken), 1)
        self.assertIn("beta", broken[0]["message"])

    def test_duplicate_name(self):
        write(os.path.join(self.vault, "mailing", "a.md"), CLEAN)
        write(os.path.join(self.vault, "facturation", "b.md"), CLEAN)
        dups = [f for f in lint.lint_vault(self.vault) if f["rule"] == "duplicate_name"]
        self.assertEqual(len(dups), 2)

    def test_personal_misplaced_vs_root(self):
        write(os.path.join(self.vault, "ui", "perso.md"),
              "---\nname: perso\ndescription: une description assez longue pour passer\nmetadata:\n  type: feedback\n  reviewed: 2026-06-01\n---\nc\n")
        write(os.path.join(self.vault, "feedback_ok.md"),
              "---\nname: ok\ndescription: une description assez longue pour passer\nmetadata:\n  type: feedback\n  reviewed: 2026-06-01\n---\nc\n")
        findings = lint.lint_vault(self.vault)
        self.assertIn("personal_misplaced", rules_for(findings, os.path.join("ui", "perso.md")))
        self.assertNotIn("personal_misplaced", rules_for(findings, "feedback_ok.md"))

    def test_feedback_named_file_in_subdir_is_misplaced(self):
        # un fichier feedback_*.md dans un domaine est perso (convention) -> hors racine -> signalé,
        # même si son type est project
        write(os.path.join(self.vault, "mailing", "feedback_bad.md"),
              "---\nname: bad\ndescription: une description assez longue pour passer le seuil\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nc\n")
        rules = rules_for(lint.lint_vault(self.vault), os.path.join("mailing", "feedback_bad.md"))
        self.assertIn("personal_misplaced", rules)

    def test_format_report_groups_by_severity(self):
        write(os.path.join(self.vault, "mailing", "x.md"),
              "---\nname: x\ndescription:\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nc\n")
        report = lint.format_report(lint.lint_vault(self.vault))
        self.assertIn("Erreurs", report)
        self.assertIn("erreur", report.lower())

    def test_format_report_empty(self):
        self.assertIn("Aucun problème", lint.format_report([]))


FLAT = ("---\nname: vieux-fait\n"
        "description: Un fait au format hérité à plat sans bloc metadata\n"
        "type: project\nreviewed: 2026-06-01\n---\nCorps hérité.\n")


class LintFixTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_apply_fixes_converts_flat_to_nested(self):
        p = os.path.join(self.vault, "mailing", "x.md")
        write(p, FLAT)
        n = lint.apply_fixes(self.vault, lint.lint_vault(self.vault))
        self.assertEqual(n, 1)
        out = open(p, encoding="utf-8").read()
        self.assertIn("metadata:", out)
        self.assertIn("  type: project", out)
        self.assertIn("  reviewed: 2026-06-01", out)
        self.assertNotIn("\ntype: project", out)
        self.assertNotIn("\nreviewed: 2026-06-01", out)
        self.assertIn("name: vieux-fait", out)
        self.assertIn("Un fait au format hérité à plat sans bloc metadata", out)
        self.assertIn("Corps hérité.", out)

    def test_fix_is_idempotent(self):
        p = os.path.join(self.vault, "mailing", "x.md")
        write(p, FLAT)
        lint.apply_fixes(self.vault, lint.lint_vault(self.vault))
        self.assertEqual(lint.lint_vault(self.vault), [])

    def test_apply_fixes_only_touches_fixable(self):
        p = os.path.join(self.vault, "x.md")
        content = ("---\nname: Pas un slug\n"
                   "description: une description assez longue pour passer le seuil\n"
                   "metadata:\n  type: project\n  reviewed: 2026-06-01\n---\nc\n")
        write(p, content)
        before = open(p, encoding="utf-8").read()
        n = lint.apply_fixes(self.vault, lint.lint_vault(self.vault))
        self.assertEqual(n, 0)
        self.assertEqual(open(p, encoding="utf-8").read(), before)


if __name__ == "__main__":
    unittest.main()
