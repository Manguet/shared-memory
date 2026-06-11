import datetime
import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "digest", os.path.join(HERE, "..", "scripts", "digest.py")
)
dg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dg)

TODAY = datetime.date(2026, 6, 11)
FRESH = "2026-06-01"          # 10 j -> frais
OLD = "2026-01-01"           # ~161 j -> périmé


def fact_md(name, desc, type_="project", reviewed=FRESH):
    return ("---\nname: %s\ndescription: %s\nmetadata:\n  type: %s\n  reviewed: %s\n---\ncorps\n"
            % (name, desc, type_, reviewed))


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class BuildDigestTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_vault_returns_empty(self):
        self.assertEqual(dg.build_digest(self.vault, today=TODAY), "")

    def test_lists_descriptions_grouped_by_domain(self):
        write(os.path.join(self.vault, "mailing", "relance.md"),
              fact_md("relance", "Relancer après 3 jours sans réponse"))
        write(os.path.join(self.vault, "facturation", "tva.md"),
              fact_md("tva", "TVA à 20% sur les prestations"))
        out = dg.build_digest(self.vault, today=TODAY)
        self.assertIn("Relancer après 3 jours sans réponse", out)
        self.assertIn("TVA à 20% sur les prestations", out)
        self.assertIn("mailing", out)
        self.assertIn("facturation", out)
        # En-tête avec le compte total.
        self.assertIn("2 faits", out)

    def test_stale_fact_marked_fresh_not(self):
        write(os.path.join(self.vault, "mailing", "vieux.md"),
              fact_md("vieux", "Fait pas revu depuis longtemps", reviewed=OLD))
        write(os.path.join(self.vault, "mailing", "neuf.md"),
              fact_md("neuf", "Fait revu hier", reviewed=FRESH))
        out = dg.build_digest(self.vault, today=TODAY)
        # La ligne du fait périmé porte un ⚠, celle du frais non.
        vieux_line = next(l for l in out.splitlines() if "Fait pas revu" in l)
        neuf_line = next(l for l in out.splitlines() if "Fait revu hier" in l)
        self.assertIn("⚠", vieux_line)
        self.assertNotIn("⚠", neuf_line)

    def test_missing_reviewed_is_stale(self):
        write(os.path.join(self.vault, "mailing", "sansdate.md"),
              "---\nname: sansdate\ndescription: Aucune date de revue\nmetadata:\n  type: project\n---\nx\n")
        out = dg.build_digest(self.vault, today=TODAY)
        line = next(l for l in out.splitlines() if "Aucune date de revue" in l)
        self.assertIn("⚠", line)

    def test_over_budget_degraded(self):
        for i in range(5):
            write(os.path.join(self.vault, "mailing", "f%d.md" % i),
                  fact_md("f%d" % i, "Description unique numero %d" % i))
        out = dg.build_digest(self.vault, max_lines=3, today=TODAY)
        # Dégradé : compte + domaines + renvoi recherche, PAS toutes les descriptions.
        self.assertIn("digest complet trop volumineux", out)
        self.assertIn("search_memory", out)
        self.assertIn("mailing", out)
        self.assertNotIn("Description unique numero 0", out)

    def test_includes_personal_facts(self):
        write(os.path.join(self.vault, "feedback_style.md"),
              fact_md("style", "Toujours répondre en français", type_="feedback"))
        out = dg.build_digest(self.vault, today=TODAY)
        self.assertIn("Toujours répondre en français", out)

    def test_includes_patterns_section_from_memory(self):
        write(os.path.join(self.vault, "mailing", "a.md"), fact_md("a", "un fait quelconque"))
        write(os.path.join(self.vault, "MEMORY.md"),
              "# Carte\n\n## Domaines\n- mailing\n\n## Patterns & Conventions\n- Toujours dater les faits\n")
        out = dg.build_digest(self.vault, today=TODAY)
        self.assertIn("Patterns & Conventions", out)
        self.assertIn("Toujours dater les faits", out)


if __name__ == "__main__":
    unittest.main()
