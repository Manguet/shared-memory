import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
VERIFY_PY = os.path.join(HERE, "..", "scripts", "verify-scale.py")

# Charge verify-scale.py comme module pour exercer sa logique réelle (gen + reshard +
# index_files + l'invariant « tout index ≤ seuil ») sur un petit vault rapide.
_SPEC = importlib.util.spec_from_file_location("verify_scale", VERIFY_PY)
vs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(vs)


def _over_threshold(vault, files, max_entries):
    """Reproduit l'invariant clé de verify-scale.main : index avec > max_entries entrées."""
    over = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            entries = [l for l in fh.read().splitlines() if l.startswith("- ")]
        if len(entries) > max_entries:
            over.append((os.path.relpath(f, vault), len(entries)))
    return over


def _max_depth(vault, files):
    idx = os.path.join(vault, "index")
    depth = 0
    for f in files:
        depth = max(depth, len(os.path.relpath(f, idx).split(os.sep)))
    return depth


class GuardTest(unittest.TestCase):
    def test_refuses_dest_equals_source(self):
        with tempfile.TemporaryDirectory() as d:
            marker = os.path.join(d, "keep.txt")
            with open(marker, "w") as f:
                f.write("x")
            r = subprocess.run([sys.executable, VERIFY_PY, d, "--source", d],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertTrue(os.path.exists(marker))   # rien n'a été détruit


class VerifyLogicTest(unittest.TestCase):
    """Exerce la logique de vérification sur un PETIT vault synthétique (rapide, déterministe) :
    pas de génération à 9000 faits ; petit N + petit seuil pour forcer la récursion."""

    MAX = 3
    DOMAINS = 2
    NFACTS = 30   # 30 > 3 -> sharding récursif -> profondeur ≥ 3

    def _build(self, dest):
        # source=None : aucune dépendance à un vault hôte ; seed fixe = déterministe.
        counts = vs.gen.generate(dest, source=None, domains=self.DOMAINS,
                                 fmin=self.NFACTS, fmax=self.NFACTS, seed=0)
        rcounts = vs.reshard.reshard(dest, max_entries=self.MAX)
        return counts, rcounts

    def test_resharded_small_vault_satisfies_invariants(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "vault")
            _gen, rcounts = self._build(dest)
            files = vs.index_files(dest)
            # 1. Aucun index au-dessus du seuil (invariant principal).
            self.assertEqual(_over_threshold(dest, files, self.MAX), [])
            # 2. Récursion réelle (le script échoue si profondeur < 3).
            self.assertGreaterEqual(_max_depth(dest, files), 3)
            # 3. Aucun fait perdu : total resharded = total généré.
            self.assertEqual(sum(rcounts.values()), self.DOMAINS * self.NFACTS)
            # 4. MEMORY.md présent (reshard la crée si absente).
            self.assertTrue(os.path.isfile(os.path.join(dest, "MEMORY.md")))

    def test_no_fact_lost_after_reshard(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "vault")
            self._build(dest)
            # Compte tous les faits .md hors MEMORY.md et hors index/**.
            n = 0
            for root, _dirs, fnames in os.walk(dest):
                rel = os.path.relpath(root, dest)
                if rel.split(os.sep)[0] == "index":
                    continue
                for fn in fnames:
                    if fn.endswith(".md") and fn != "MEMORY.md":
                        n += 1
            self.assertEqual(n, self.DOMAINS * self.NFACTS)

    def test_over_threshold_invariant_detects_violation(self):
        # Vérifie que le contrôle d'invariant attrape bien une violation : on injecte
        # une entrée de trop dans un index feuille -> _over_threshold doit le signaler.
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "vault")
            self._build(dest)
            files = vs.index_files(dest)
            self.assertEqual(_over_threshold(dest, files, self.MAX), [])   # sain au départ
            leaves = []
            for f in files:
                with open(f, encoding="utf-8") as fh:
                    if any(l.lstrip().startswith("- `") for l in fh.read().splitlines()):
                        leaves.append(f)
            victim = leaves[0]
            with open(victim, "a", encoding="utf-8") as fh:
                for k in range(self.MAX + 2):
                    fh.write("- `extra-%d` — bourrage · project -> x.md\n" % k)
            over = _over_threshold(dest, vs.index_files(dest), self.MAX)
            self.assertTrue(over)   # la violation est détectée
            self.assertIn(os.path.relpath(victim, dest), [o[0] for o in over])


if __name__ == "__main__":
    unittest.main()
