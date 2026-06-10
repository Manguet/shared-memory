# Plan — `reshard.py` : redécoupage automatique + vérification à l'échelle (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer `scripts/reshard.py` qui maintient l'invariant « ≤ N faits directs et ≤ N sous-dossiers par dossier » (split récursif en sous-domaines + régénération de tous les index), le prouver à l'échelle sur une copie de `negocian-memory` augmentée de 30 domaines synthétiques, et câbler le tout dans la convention et les skills.

**Architecture :** `reshard.py` lit les faits via `collect_facts` (build-viewer.py), calcule un arbre équilibré déterministe (`split_tree`), déplace les faits sur disque et reconstruit `index/**` + `MEMORY.md`. Pur fichiers, zéro dépendance, idempotent. Un générateur synthétique (`gen-synth-vault.py`) et un script de vérif (`verify-scale.py`) servent le test à l'échelle. Tests `unittest` (pattern `importlib.util` déjà en place).

**Tech Stack :** Python 3 stdlib (os, shutil, math, importlib, argparse, random). Tests `unittest`.

**Référence design :** `docs/superpowers/specs/2026-06-10-reshard-scale-design.md`.

**Sûreté :** le vrai vault `negocian-memory` (clone `~/.shared-memory/vaults/negocian-memory`) n'est **jamais** modifié — seulement **lu** comme source de copie. Tout le test se fait dans un dossier jetable (`/tmp/sm-scale-vault`).

---

## File Structure

| Fichier | Responsabilité | Action |
|---|---|---|
| `scripts/reshard.py` | Helpers purs (`balanced_chunks`, `split_tree`) + restructuration/régénération (`reshard`) + CLI. | Créer |
| `scripts/gen-synth-vault.py` | Copie un vault source (sans `.git`) + génère N domaines × M faits synthétiques. | Créer |
| `scripts/verify-scale.py` | Génère la copie + reshard `--max-entries 25` + **assert** index ≤ N & récursion présente. | Créer |
| `tests/test_reshard.py` | unittest : helpers, split 1 niveau, récursion, conservation, idempotence, MEMORY, racine intacte. | Créer |
| `tests/test_gen_synth.py` | unittest : copie des faits source, N domaines, comptes, seed reproductible. | Créer |
| `docs/domain-convention.md` | Documente reshard comme moteur du redécoupage. | Modifier |
| `skills/memory-import/SKILL.md` | Régénère les index via reshard (split proposé si > seuil). | Modifier |
| `skills/memory-promote/SKILL.md` | Lance reshard avant commit ; `git add` des faits déplacés. | Modifier |

**Convention de format (rappel, à respecter à l'identique) :**
- ligne de fait : `` - `<nom>` — <description> · <type> → `<chemin>/<fait>.md` ``
- ligne de sous-domaine : `- <label> (<n> faits) → index/<chemin>/<label>.md`

---

## Task 1 : `reshard.py` — helpers purs `balanced_chunks` + `split_tree`

**Files:**
- Create: `scripts/reshard.py`
- Test: `tests/test_reshard.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `tests/test_reshard.py` :

```python
import importlib.util
import os
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "reshard", os.path.join(HERE, "..", "scripts", "reshard.py"))
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


class HelpersTest(unittest.TestCase):
    def test_balanced_chunks_even_and_remainder(self):
        self.assertEqual(R.balanced_chunks([0, 1, 2, 3, 4], 2), [[0, 1, 2], [3, 4]])
        self.assertEqual(R.balanced_chunks(list(range(10)), 3),
                         [[0, 1, 2, 3], [4, 5, 6], [7, 8, 9]])

    def test_balanced_chunks_preserves_all_items(self):
        chunks = R.balanced_chunks(list(range(23)), 4)
        self.assertEqual([x for c in chunks for x in c], list(range(23)))
        self.assertEqual(len(chunks), 4)

    def test_split_tree_leaf_when_small(self):
        self.assertEqual(R.split_tree([1, 2], 3), {"leaf": [1, 2]})

    def test_split_tree_one_level(self):
        t = R.split_tree(list(range(4)), 3)
        self.assertIn("children", t)
        self.assertTrue(all("leaf" in c for c in t["children"]))
        self.assertTrue(all(len(c["leaf"]) <= 3 for c in t["children"]))

    def test_split_tree_recurses_when_needed(self):
        t = R.split_tree(list(range(10)), 3)   # 10 > 3*3 => 2 niveaux
        self.assertIn("children", t)
        self.assertTrue(any("children" in c for c in t["children"]))
        self.assertLessEqual(len(t["children"]), 3)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_reshard -v`
Expected : FAIL — `scripts/reshard.py` absent (`FileNotFoundError` au chargement).

- [ ] **Step 3 : Créer `scripts/reshard.py` (helpers seulement)**

```python
#!/usr/bin/env python3
"""Redécoupage automatique d'un vault en sous-domaines (invariant ≤ N par dossier).

Restructure les faits sur disque puis régénère tout `index/**` + `MEMORY.md`.
Réutilise collect_facts/parse_md de build-viewer.py. Pur fichiers, zéro dépendance.
"""
import argparse
import importlib.util
import math
import os
import shutil

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "build_viewer", os.path.join(_HERE, "build-viewer.py"))
bv = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bv)

DEFAULT_MAX = 150


def balanced_chunks(items, k):
    """Découpe `items` en k tranches contiguës de tailles quasi égales (préserve l'ordre)."""
    base, extra = divmod(len(items), k)
    chunks, i = [], 0
    for j in range(k):
        size = base + (1 if j < extra else 0)
        chunks.append(items[i:i + size])
        i += size
    return chunks


def split_tree(items, n):
    """Arbre équilibré : feuille si ≤ n items, sinon ≤ n enfants, récursif sans plafond.
    Renvoie {'leaf': [items]} ou {'children': [sous-arbres]}."""
    if len(items) <= n:
        return {"leaf": list(items)}
    k = min(n, math.ceil(len(items) / n))
    return {"children": [split_tree(c, n) for c in balanced_chunks(items, k)]}
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_reshard -v`
Expected : PASS (5 tests).

- [ ] **Step 5 : Commit**

```bash
git add scripts/reshard.py tests/test_reshard.py
git commit -m "feat(reshard): helpers purs balanced_chunks + split_tree

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 : `reshard.py` — restructuration + régénération des index (cœur)

**Files:**
- Modify: `scripts/reshard.py`
- Test: `tests/test_reshard.py`

- [ ] **Step 1 : Ajouter les tests qui échouent**

Ajouter dans `tests/test_reshard.py`, avant `if __name__` — d'abord un helper d'écriture de fait, puis les cas :

```python
import tempfile


def write_fact(vault, relpath, name, desc="desc discriminante", body="corps"):
    p = os.path.join(vault, relpath)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("---\nname: %s\ndescription: %s\nmetadata:\n  type: project\n---\n%s"
                % (name, desc, body))


def md_files_under(d):
    out = []
    for root, _dirs, files in os.walk(d):
        for fn in files:
            if fn.endswith(".md"):
                out.append(os.path.join(root, fn))
    return out


class ReshardCoreTest(unittest.TestCase):
    def test_small_domain_stays_flat(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(3):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=5)
            # pas de sous-dossier sous mailing : tous les faits à plat
            subdirs = [e for e in os.listdir(os.path.join(v, "mailing"))
                       if os.path.isdir(os.path.join(v, "mailing", e))]
            self.assertEqual(subdirs, [])
            with open(os.path.join(v, "index", "mailing.md"), encoding="utf-8") as f:
                lines = [l for l in f.read().splitlines() if l.startswith("- ")]
            self.assertEqual(len(lines), 3)

    def test_large_domain_splits_into_subdomains(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(4):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=2)
            mailing = os.path.join(v, "mailing")
            subdirs = sorted(e for e in os.listdir(mailing)
                             if os.path.isdir(os.path.join(mailing, e)))
            self.assertTrue(len(subdirs) >= 2)             # scindé
            # aucun .md directement sous mailing/ (tout est descendu en sous-domaine)
            direct = [e for e in os.listdir(mailing) if e.endswith(".md")]
            self.assertEqual(direct, [])
            # l'index parent = pointeurs de sous-domaine
            with open(os.path.join(v, "index", "mailing.md"), encoding="utf-8") as f:
                txt = f.read()
            self.assertIn("faits) → index/mailing/", txt)

    def test_no_fact_lost(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(7):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=2)
            self.assertEqual(len(md_files_under(os.path.join(v, "mailing"))), 7)

    def test_root_facts_untouched(self):
        with tempfile.TemporaryDirectory() as v:
            write_fact(v, "feedback_x.md", "feedback-x")     # fait racine (perso)
            for i in range(3):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=2)
            self.assertTrue(os.path.isfile(os.path.join(v, "feedback_x.md")))
            # le fait racine n'apparaît dans aucun index
            for f in md_files_under(os.path.join(v, "index")):
                self.assertNotIn("feedback-x", open(f, encoding="utf-8").read())

    def test_memory_lists_domains(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(3):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            write_fact(v, "ui/a.md", "a")
            R.reshard(v, max_entries=5)
            mem = open(os.path.join(v, "MEMORY.md"), encoding="utf-8").read()
            self.assertIn("- mailing (3 faits) → index/mailing.md", mem)
            self.assertIn("- ui (1 faits) → index/ui.md", mem)
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_reshard.ReshardCoreTest -v`
Expected : FAIL — `module 'reshard' has no attribute 'reshard'`.

- [ ] **Step 3 : Implémenter le cœur**

Ajouter à `scripts/reshard.py` (après `split_tree`) :

```python
def _read_raw(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _domain_facts(vault):
    """Groupe les faits par domaine de 1er niveau (path non vide). Faits racine ignorés.
    Chaque fait porte 'raw' (contenu fichier), trié par name."""
    facts, _ = bv.collect_facts(vault, include_body=False)
    by_domain = {}
    for fa in facts:
        if not fa["path"]:                  # fait racine (perso/général) -> jamais shardé
            continue
        fa = dict(fa, raw=_read_raw(os.path.join(vault, fa["file"])))
        by_domain.setdefault(fa["path"][0], []).append(fa)
    for d in by_domain:
        by_domain[d].sort(key=lambda f: f["name"])
    return by_domain


def _count_leaf_facts(node):
    if "leaf" in node:
        return len(node["leaf"])
    return sum(_count_leaf_facts(c) for c in node["children"])


def _materialize(node, segments):
    """Renvoie (placements, indexes) pour un nœud à `segments` (ex. ['mailing','part-01']).
    placements: (new_relpath, raw). indexes: (index_seg, kind, entries)."""
    seg = "/".join(segments)
    placements, indexes = [], []
    if "leaf" in node:
        entries = []
        for fa in node["leaf"]:
            rel = seg + "/" + fa["name"] + ".md"
            placements.append((rel, fa["raw"]))
            entries.append(("fact", fa["name"], fa["description"], fa["type"], rel))
        indexes.append((seg, "leaf", entries))
    else:
        children = node["children"]
        w = max(2, len(str(len(children))))
        entries = []
        for i, child in enumerate(children):
            label = "part-%0*d" % (w, i + 1)
            child_seg = segments + [label]
            sub_p, sub_i = _materialize(child, child_seg)
            placements.extend(sub_p)
            indexes.extend(sub_i)
            entries.append(("node", label, _count_leaf_facts(child), "/".join(child_seg)))
        indexes.append((seg, "node", entries))
    return placements, indexes


def _write_index(vault, seg, kind, entries):
    path = os.path.join(vault, "index", seg + ".md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = ["# %s" % seg, ""]
    if kind == "leaf":
        for _, name, desc, typ, rel in entries:
            lines.append("- `%s` — %s · %s → `%s`" % (name, desc, typ, rel))
    else:
        for _, label, count, child_seg in entries:
            lines.append("- %s (%d faits) → index/%s.md" % (label, count, child_seg))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _write_memory(vault, domain_counts):
    lines = ["# Mémoire — carte des domaines", "", "## Domaines", ""]
    for domain in sorted(domain_counts):
        lines.append("- %s (%d faits) → index/%s.md" % (domain, domain_counts[domain], domain))
    with open(os.path.join(vault, "MEMORY.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def reshard(vault, max_entries=DEFAULT_MAX):
    """Applique l'invariant ≤ max_entries par dossier ; régénère index/** + MEMORY.md.
    Idempotent. Renvoie {domaine: nb_faits}."""
    by_domain = _domain_facts(vault)
    all_placements, all_indexes, counts = [], [], {}
    for domain, facts in sorted(by_domain.items()):
        names = [f["name"] for f in facts]
        if len(names) != len(set(names)):
            raise ValueError("noms en double dans le domaine %s" % domain)
        tree = split_tree(facts, max_entries)
        placements, indexes = _materialize(tree, [domain])
        all_placements.extend(placements)
        all_indexes.extend(indexes)
        counts[domain] = len(facts)
    # Reconstruction propre : on efface les dossiers de domaines + index/, puis on réécrit.
    for domain in by_domain:
        shutil.rmtree(os.path.join(vault, domain), ignore_errors=True)
    shutil.rmtree(os.path.join(vault, "index"), ignore_errors=True)
    for rel, raw in all_placements:
        dest = os.path.join(vault, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(raw)
    for seg, kind, entries in all_indexes:
        _write_index(vault, seg, kind, entries)
    _write_memory(vault, counts)
    return counts
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_reshard -v`
Expected : PASS (10 tests cumulés).

- [ ] **Step 5 : Commit**

```bash
git add scripts/reshard.py tests/test_reshard.py
git commit -m "feat(reshard): restructuration en sous-domaines + régénération index/MEMORY

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 : `reshard.py` — récursion, conservation des pointeurs, idempotence

**Files:**
- Modify: `tests/test_reshard.py` (vérifs supplémentaires sur le code existant — aucun changement de `reshard.py` attendu)

- [ ] **Step 1 : Ajouter les tests qui échouent (ou passent déjà)**

Ajouter dans `tests/test_reshard.py`, avant `if __name__` :

```python
def index_files_under(vault):
    return md_files_under(os.path.join(vault, "index"))


def index_depth(vault):
    idx = os.path.join(vault, "index")
    return max(len(os.path.relpath(f, idx).split(os.sep)) for f in index_files_under(vault))


def leaf_pointer_targets(vault):
    targets = []
    for f in index_files_under(vault):
        for line in open(f, encoding="utf-8").read().splitlines():
            if line.startswith("- `"):                  # ligne de fait (feuille)
                targets.append(line.split("→")[1].strip().strip("`"))
    return targets


class ReshardRecursionTest(unittest.TestCase):
    def test_two_levels_when_exceeds_n_squared(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(5):                            # 5 > 2*2 => 2 niveaux à n=2
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=2)
            self.assertGreaterEqual(index_depth(v), 3)    # index/mailing/part-xx/part-yy.md
            self.assertEqual(_leaf_count(v), 5)

    def test_each_fact_reachable_by_exactly_one_leaf_pointer(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(7):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=2)
            targets = leaf_pointer_targets(v)
            actual = sorted(os.path.relpath(p, v) for p in md_files_under(os.path.join(v, "mailing")))
            self.assertEqual(sorted(targets), actual)     # bijection pointeurs <-> faits
            self.assertEqual(len(targets), len(set(targets)))

    def test_every_index_within_threshold(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(30):
                write_fact(v, "mailing/f%02d.md" % i, "f%02d" % i)
            R.reshard(v, max_entries=4)
            for f in index_files_under(v):
                entries = [l for l in open(f, encoding="utf-8").read().splitlines()
                           if l.startswith("- ")]
                self.assertLessEqual(len(entries), 4)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(9):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            R.reshard(v, max_entries=2)
            snap1 = {os.path.relpath(f, v): open(f, encoding="utf-8").read()
                     for f in index_files_under(v)}
            R.reshard(v, max_entries=2)
            snap2 = {os.path.relpath(f, v): open(f, encoding="utf-8").read()
                     for f in index_files_under(v)}
            self.assertEqual(snap1, snap2)


def _leaf_count(v):
    return len(md_files_under(os.path.join(v, "mailing")))
```

- [ ] **Step 2 : Lancer, vérifier**

Run : `python3 -m unittest tests.test_reshard.ReshardRecursionTest -v`
Expected : PASS (4 tests) — ces comportements découlent du cœur de la Task 2. Si l'un échoue, corriger `reshard.py` (et non le test) jusqu'au vert.

- [ ] **Step 3 : Lancer la suite reshard complète**

Run : `python3 -m unittest tests.test_reshard -v`
Expected : PASS (14 tests cumulés).

- [ ] **Step 4 : Commit**

```bash
git add tests/test_reshard.py
git commit -m "test(reshard): récursion multi-niveaux, bijection pointeurs, idempotence

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 : `reshard.py` — CLI

**Files:**
- Modify: `scripts/reshard.py`
- Test: `tests/test_reshard.py`

- [ ] **Step 1 : Ajouter le test qui échoue (smoke CLI via subprocess)**

Ajouter dans `tests/test_reshard.py`, avant `if __name__` :

```python
import subprocess
import sys

RESHARD_PY = os.path.join(HERE, "..", "scripts", "reshard.py")


class CliTest(unittest.TestCase):
    def test_cli_reshards_with_max_entries(self):
        with tempfile.TemporaryDirectory() as v:
            for i in range(4):
                write_fact(v, "mailing/f%d.md" % i, "f%d" % i)
            r = subprocess.run([sys.executable, RESHARD_PY, v, "--max-entries", "2"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            mailing = os.path.join(v, "mailing")
            subdirs = [e for e in os.listdir(mailing)
                       if os.path.isdir(os.path.join(mailing, e))]
            self.assertTrue(len(subdirs) >= 2)
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_reshard.CliTest -v`
Expected : FAIL — `reshard.py` n'a pas de `__main__` (returncode ≠ 0 ou aucun split).

- [ ] **Step 3 : Ajouter la CLI à la fin de `scripts/reshard.py`**

```python
def main():
    ap = argparse.ArgumentParser(description="Redécoupe un vault en sous-domaines (≤ N par dossier).")
    ap.add_argument("vault")
    ap.add_argument("--max-entries", type=int, default=DEFAULT_MAX)
    args = ap.parse_args()
    counts = reshard(args.vault, args.max_entries)
    total = sum(counts.values())
    print("reshard: %d domaines, %d faits, seuil %d" % (len(counts), total, args.max_entries))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_reshard -v`
Expected : PASS (15 tests cumulés).

- [ ] **Step 5 : Commit**

```bash
git add scripts/reshard.py tests/test_reshard.py
git commit -m "feat(reshard): CLI (vault + --max-entries)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 : `gen-synth-vault.py` — générateur de vault synthétique

**Files:**
- Create: `scripts/gen-synth-vault.py`
- Test: `tests/test_gen_synth.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `tests/test_gen_synth.py` :

```python
import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "gen_synth", os.path.join(HERE, "..", "scripts", "gen-synth-vault.py"))
G = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G)


def md_count(d):
    n = 0
    for _root, _dirs, files in os.walk(d):
        n += sum(1 for f in files if f.endswith(".md"))
    return n


class GenTest(unittest.TestCase):
    def test_generates_domains_with_fact_counts_in_range(self):
        with tempfile.TemporaryDirectory() as dest:
            counts = G.generate(dest, source=None, domains=3, fmin=5, fmax=8, seed=1)
            self.assertEqual(len(counts), 3)
            for dom, n in counts.items():
                self.assertTrue(5 <= n <= 8)
                self.assertEqual(md_count(os.path.join(dest, dom)), n)

    def test_seed_is_reproducible(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            c1 = G.generate(d1, source=None, domains=4, fmin=5, fmax=20, seed=42)
            c2 = G.generate(d2, source=None, domains=4, fmin=5, fmax=20, seed=42)
            self.assertEqual(c1, c2)

    def test_copies_source_facts(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dest:
            os.makedirs(os.path.join(src, "mailing"))
            with open(os.path.join(src, "mailing", "real.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: real\ndescription: vrai\nmetadata:\n  type: project\n---\nx")
            os.makedirs(os.path.join(src, ".git"))
            with open(os.path.join(src, ".git", "config"), "w") as f:
                f.write("[core]")
            G.generate(dest, source=src, domains=2, fmin=5, fmax=8, seed=1)
            self.assertTrue(os.path.isfile(os.path.join(dest, "mailing", "real.md")))
            self.assertFalse(os.path.exists(os.path.join(dest, ".git")))   # .git exclu


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `python3 -m unittest tests.test_gen_synth -v`
Expected : FAIL — `scripts/gen-synth-vault.py` absent.

- [ ] **Step 3 : Créer `scripts/gen-synth-vault.py`**

```python
#!/usr/bin/env python3
"""Génère un vault synthétique jetable : copie d'un vault source (sans .git) + N domaines factices.

Aide à tester reshard.py à l'échelle. N'écrit pas d'index (reshard les régénère)."""
import argparse
import os
import random
import shutil

FACT_TMPL = ("---\nname: %(name)s\ndescription: %(desc)s\nmetadata:\n  type: project\n---\n"
             "Fait synthétique %(i)d du domaine %(d)d. Remplissage pour le test à l'échelle.\n")


def generate(dest, source=None, domains=30, fmin=120, fmax=500, seed=0):
    """Copie `source` (hors .git) dans `dest` puis ajoute `domains` domaines synthétiques.
    Renvoie {domaine_synth: nb_faits}. Déterministe via `seed`."""
    rng = random.Random(seed)
    if source:
        shutil.copytree(source, dest, ignore=shutil.ignore_patterns(".git"), dirs_exist_ok=True)
    else:
        os.makedirs(dest, exist_ok=True)
    counts = {}
    for d in range(1, domains + 1):
        dom = "synthdom-%02d" % d
        nfacts = rng.randint(fmin, fmax)
        ddir = os.path.join(dest, dom)
        os.makedirs(ddir, exist_ok=True)
        for i in range(nfacts):
            name = "synth-d%02d-f%04d" % (d, i)
            desc = "fait synthétique %d du domaine %d — variante %d" % (i, d, i % 7)
            with open(os.path.join(ddir, name + ".md"), "w", encoding="utf-8") as f:
                f.write(FACT_TMPL % {"name": name, "desc": desc, "i": i, "d": d})
        counts[dom] = nfacts
    return counts


def main():
    ap = argparse.ArgumentParser(description="Génère un vault synthétique pour tester reshard.")
    ap.add_argument("dest")
    ap.add_argument("--source", default=None)
    ap.add_argument("--domains", type=int, default=30)
    ap.add_argument("--min", dest="fmin", type=int, default=120)
    ap.add_argument("--max", dest="fmax", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    counts = generate(args.dest, args.source, args.domains, args.fmin, args.fmax, args.seed)
    print("gen: %d domaines synthétiques, %d faits -> %s"
          % (len(counts), sum(counts.values()), args.dest))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `python3 -m unittest tests.test_gen_synth -v`
Expected : PASS (3 tests).

- [ ] **Step 5 : Commit**

```bash
git add scripts/gen-synth-vault.py tests/test_gen_synth.py
git commit -m "feat(scale): générateur de vault synthétique (copie source + N domaines)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 : `verify-scale.py` + exécution réelle du test à l'échelle

**Files:**
- Create: `scripts/verify-scale.py`

C'est le **livrable de vérification** : générer la copie de `negocian-memory` + 30 domaines synthétiques, reshard à N=25 (force la récursion), et prouver que tout index reste ≤ N.

- [ ] **Step 1 : Créer `scripts/verify-scale.py`**

```python
#!/usr/bin/env python3
"""Vérification à l'échelle de reshard : copie d'un vault source + 30 domaines synthétiques,
reshard à un seuil bas (force la récursion), puis assertions de lisibilité.

Usage: verify-scale.py <dest> [--source <clone>] [--max-entries 25]
Sort 0 si tout index <= seuil et récursion présente, 1 sinon."""
import argparse
import importlib.util
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen = _load("gen_synth", "gen-synth-vault.py")
reshard = _load("reshard", "reshard.py")


def index_files(vault):
    out = []
    for root, _dirs, files in os.walk(os.path.join(vault, "index")):
        for fn in files:
            if fn.endswith(".md"):
                out.append(os.path.join(root, fn))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("--source", default=os.path.expanduser("~/.shared-memory/vaults/negocian-memory"))
    ap.add_argument("--max-entries", type=int, default=25)
    args = ap.parse_args()

    if os.path.exists(args.dest):
        shutil.rmtree(args.dest)
    gcounts = gen.generate(args.dest, source=args.source, domains=30, fmin=120, fmax=500, seed=0)
    rcounts = reshard.reshard(args.dest, max_entries=args.max_entries)

    idx = os.path.join(args.dest, "index")
    files = index_files(args.dest)
    over = []
    maxdepth = 0
    for f in files:
        entries = [l for l in open(f, encoding="utf-8").read().splitlines() if l.startswith("- ")]
        if len(entries) > args.max_entries:
            over.append((os.path.relpath(f, args.dest), len(entries)))
        maxdepth = max(maxdepth, len(os.path.relpath(f, idx).split(os.sep)))

    total_facts = sum(rcounts.values())
    print("Domaines: %d | faits totaux: %d | fichiers d'index: %d | profondeur max: %d | seuil: %d"
          % (len(rcounts), total_facts, len(files), maxdepth, args.max_entries))
    if over:
        print("ÉCHEC — index au-dessus du seuil :", over[:5])
        sys.exit(1)
    if maxdepth < 2:
        print("ÉCHEC — aucune récursion (profondeur < 2)")
        sys.exit(1)
    print("OK — tous les index ≤ %d lignes, récursion présente (profondeur %d)."
          % (args.max_entries, maxdepth))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2 : Exécuter le test à l'échelle réel (copie de negocian-memory)**

Run :
```bash
python3 scripts/verify-scale.py /tmp/sm-scale-vault
```
Expected : une ligne de stats (≈30+ domaines — 30 synthétiques + les domaines réels copiés —, plusieurs milliers de faits), puis `OK — tous les index ≤ 25 lignes, récursion présente (profondeur ≥ 2).` et code de sortie 0. **Le vrai vault n'est pas touché** (seulement lu comme source).

- [ ] **Step 3 : Vérifier visuellement avec le viewer (optionnel mais recommandé)**

Run :
```bash
python3 scripts/build-viewer.py >/dev/null 2>&1 || true   # build-viewer est un module ; on passe par serve
python3 scripts/serve-viewer.py /tmp/sm-scale-vault assets/viewer-template.html 8899 &
echo "Ouvrir http://127.0.0.1:8899 puis Ctrl-C pour arrêter"
```
Expected : l'arbre récursif N-niveaux s'affiche (domaines `synthdom-xx` éclatés en `part-xx`). Arrêter le serveur ensuite (`kill %1`).

- [ ] **Step 4 : Confirmer la non-pollution du vrai vault**

Run :
```bash
git -C ~/.shared-memory/vaults/negocian-memory status --porcelain | wc -l
```
Expected : le **même** nombre de lignes qu'avant (la migration en cours non commitée est intacte ; verify-scale n'a fait que **lire** la source).

- [ ] **Step 5 : Commit**

```bash
git add scripts/verify-scale.py
git commit -m "feat(scale): script de vérification à l'échelle (copie + reshard N=25 + asserts)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7 : Câbler `domain-convention.md`

**Files:**
- Modify: `docs/domain-convention.md`

- [ ] **Step 1 : Compléter la section « Profondeur récursive sans plafond »**

Dans `docs/domain-convention.md`, à la **fin** de la section `## Profondeur récursive sans plafond` (juste avant la section suivante), ajouter :

```markdown
### Moteur du redécoupage : `reshard.py`

Le redécoupage est porté par **`scripts/reshard.py`** (invariant : *aucun dossier ne dépasse
~150 faits directs ni ~150 sous-dossiers*). Il **restructure** les faits sur disque (déplacement
en sous-domaines `part-xx` seulement là où le seuil est franchi, donc **idempotent** et
sans toucher un sous-arbre déjà conforme) puis **régénère tout `index/**` + `MEMORY.md`** au format
compact. Les skills l'appellent au lieu d'écrire l'index à la main :

```bash
python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/reshard.py "<vault>" [--max-entries 150]
```

Les sous-domaines créés portent des labels mécaniques (`part-01`…) ; **un humain peut les renommer**
en libellés signifiants ensuite (reshard ne re-brasse pas un sous-arbre resté sous le seuil).
```

- [ ] **Step 2 : Vérifier**

Run : `grep -n "reshard.py" docs/domain-convention.md`
Expected : au moins une occurrence.

- [ ] **Step 3 : Commit**

```bash
git add docs/domain-convention.md
git commit -m "docs(convention): reshard.py, moteur du redécoupage en sous-domaines

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8 : Câbler `memory-import`

**Files:**
- Modify: `skills/memory-import/SKILL.md`

- [ ] **Step 1 : Remplacer l'étape 6 (mise à jour de l'index à la main) par un appel à reshard**

Dans `skills/memory-import/SKILL.md`, remplacer **tout** le paragraphe de l'étape 6 (celui qui commence par « **Mettre à jour le sous-index** ») par :

```markdown
6. **Régénérer l'index via reshard** (au lieu d'écrire la ligne à la main). Compter d'abord les
   faits du domaine ; s'il **dépasse ~150 faits**, **prévenir l'utilisateur** qu'un découpage en
   sous-domaines (déplacement de faits) va avoir lieu et **demander son accord**. Puis lancer :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/reshard.py "<clone>"
   ```

   reshard reconstruit `index/**` au format compact (description reprise du frontmatter, DRY) et
   crée les domaines à la carte `MEMORY.md`. S'il a créé des sous-domaines `part-xx`, le **signaler**
   (l'utilisateur pourra les renommer). Détails : `${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`.
```

- [ ] **Step 2 : Ajouter la ressource reshard**

Dans la section `## Ressources` de `skills/memory-import/SKILL.md`, ajouter :

```markdown
- **`${CLAUDE_PLUGIN_ROOT}/scripts/reshard.py`** — régénère les index compacts et découpe les
  domaines trop gros en sous-domaines.
```

- [ ] **Step 3 : Vérifier**

Run : `grep -n "reshard.py" skills/memory-import/SKILL.md`
Expected : deux occurrences (procédure + ressources).

- [ ] **Step 4 : Commit**

```bash
git add skills/memory-import/SKILL.md
git commit -m "feat(memory-import): régénère les index via reshard (split proposé si > seuil)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9 : Câbler `memory-promote`

**Files:**
- Modify: `skills/memory-promote/SKILL.md`

- [ ] **Step 1 : Remplacer l'étape 5 (tenue de l'index à la main) par un appel à reshard**

Dans `skills/memory-promote/SKILL.md`, remplacer **tout** le paragraphe de l'étape 5 (« **Tenir l'index hiérarchique à jour** ») par :

```markdown
5. **Régénérer l'index hiérarchique via reshard** (→ `${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`).
   Chaque fait retenu vit dans `<domaine>/<fait>.md`. Lancer :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/reshard.py "<clone>"
   ```

   reshard régénère `index/**` (lignes compactes) + `MEMORY.md` (domaines), et **découpe en
   sous-domaines** tout domaine dépassant ~150 faits (déplacement de faits). Si un découpage a lieu,
   le **signaler** dans le résumé de proposition.
```

- [ ] **Step 2 : Élargir le `git add` de l'étape 6 aux fichiers déplacés**

Dans `skills/memory-promote/SKILL.md`, dans le bloc git de l'étape 6, remplacer la/les ligne(s)
`git add …` existante(s) par :

```bash
   git -C "<clone>" add -A     # faits (déplacés en sous-domaines compris), index/**, MEMORY.md
```

- [ ] **Step 3 : Vérifier**

Run : `grep -n "reshard.py\|add -A" skills/memory-promote/SKILL.md`
Expected : occurrences présentes (appel reshard + `git add -A`).

- [ ] **Step 4 : Commit**

```bash
git add skills/memory-promote/SKILL.md
git commit -m "feat(memory-promote): reshard avant commit, git add -A des faits déplacés

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10 : Vérification d'ensemble

- [ ] **Step 1 : Suite complète**

Run : `python3 -m unittest discover -s . -p 'test_*.py' 2>&1 | tail -3`
Expected : tous les tests passent (les 51 précédents + reshard 15 + gen 3 = 69), `OK`.

- [ ] **Step 2 : Re-confirmer le test à l'échelle**

Run : `python3 scripts/verify-scale.py /tmp/sm-scale-vault && echo "exit=$?"`
Expected : `OK — tous les index ≤ 25 lignes, récursion présente`, exit=0.

- [ ] **Step 3 : Re-confirmer la non-pollution du vrai vault**

Run : `git -C ~/.shared-memory/vaults/negocian-memory status --porcelain | wc -l`
Expected : inchangé par rapport au début (le vrai vault n'a jamais été écrit).

- [ ] **Step 4 : (pas de commit)** Vérification seule.

---

## Self-Review

**Couverture de la spec :**

| Élément du design | Tâche |
|---|---|
| Invariant ≤ N faits / ≤ N sous-dossiers | Task 2 (split_tree + materialize), Task 3 (assert seuil) |
| reshard restructure (déplace si violation) + régénère index/MEMORY | Task 2 |
| Reconstruction propre d'`index/` (supprime obsolètes) | Task 2 (`rmtree index/` avant réécriture) |
| Idempotence + libellés humains préservés (suit les noms de dossier) | Task 3 (`test_idempotent`) |
| Split déterministe, récursif, labels `part-xx` | Task 1 (`split_tree`), Task 2 (`_materialize`), Task 3 (récursion) |
| Faits racine (perso) jamais shardés | Task 2 (`test_root_facts_untouched`) |
| `gen-synth-vault.py` : copie source sans `.git` + 30 domaines × 120-500 | Task 5 |
| Vérif à l'échelle : N=25 force la récursion, tout index ≤ N | Task 6 |
| Sûreté : negocian-memory seulement lu | Task 6 (Step 4), Task 10 (Step 3) |
| Rendu viewer de l'arbre N-niveaux | Task 6 (Step 3) |
| Câblage convention | Task 7 |
| Câblage memory-import / memory-promote | Task 8, Task 9 |

**Cohérence des types/formats (vérifiée) :**
- `split_tree → {"leaf": [...]}` | `{"children": [...]}` : produit Task 1, consommé par `_materialize`/`_count_leaf_facts` Task 2, testé Task 3.
- ligne de fait `` - `<nom>` — <desc> · <type> → `<rel>` `` : `_write_index` (Task 2) == format Volet A == parseur de pointeurs du test (Task 3 `leaf_pointer_targets`).
- ligne de sous-domaine `- <label> (<n> faits) → index/<seg>.md` : `_write_index` Task 2, vérifiée Task 2 (`test_large_domain_splits`).
- `reshard(vault, max_entries) -> {domaine: n}` : Task 2, utilisé par CLI Task 4, verify-scale Task 6.
- `generate(dest, source, domains, fmin, fmax, seed) -> {domaine: n}` : Task 5, utilisé par verify-scale Task 6.

**Placeholders :** aucun — code complet à chaque étape, commandes et sorties attendues explicites.

**Note (non bloquante) :** `MEMORY.md` est **régénéré** par reshard (titre + liste de domaines) ; toute intro/curation humaine de la carte serait écrasée. Conforme à la spec (« reshard = moteur unique d'index »). Documenté dans la convention (Task 7).
