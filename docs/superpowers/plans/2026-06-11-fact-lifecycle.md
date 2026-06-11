# Cycle de vie des faits périmés Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un moteur `scripts/stale.py` (source unique de la péremption + re-stamp) et un skill `/memory-refresh` qui re-vérifie les faits périmés contre le code et re-stampe / corrige / retire — fermant la boucle « signaler → agir ».

**Architecture :** `stale.py` (stdlib, réutilise `collect_facts`) expose `is_stale`/`days_old`/`stale_facts`/`set_reviewed` + CLI (liste / `--restamp`). `digest.py` réutilise `stale.is_stale` (DRY). Le skill `/memory-refresh` orchestre la re-vérification (jugement humain) → brouillons étage 1 → `/memory-promote`.

**Tech Stack :** Python 3 (stdlib : `datetime`, `importlib`, `os`, `re`, `sys`), bash, `unittest`.

**Référence design :** `docs/superpowers/specs/2026-06-11-fact-lifecycle-design.md`.

**Convention du programme :** doc ET tests à jour à chaque chantier (cf. mémoire `chantier-doc-tests-convention`).

---

## File Structure

| Fichier | Responsabilité | Action |
|---|---|---|
| `scripts/stale.py` | moteur péremption + re-stamp + CLI. | Créer |
| `tests/test_stale.py` | unitaires du moteur. | Créer |
| `scripts/digest.py` | réutiliser `stale.is_stale` (DRY). | Modifier |
| `skills/memory-refresh/SKILL.md` | skill de re-vérification. | Créer |
| `README.md`, `INSTALL.md`, `docs/ARCHITECTURE.md`, `docs/domain-convention.md` | documenter. | Modifier |

**Conventions réutilisées :**
- `scripts/build-viewer.py` : `collect_facts(vault, include_body=False) -> (facts, index_body)` ;
  chaque fait porte `file/name/description/type/reviewed/domain`.
- Format canonique : `reviewed` sous le bloc `metadata:` imbriqué (cf. `assets/fact-template.md`,
  chantier lint). `set_reviewed` vise ce format.
- Import des scripts (tiret) via `importlib.util.spec_from_file_location` (cf. `digest.py`).

---

## Task 1 : Moteur `scripts/stale.py` + tests

**Files:**
- Create: `scripts/stale.py`
- Create: `tests/test_stale.py`

- [ ] **Step 1 : Écrire les tests (`tests/test_stale.py`)**

```python
import datetime
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "scripts", "stale.py")
SPEC = importlib.util.spec_from_file_location("stale", SCRIPT)
st = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(st)

TODAY = datetime.date(2026, 6, 11)


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def fact_md(name, desc, reviewed):
    rev = ("  reviewed: %s\n" % reviewed) if reviewed else ""
    return "---\nname: %s\ndescription: %s\nmetadata:\n  type: project\n%s---\ncorps\n" % (
        name, desc, rev)


class IsStaleTest(unittest.TestCase):
    def test_absent_is_stale(self):
        self.assertTrue(st.is_stale("", TODAY))

    def test_recent_is_fresh(self):
        self.assertFalse(st.is_stale("2026-06-01", TODAY))   # 10 j

    def test_boundary_90_stale_89_fresh(self):
        self.assertTrue(st.is_stale("2026-03-13", TODAY))    # 90 j -> périmé
        self.assertFalse(st.is_stale("2026-03-14", TODAY))   # 89 j -> frais

    def test_unparseable_is_stale(self):
        self.assertTrue(st.is_stale("pas-une-date", TODAY))


class DaysOldTest(unittest.TestCase):
    def test_recent(self):
        self.assertEqual(st.days_old("2026-06-01", TODAY), 10)

    def test_absent_is_sentinel(self):
        self.assertGreaterEqual(st.days_old("", TODAY), 10 ** 9)


class StaleFactsTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.v = self._t.name

    def tearDown(self):
        self._t.cleanup()

    def test_only_stale_sorted_oldest_first(self):
        write(os.path.join(self.v, "a", "frais.md"), fact_md("frais", "frais", "2026-06-01"))
        write(os.path.join(self.v, "a", "vieux.md"), fact_md("vieux", "vieux", "2026-01-01"))
        write(os.path.join(self.v, "a", "sansdate.md"), fact_md("sansdate", "sans date", ""))
        res = st.stale_facts(self.v, today=TODAY)
        names = [f["name"] for f in res]
        self.assertNotIn("frais", names)                 # frais exclu
        self.assertEqual(names, ["sansdate", "vieux"])   # non-daté en tête, puis le plus vieux


class SetReviewedTest(unittest.TestCase):
    def test_updates_existing_reviewed(self):
        text = fact_md("x", "une description", "2026-01-01")
        out = st.set_reviewed(text, "2026-06-11")
        self.assertIn("  reviewed: 2026-06-11", out)
        self.assertNotIn("2026-01-01", out)
        self.assertIn("name: x", out)
        self.assertIn("corps", out)

    def test_adds_missing_reviewed(self):
        text = fact_md("x", "une description", "")   # metadata sans reviewed
        out = st.set_reviewed(text, "2026-06-11")
        self.assertIn("  reviewed: 2026-06-11", out)
        self.assertIn("  type: project", out)
        self.assertIn("une description", out)


class RestampCliTest(unittest.TestCase):
    def test_restamp_writes_date(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "f.md")
            write(p, fact_md("f", "une description", "2026-01-01"))
            subprocess.run([sys.executable, SCRIPT, "--restamp", p, "2026-06-11"], check=True)
            with open(p, encoding="utf-8") as fh:
                out = fh.read()
            self.assertIn("  reviewed: 2026-06-11", out)
            self.assertNotIn("2026-01-01", out)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2 : Lancer — échec attendu**

Run : `python3 -m unittest tests.test_stale -v`
Expected : ERROR — `scripts/stale.py` n'existe pas.

- [ ] **Step 3 : Écrire `scripts/stale.py`**

```python
#!/usr/bin/env python3
"""Péremption des faits : source unique de la règle de fraîcheur (STALE_DAYS=90).

is_stale / days_old : règle de péremption (reviewed absent/illisible, ou >= 90 j).
stale_facts(vault, today) : faits périmés, triés du plus vieux au plus récent (non-datés en tête).
set_reviewed(text, date) : re-stampe le frontmatter d'un fait (reviewed sous metadata:).
Réutilise collect_facts/parse_md de build-viewer.py. Stdlib seule.

CLI :
  python3 stale.py <vault>                      -> liste lisible des faits périmés
  python3 stale.py --restamp <fichier> [date]   -> fixe reviewed=date (déf. aujourd'hui)
"""
import datetime
import importlib.util
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "build_viewer", os.path.join(_HERE, "build-viewer.py")
)
_bv = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_bv)

STALE_DAYS = 90
_ABSENT = 10 ** 9   # sentinelle d'ancienneté : reviewed absent/illisible trie en tête
FM_RE = re.compile(r"^(---\n)(.*?)(\n---\n?)(.*)$", re.S)


def days_old(reviewed, today):
    """Ancienneté en jours ; sentinelle haute si `reviewed` absent/illisible."""
    if not reviewed:
        return _ABSENT
    try:
        d = datetime.date.fromisoformat(reviewed)
    except ValueError:
        return _ABSENT
    return (today - d).days


def is_stale(reviewed, today):
    """Périmé si `reviewed` absent/illisible, ou vieux d'au moins STALE_DAYS jours."""
    return days_old(reviewed, today) >= STALE_DAYS


def stale_facts(vault, today=None):
    """Faits périmés, triés du plus vieux au plus récent (non-datés en tête)."""
    today = today or datetime.date.today()
    facts, _ = _bv.collect_facts(vault, include_body=False)
    out = []
    for f in facts:
        age = days_old(f["reviewed"], today)
        if age >= STALE_DAYS:
            g = dict(f)
            g["days_old"] = age
            out.append(g)
    out.sort(key=lambda g: g["days_old"], reverse=True)
    return out


def set_reviewed(text, date):
    """Fixe `reviewed=date` sous le bloc `metadata:` canonique (met à jour ou ajoute).

    Préserve les autres clés, le corps. Si aucun bloc `metadata:`, en crée un en fin de frontmatter.
    """
    m = FM_RE.match(text)
    if not m:
        return text
    head, block, sep, body = m.group(1), m.group(2), m.group(3), m.group(4)
    lines = block.split("\n")
    # 1) une ligne `reviewed:` indentée existe -> remplacer sa valeur
    for i, ln in enumerate(lines):
        mm = re.match(r"^(\s+)reviewed\s*:\s*.*$", ln)
        if mm:
            lines[i] = "%sreviewed: %s" % (mm.group(1), date)
            return head + "\n".join(lines) + sep + body
    # 2) un bloc `metadata:` existe -> ajouter `reviewed` à la fin de ses lignes indentées
    for i, ln in enumerate(lines):
        if re.match(r"^metadata\s*:", ln):
            j = i + 1
            while j < len(lines) and re.match(r"^[ \t]+\S", lines[j]):
                j += 1
            lines.insert(j, "  reviewed: %s" % date)
            return head + "\n".join(lines) + sep + body
    # 3) pas de bloc metadata: -> en créer un
    lines.append("metadata:")
    lines.append("  reviewed: %s" % date)
    return head + "\n".join(lines) + sep + body


def _format_list(facts):
    if not facts:
        return "✅ Aucun fait périmé."
    lines = ["Faits périmés (%d) — du plus vieux au plus récent :" % len(facts)]
    for f in facts:
        age = "jamais vérifié" if f["days_old"] >= _ABSENT else "%d j" % f["days_old"]
        lines.append("- [%s] `%s` — %s · %s (%s)"
                     % (age, f["name"], f["description"], f["type"], f["domain"]))
    return "\n".join(lines)


def _restamp_file(path, date):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    new = set_reviewed(text, date)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new)


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "--restamp":
        path = argv[1]
        date = argv[2] if len(argv) > 2 else datetime.date.today().isoformat()
        _restamp_file(path, date)
        print("reviewed=%s -> %s" % (date, path))
    else:
        vault = argv[0] if argv else "."
        print(_format_list(stale_facts(vault)))
```

- [ ] **Step 4 : Lancer — succès attendu**

Run : `python3 -m unittest tests.test_stale -v`
Expected : PASS (10 tests).

- [ ] **Step 5 : Fumée CLI liste**

Run :
```bash
mkdir -p /tmp/stv/mailing
printf -- '---\nname: vieux\ndescription: un fait pas revu depuis longtemps\nmetadata:\n  type: project\n  reviewed: 2026-01-01\n---\nx\n' > /tmp/stv/mailing/vieux.md
python3 scripts/stale.py /tmp/stv
rm -rf /tmp/stv
```
Expected : « Faits périmés (1)… » avec la ligne `vieux`.

- [ ] **Step 6 : Commit**

```bash
git add scripts/stale.py tests/test_stale.py
git commit -m "feat(stale): moteur de péremption (is_stale/days_old/stale_facts/set_reviewed) + CLI

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 : DRY — `digest.py` réutilise `stale.is_stale`

**Files:**
- Modify: `scripts/digest.py`

- [ ] **Step 1 : Charger `stale.py` et déléguer `_is_stale`**

Dans `scripts/digest.py`, juste après le bloc qui charge `build-viewer.py` (les lignes définissant
`_bv`), ajouter le chargement de `stale.py` :

```python
_SPEC_STALE = importlib.util.spec_from_file_location(
    "stale", os.path.join(_HERE, "stale.py")
)
_stale = importlib.util.module_from_spec(_SPEC_STALE)
_SPEC_STALE.loader.exec_module(_stale)
```

Puis remplacer la définition locale :

```python
STALE_DAYS = 90


def _is_stale(reviewed, today):
    """Périmé si `reviewed` absent/illisible, ou vieux d'au moins STALE_DAYS jours (SP2)."""
    if not reviewed:
        return True
    try:
        d = datetime.date.fromisoformat(reviewed)
    except ValueError:
        return True
    return (today - d).days >= STALE_DAYS
```

par une délégation à la source unique :

```python
STALE_DAYS = _stale.STALE_DAYS


def _is_stale(reviewed, today):
    """Délègue à la source unique de la péremption (scripts/stale.py)."""
    return _stale.is_stale(reviewed, today)
```

(`build_digest` continue d'appeler `_is_stale` — inchangé.)

- [ ] **Step 2 : Vérifier que `digest` reste vert**

Run : `python3 -m unittest tests.test_digest -v`
Expected : PASS (tous les tests de digest, dont `test_stale_fact_marked_fresh_not`).

- [ ] **Step 3 : Fumée digest (péremption toujours marquée)**

Run :
```bash
mkdir -p /tmp/dgv/mailing
printf -- '---\nname: vieux\ndescription: fait pas revu\nmetadata:\n  type: project\n  reviewed: 2026-01-01\n---\nx\n' > /tmp/dgv/mailing/vieux.md
python3 scripts/digest.py /tmp/dgv | grep -c "⚠"
rm -rf /tmp/dgv
```
Expected : `1` (le fait vieux est bien marqué `⚠`).

- [ ] **Step 4 : Commit**

```bash
git add scripts/digest.py
git commit -m "refactor(digest): réutiliser stale.is_stale (source unique de péremption)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 : Skill `/memory-refresh`

**Files:**
- Create: `skills/memory-refresh/SKILL.md`

- [ ] **Step 1 : Écrire `skills/memory-refresh/SKILL.md`**

```markdown
---
name: memory-refresh
description: This skill should be used when the user asks to "rafraîchir la mémoire", "re-vérifier les faits périmés", "mettre à jour les faits anciens", "revoir les faits à revérifier", "refresh memory", "re-verify stale facts", or "/memory-refresh". It lists stale facts (reviewed >= 90 days or never), re-verifies each project/reference fact against the current code, and re-stamps / corrects / retires it — drafts for /memory-promote.
argument-hint: ""
allowed-tools: Bash, Read, Grep, Glob, Edit, AskUserQuestion
version: 0.1.0
---

# memory-refresh — Re-vérifier les faits périmés

Ferme la boucle de fraîcheur : **lister** les faits périmés (`reviewed` ≥ 90 j ou jamais), les
**confronter au code actuel**, et **re-stamper** (encore vrais), **corriger** ou **retirer** (faux).
Écrit des **brouillons** (étage 1) ; rien n'est partagé tant que `/memory-promote` n'a pas eu lieu.

## Procédure

1. **Localiser le vault** du projet courant :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT%/}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Si rien n'est renvoyé, demander de lancer `/memory-setup` d'abord.

2. **Lister les périmés** (lecture seule) :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/stale.py "<clone>"
   ```

   Séparer les faits **project/reference** (re-vérifiables contre le code) des faits **perso**
   (`user`/`feedback`). Si la liste est vide, le dire et s'arrêter.

3. **Si beaucoup de faits**, proposer un **sous-ensemble** (par domaine, ou les N plus vieux) pour
   garder la session focalisée.

4. **Pour chaque fait project/reference** (du plus vieux au plus récent) : le **confronter au code
   actuel** (Read/Grep/Glob) — encore vrai ? non contredit ?
   - **Encore vrai** → re-stamper :

     ```bash
     python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/stale.py --restamp "<clone>/<chemin-du-fait>"
     ```

   - **Faux** → proposer au choix : **corriger** (éditer le corps pour coller à la réalité, puis
     re-stamper) ou **retirer** (supprimer le fichier ; la suppression se propage via
     `/memory-promote` → `/memory-review`).

5. **Faits perso périmés** → les **lister à juger** (préférence, pas de code à vérifier) ; ne
   re-stamper que si l'utilisateur confirme qu'ils tiennent encore.

6. **Confirmer le lot** avant d'écrire (AskUserQuestion) : récap « N re-stampés · M corrigés · K
   retirés ». Ne rien écrire sans accord.

7. **Régénérer les index** si des fichiers ont changé, puis guider vers `/memory-promote` :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/reshard.py "<clone>"
   ```

## Points d'attention

- **Re-stamper = « j'ai vérifié »**, pas « le fichier existe » : ne jamais re-stamper sans avoir
  confronté le fait au code. Pas de re-stampage en masse à l'aveugle.
- **Confirmation obligatoire** avant écriture ; brouillons (étage 1) → `/memory-promote`.
- **Pas d'archivage automatique** : retirer un fait est une décision humaine explicite.
- **Perso** (`user`/`feedback`) : pas de code à vérifier — l'utilisateur juge.

## Prochaine étape (guider l'utilisateur)

Terminer en disant mot pour mot : « Pour partager ces mises à jour, lance `/memory-promote`. »

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/scripts/stale.py`** — liste des périmés + re-stamp.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/reshard.py`** — régénère `index/**` après changements.
- **`${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`** — fraîcheur, format d'un fait.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — résolution du vault.
```

- [ ] **Step 2 : Vérifier le frontmatter**

Run :
```bash
head -7 skills/memory-refresh/SKILL.md
grep -c "^name: memory-refresh" skills/memory-refresh/SKILL.md
```
Expected : frontmatter présent ; `grep` renvoie `1`.

- [ ] **Step 3 : Commit**

```bash
git add skills/memory-refresh/SKILL.md
git commit -m "feat(refresh): skill /memory-refresh — re-vérifier et re-stamper les faits périmés

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 : Documentation

**Files:**
- Modify: `README.md`
- Modify: `INSTALL.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/domain-convention.md`

- [ ] **Step 1 : README — tableau des skills**

Dans `README.md`, dans le tableau « ### Skills », après la ligne `| `/memory-lint` | … |`, insérer :

```markdown
| `/memory-refresh` | **re-vérifier les faits périmés** (≥ 90 j) contre le code : re-stamper / corriger / retirer |
```

- [ ] **Step 2 : README — puce « Sous le capot »**

Dans `README.md`, section « ### Sous le capot », après la puce « 🧹 Lint des faits », insérer :

```markdown
- **🔁 Re-vérification (`/memory-refresh`)** — la fraîcheur ne fait pas que signaler : `/memory-refresh`
  liste les faits périmés (≥ 90 j ou jamais vérifiés), les **confronte au code actuel**, et
  **re-stampe** ceux encore vrais, **corrige** ou **retire** les autres. La confiance ne s'érode pas.
```

- [ ] **Step 3 : INSTALL — commandes utiles**

Dans `INSTALL.md`, dans le tableau « Commandes utiles », après la ligne `| `/memory-lint` | … |`, insérer :

```markdown
| `/memory-refresh` | re-vérifier les faits périmés contre le code (re-stamp / corrige / retire) |
```

- [ ] **Step 4 : ARCHITECTURE — nouvelle section §15**

Dans `docs/ARCHITECTURE.md`, à la **fin du fichier** (après §14), ajouter :

```markdown
## 15. Cycle de vie des faits / re-vérification

La fraîcheur **signale** (`⚠` si `reviewed` ≥ 90 j ou absent), mais signaler ne suffit pas : sans
remédiation, le `⚠` s'accumule. `scripts/stale.py` est la **source unique** de la règle de péremption
(`is_stale`, `days_old`, `STALE_DAYS = 90`) — réutilisée par `digest.py` (DRY) — et liste les faits
périmés (`stale_facts`, triés du plus vieux au plus récent).

`/memory-refresh` **ferme la boucle** : il liste les périmés, **confronte chaque fait
project/reference au code actuel**, puis **re-stampe** (`set_reviewed` → `reviewed = aujourd'hui`)
ceux encore vrais, **corrige** ou **retire** les autres. Les faits perso (`user`/`feedback`) sont
listés à juger (pas de code à vérifier). Tout est **brouillon (étage 1)** → `/memory-promote`.

Principe : **re-stamper signifie « vérifié », pas « existe »** — jamais de re-stampage en masse à
l'aveugle ; pas d'archivage automatique (retirer un fait est une décision humaine).
```

- [ ] **Step 5 : domain-convention — renvoi dans « Fraîcheur des faits »**

Dans `docs/domain-convention.md`, à la **fin de la section** « ## Fraîcheur des faits (`reviewed`) »
(avant la section suivante), ajouter cette ligne :

```markdown
Pour **agir** sur les faits périmés (les re-vérifier contre le code et re-stamper / corriger /
retirer), utiliser `/memory-refresh` (moteur `scripts/stale.py`).
```

- [ ] **Step 6 : Vérifier**

Run : `grep -c "memory-refresh" README.md INSTALL.md docs/ARCHITECTURE.md docs/domain-convention.md`
Expected : chaque fichier ≥ 1.

- [ ] **Step 7 : Commit**

```bash
git add README.md INSTALL.md docs/ARCHITECTURE.md docs/domain-convention.md
git commit -m "docs(refresh): documenter /memory-refresh + stale.py (README/INSTALL/ARCHITECTURE/convention)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 : Vérification

- [ ] **Step 1 : Suite complète (non-régression)**

Run : `python3 -m unittest discover -s . -p 'test_*.py' 2>&1 | tail -3`
Expected : OK — tous les tests passent (existants + 10 de `test_stale` ; `test_digest` toujours vert).

- [ ] **Step 2 : Fumée bout-en-bout (liste → re-stamp → plus périmé)**

Run :
```bash
TMP=$(mktemp -d); mkdir -p "$TMP/mailing"
printf -- '---\nname: vieux\ndescription: un fait pas revu depuis longtemps du tout\nmetadata:\n  type: project\n  reviewed: 2026-01-01\n---\nx\n' > "$TMP/mailing/vieux.md"
echo "=== liste avant ===" ; python3 scripts/stale.py "$TMP"
echo "=== re-stamp ===" ; python3 scripts/stale.py --restamp "$TMP/mailing/vieux.md" "$(date +%F)"
echo "=== liste après ===" ; python3 scripts/stale.py "$TMP"
rm -rf "$TMP"
```
Expected : avant → le fait `vieux` listé ; après re-stamp à aujourd'hui → « ✅ Aucun fait périmé. ».

- [ ] **Step 3 : Relecture**

Vérifier de visu : `stale.py` n'utilise que la stdlib ; `set_reviewed` préserve name/description/corps ;
`digest.py` délègue bien à `stale.is_stale` ; le skill `/memory-refresh` re-stampe **uniquement** après
confrontation au code et demande confirmation avant le lot ; doc §15 cohérente.

---

## Self-Review

**Couverture de la spec :**

| Élément du design | Tâche |
|---|---|
| `stale.py` : `is_stale`, `days_old`, `stale_facts`, `set_reviewed` + CLI liste/`--restamp` | Task 1 |
| `STALE_DAYS=90`, sentinelle pour non-datés, tri du plus vieux au plus récent | Task 1 + tests |
| DRY : `digest.py` réutilise `stale.is_stale` | Task 2 |
| Skill `/memory-refresh` (liste → confronte code → re-stamp/corrige/retire ; perso à juger) | Task 3 |
| Confirmation avant écriture ; brouillons → promote ; reshard | Task 3 |
| Doc (README/INSTALL/ARCHITECTURE §15/convention) | Task 4 |
| Tests (`test_stale` + digest reste vert) | Task 1, Task 5 |
| Vérification (suite + fumée bout-en-bout) | Task 5 |

**Placeholders :** aucun — `stale.py`, `test_stale.py`, l'edit DRY de digest, le `SKILL.md` et les
edits doc sont fournis intégralement.

**Cohérence des types/signatures :** `is_stale(reviewed, today) -> bool`, `days_old(reviewed, today)
-> int`, `stale_facts(vault, today=None) -> list[dict]` (chaque dict enrichi de `days_old`),
`set_reviewed(text, date) -> str` — mêmes signatures dans le moteur, les tests et la CLI. La
sentinelle `_ABSENT = 10**9` est cohérente entre `days_old`, le tri et le test
`test_absent_is_sentinel` (`>= 10**9`). `digest._is_stale` délègue à `stale.is_stale` (même
sémantique), `build_digest` inchangé. `set_reviewed` cible le format canonique `metadata:` (chantier
lint).
