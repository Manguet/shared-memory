# Lint & normalisation des faits (`/memory-lint`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un moteur `scripts/lint.py` + skill `/memory-lint` qui détecte les problèmes de format des faits, corrige mécaniquement la seule dérive sûre (frontmatter à plat → bloc `metadata:`), et signale le reste — avec un garde-fou advisory dans `/memory-promote`.

**Architecture :** Moteur Python pur (`lint_vault`/`format_report`/`apply_fixes` + CLI), réutilisant `parse_md`/`collect_facts` de `build-viewer.py` via `importlib` (comme `digest.py`). Le skill orchestre rapport → confirmation → fix → reshard. Rapport + fix **opt-in** ; **seule** auto-correction = `flat_frontmatter`.

**Tech Stack :** Python 3 (stdlib : `importlib`, `os`, `re`, `sys`), bash, `unittest`.

**Référence design :** `docs/superpowers/specs/2026-06-11-memory-lint-design.md`.

**Convention du programme :** doc ET tests à jour à chaque chantier (cf. mémoire `chantier-doc-tests-convention`).

---

## File Structure

| Fichier | Responsabilité | Action |
|---|---|---|
| `scripts/lint.py` | moteur : détection (`lint_vault`, `format_report`) + correction (`apply_fixes`) + CLI. | Créer |
| `tests/test_lint.py` | tests unitaires du moteur (détection + fix + idempotence). | Créer |
| `skills/memory-lint/SKILL.md` | surface utilisateur (rapport → confirmation → fix → reshard). | Créer |
| `skills/memory-promote/SKILL.md` | garde-fou advisory : lint avant push, signaler les erreurs. | Modifier |
| `README.md`, `INSTALL.md`, `docs/ARCHITECTURE.md`, `docs/domain-convention.md` | documenter. | Modifier |

**Conventions réutilisées :**
- `scripts/build-viewer.py` : `parse_md(path) -> (fm, body)` aplatit le frontmatter : une clé sous
  `metadata:` ressort en `metadata.type` ; une clé de premier niveau ressort en `type`. C'est ce qui
  permet de distinguer le format imbriqué du format à plat.
- Import des scripts (tiret dans le nom) via `importlib.util.spec_from_file_location` (cf.
  `tests/test_build_viewer.py`, `scripts/digest.py`).
- Types valides : `project`, `reference`, `user`, `feedback` (cf. `docs/domain-convention.md`).

---

## Task 1 : Moteur de détection (`lint_vault` + `format_report` + CLI rapport)

**Files:**
- Create: `scripts/lint.py`
- Create: `tests/test_lint.py`

- [ ] **Step 1 : Écrire les tests de détection (`tests/test_lint.py`)**

```python
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
        # le type est présent (à plat) -> missing_type NE se déclenche PAS
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
        write(os.path.join(self.vault, "facturation", "b.md"), CLEAN)   # même name: relance-j3
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

    def test_format_report_groups_by_severity(self):
        write(os.path.join(self.vault, "mailing", "x.md"),
              "---\nname: x\ndescription:\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nc\n")
        report = lint.format_report(lint.lint_vault(self.vault))
        self.assertIn("Erreurs", report)
        self.assertIn("erreur", report.lower())

    def test_format_report_empty(self):
        self.assertIn("Aucun problème", lint.format_report([]))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2 : Lancer les tests — échec attendu**

Run : `python3 -m unittest tests.test_lint -v`
Expected : ERROR — `scripts/lint.py` n'existe pas.

- [ ] **Step 3 : Écrire `scripts/lint.py` (détection + rapport + CLI)**

```python
#!/usr/bin/env python3
"""Lint & normalisation des faits d'un vault mémoire.

`lint_vault(vault) -> list[Finding]` parcourt les faits et applique un catalogue de règles.
Un Finding = {file, rule, severity, fixable, message}. `apply_fixes` n'applique que les
findings fixable=True (aujourd'hui : flat_frontmatter → bloc metadata:). Pur fichiers, stdlib
seule. Réutilise parse_md de build-viewer.py.

CLI : python3 lint.py <vault> [--fix]
"""
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

VALID_TYPES = {"project", "reference", "user", "feedback"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
FM_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def _finding(file, rule, severity, fixable, message):
    return {"file": file, "rule": rule, "severity": severity, "fixable": fixable, "message": message}


def _fact_files(vault):
    """Chemins relatifs des faits (mêmes exclusions que collect_facts : MEMORY.md, index/)."""
    out = []
    for root, _dirs, files in os.walk(vault):
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(root, fn), vault)
            parts = rel.split(os.sep)
            if rel == "MEMORY.md" or parts[0] == "index":
                continue
            out.append(rel)
    return sorted(out)


def _lint_fact(rel, fm, body, known):
    out = []
    name = (fm.get("name") or "").strip()
    if not name:
        out.append(_finding(rel, "missing_name", "error", False, "Champ `name` absent ou vide."))
    desc = (fm.get("description") or "").strip()
    if not desc:
        out.append(_finding(rel, "missing_description", "error", False,
                            "Champ `description` absent ou vide."))
    elif len(desc.split()) < 5:
        out.append(_finding(rel, "short_description", "warn", False,
                            "Description courte (< 5 mots) — c'est l'aiguillage du recall."))

    nested_type = fm.get("metadata.type")
    flat_type = fm.get("type")
    typ = nested_type or flat_type
    if not typ:
        out.append(_finding(rel, "missing_type", "error", False,
                            "Aucun `type` (ni `metadata.type` ni `type`)."))
    elif typ not in VALID_TYPES:
        out.append(_finding(rel, "invalid_type", "error", False,
                            "Type invalide : `%s` (attendu : %s)." % (typ, ", ".join(sorted(VALID_TYPES)))))

    if flat_type is not None or fm.get("reviewed") is not None:
        out.append(_finding(rel, "flat_frontmatter", "warn", True,
                            "Frontmatter à plat (`type`/`reviewed`) — à mettre sous un bloc `metadata:`."))

    reviewed = fm.get("metadata.reviewed") or fm.get("reviewed")
    if not reviewed:
        out.append(_finding(rel, "reviewed_missing", "warn", False,
                            "Pas de `reviewed` (date de vérification du fait)."))
    elif not DATE_RE.match(reviewed):
        out.append(_finding(rel, "reviewed_malformed", "warn", False,
                            "`reviewed: %s` n'est pas au format AAAA-MM-JJ." % reviewed))

    if name and not SLUG_RE.match(name):
        out.append(_finding(rel, "name_not_slug", "warn", False,
                            "`name` n'est pas un slug kebab-case (renommer casserait les pointeurs)."))

    for target in WIKILINK_RE.findall(body):
        t = target.strip()
        if t and t not in known:
            out.append(_finding(rel, "broken_wikilink", "warn", False,
                                "Lien `[[%s]]` sans fait correspondant." % t))

    base = os.path.basename(rel)
    is_personal = typ in ("user", "feedback") or base.startswith("feedback_")
    at_root = os.sep not in rel
    if is_personal and not at_root:
        out.append(_finding(rel, "personal_misplaced", "warn", False,
                            "Fait perso (`user`/`feedback`) hors racine — doit rester à la racine."))
    return out


def lint_vault(vault):
    files = _fact_files(vault)
    parsed = {}       # rel -> (fm or None, body)
    names = {}        # name -> [rel, ...]
    findings = []
    for rel in files:
        full = os.path.join(vault, rel)
        text = open(full, encoding="utf-8").read()
        if not FM_RE.match(text):
            findings.append(_finding(rel, "frontmatter_invalid", "error", False,
                                     "Frontmatter `---` absent ou illisible."))
            parsed[rel] = (None, text)
            continue
        fm, body = _bv.parse_md(full)
        parsed[rel] = (fm, body)
        nm = (fm.get("name") or "").strip()
        if nm:
            names.setdefault(nm, []).append(rel)

    known = set(names.keys())
    for rel in files:
        fm, body = parsed[rel]
        if fm is None:
            continue
        findings.extend(_lint_fact(rel, fm, body, known))

    for nm, rels in names.items():
        if len(rels) > 1:
            for rel in rels:
                findings.append(_finding(rel, "duplicate_name", "error", False,
                                         "`name: %s` est en double (%d faits)." % (nm, len(rels))))
    return findings


def format_report(findings):
    if not findings:
        return "✅ Aucun problème détecté."
    errors = [f for f in findings if f["severity"] == "error"]
    warns = [f for f in findings if f["severity"] == "warn"]
    lines = ["Lint mémoire : %d erreur(s), %d avertissement(s)." % (len(errors), len(warns))]
    for label, group in (("Erreurs", errors), ("Avertissements", warns)):
        if not group:
            continue
        lines.append("")
        lines.append("## %s" % label)
        for f in sorted(group, key=lambda x: (x["file"], x["rule"])):
            fix = " [auto-corrigeable]" if f["fixable"] else ""
            lines.append("- `%s` — %s : %s%s" % (f["file"], f["rule"], f["message"], fix))
    return "\n".join(lines)


if __name__ == "__main__":
    rest = sys.argv[1:]
    do_fix = "--fix" in rest
    positional = [a for a in rest if not a.startswith("--")]
    vault = positional[0] if positional else "."
    findings = lint_vault(vault)
    if do_fix:
        from_fixes = apply_fixes(vault, findings)
        print("%d fait(s) normalisé(s) (flat_frontmatter)." % from_fixes)
        findings = lint_vault(vault)
    print(format_report(findings))
```

Note : le bloc `__main__` appelle `apply_fixes`, défini en Task 2. Tant que Task 2 n'est pas faite,
**ne pas** lancer `lint.py --fix` (le `lint_vault` simple et les tests de détection fonctionnent ;
`apply_fixes` est référencé mais non appelé hors `--fix`).

- [ ] **Step 4 : Lancer les tests de détection — succès attendu**

Run : `python3 -m unittest tests.test_lint -v`
Expected : PASS (13 tests de `LintDetectionTest`).

- [ ] **Step 5 : Fumée CLI rapport**

Run :
```bash
mkdir -p /tmp/lintv/mailing
printf -- '---\nname: Mauvais Nom\ndescription: court\ntype: project\nreviewed: 2026-06-01\n---\nc\n' > /tmp/lintv/mailing/x.md
python3 scripts/lint.py /tmp/lintv
```
Expected : rapport listant `flat_frontmatter [auto-corrigeable]`, `name_not_slug`, `short_description` ; n'écrit rien.

- [ ] **Step 6 : Commit**

```bash
git add scripts/lint.py tests/test_lint.py
git commit -m "feat(lint): moteur de détection des faits (lint_vault + format_report + CLI)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 : Correction mécanique (`apply_fixes` + `--fix`)

**Files:**
- Modify: `scripts/lint.py`
- Modify: `tests/test_lint.py`

- [ ] **Step 1 : Ajouter les tests de fix (`tests/test_lint.py`)**

Ajouter cette classe à la fin de `tests/test_lint.py`, avant le `if __name__` :

```python
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
        # plus de clé type/reviewed au premier niveau
        self.assertNotIn("\ntype: project", out)
        self.assertNotIn("\nreviewed: 2026-06-01", out)
        # name, description et corps préservés
        self.assertIn("name: vieux-fait", out)
        self.assertIn("Un fait au format hérité à plat sans bloc metadata", out)
        self.assertIn("Corps hérité.", out)

    def test_fix_is_idempotent(self):
        p = os.path.join(self.vault, "mailing", "x.md")
        write(p, FLAT)
        lint.apply_fixes(self.vault, lint.lint_vault(self.vault))
        # après fix, plus aucun finding (le fait FLAT est sinon propre)
        self.assertEqual(lint.lint_vault(self.vault), [])

    def test_apply_fixes_only_touches_fixable(self):
        # un fait avec un avertissement non-fixable (name_not_slug) ne doit PAS être modifié
        p = os.path.join(self.vault, "x.md")
        content = ("---\nname: Pas un slug\n"
                   "description: une description assez longue pour passer le seuil\n"
                   "metadata:\n  type: project\n  reviewed: 2026-06-01\n---\nc\n")
        write(p, content)
        before = open(p, encoding="utf-8").read()
        n = lint.apply_fixes(self.vault, lint.lint_vault(self.vault))
        self.assertEqual(n, 0)
        self.assertEqual(open(p, encoding="utf-8").read(), before)
```

- [ ] **Step 2 : Lancer les tests de fix — échec attendu**

Run : `python3 -m unittest tests.test_lint.LintFixTest -v`
Expected : FAIL/ERROR — `apply_fixes` n'existe pas encore.

- [ ] **Step 3 : Implémenter `apply_fixes` + `_normalize_frontmatter` dans `scripts/lint.py`**

Insérer ces deux fonctions dans `scripts/lint.py` **juste avant** le bloc `if __name__ == "__main__":` :

```python
def _normalize_frontmatter(text):
    """Déplace `type`/`reviewed` de premier niveau sous un bloc `metadata:`.

    Renvoie (new_text, changed). Préserve les autres clés de tête (name, description, …),
    le bloc metadata existant et le corps. Idempotent : sans clé à plat, renvoie (text, False).
    """
    m = FM_RE.match(text)
    if not m:
        return text, False
    block, body = m.group(1), m.group(2)
    lines = block.split("\n")
    top, meta, flat = [], [], {}
    i = 0
    while i < len(lines):
        ln = lines[i]
        if re.match(r"^metadata\s*:", ln):
            i += 1
            while i < len(lines) and re.match(r"^[ \t]+\S", lines[i]):
                meta.append(lines[i].strip())
                i += 1
            continue
        mm = re.match(r"^([\w.\-]+)\s*:\s*(.*)$", ln)
        if mm and mm.group(1) in ("type", "reviewed") and ln[:1] not in (" ", "\t"):
            flat[mm.group(1)] = mm.group(2).strip()
            i += 1
            continue
        top.append(ln)
        i += 1
    if not flat:
        return text, False
    meta_keys = {kv.split(":", 1)[0].strip() for kv in meta}
    merged = list(meta)
    for k in ("type", "reviewed"):
        if k in flat and k not in meta_keys:
            merged.append("%s: %s" % (k, flat[k]))
    new_lines = [l for l in top if l.strip() != ""]
    new_lines.append("metadata:")
    new_lines.extend("  " + kv for kv in merged)
    return "---\n" + "\n".join(new_lines) + "\n---\n" + body, True


def apply_fixes(vault, findings):
    """Applique uniquement les findings fixable=True (flat_frontmatter). Renvoie le nb corrigé."""
    targets = sorted({f["file"] for f in findings
                      if f.get("fixable") and f["rule"] == "flat_frontmatter"})
    fixed = 0
    for rel in targets:
        full = os.path.join(vault, rel)
        new_text, changed = _normalize_frontmatter(open(full, encoding="utf-8").read())
        if changed:
            open(full, "w", encoding="utf-8").write(new_text)
            fixed += 1
    return fixed
```

- [ ] **Step 4 : Lancer les tests de fix — succès attendu**

Run : `python3 -m unittest tests.test_lint -v`
Expected : PASS (les 13 de détection + 3 de fix = 16).

- [ ] **Step 5 : Fumée CLI `--fix`**

Run :
```bash
printf -- '---\nname: vieux-fait\ndescription: Un fait au format hérité à plat sans metadata\ntype: project\nreviewed: 2026-06-01\n---\nCorps.\n' > /tmp/lintv/mailing/x.md
python3 scripts/lint.py /tmp/lintv --fix
echo "--- fichier après fix ---"; cat /tmp/lintv/mailing/x.md
rm -rf /tmp/lintv
```
Expected : « 1 fait(s) normalisé(s) » puis un rapport propre ; le fichier montre `metadata:` avec `type`/`reviewed` indentés.

- [ ] **Step 6 : Commit**

```bash
git add scripts/lint.py tests/test_lint.py
git commit -m "feat(lint): apply_fixes — normaliser le frontmatter à plat (idempotent)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 : Skill `/memory-lint`

**Files:**
- Create: `skills/memory-lint/SKILL.md`

- [ ] **Step 1 : Écrire `skills/memory-lint/SKILL.md`**

```markdown
---
name: memory-lint
description: This skill should be used when the user asks to "linter la mémoire", "vérifier le format des faits", "nettoyer le vault", "normaliser les faits", "valider les faits", "lint memory", "check memory facts", or "/memory-lint". It reports format/quality problems in a vault's facts and applies only the safe mechanical fix (flat frontmatter → metadata block) after confirmation.
argument-hint: ""
allowed-tools: Bash, Read, AskUserQuestion
version: 0.1.0
---

# memory-lint — Linter et normaliser les faits du vault

Détecte les problèmes de **format** des faits (champs requis, type valide, `name` unique, date
bien formée, frontmatter à plat, wikilinks cassés, perso mal placé), **corrige mécaniquement** la
seule dérive sûre (frontmatter à plat → bloc `metadata:`) **après confirmation**, et **signale** le
reste pour décision humaine. N'écrit jamais sans accord.

## Procédure

1. **Localiser le vault** du projet courant :

   ```bash
   bash -c 'source ${CLAUDE_PLUGIN_ROOT%/}/scripts/lib.sh; sm_vault_clone_for_slug "$(sm_slug "${CLAUDE_PROJECT_DIR:-$PWD}")"'
   ```

   Si rien n'est renvoyé, demander de lancer `/memory-setup` d'abord.

2. **Lancer le lint** (lecture seule, n'écrit rien) :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/lint.py "<clone>"
   ```

3. **Présenter le rapport** tel quel : erreurs d'abord, puis avertissements. Expliquer brièvement
   les **erreurs** (elles cassent les pointeurs/recherche : champ requis manquant, type invalide,
   `name` en double) — elles se corrigent **à la main** (ou via le viewer `/memory-ui`).

4. **S'il y a des findings `[auto-corrigeable]`** (frontmatter à plat) : indiquer le nombre de faits
   concernés et **demander l'accord** (AskUserQuestion) avant d'écrire. Sans accord, ne rien faire.

5. **Si accord, appliquer** la correction mécanique puis régénérer les index :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/lint.py "<clone>" --fix
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/reshard.py "<clone>"
   ```

6. **Rappeler** que les **avertissements** non corrigés (description courte, `name` non-slug,
   wikilinks cassés, perso mal placé) sont à traiter **à la main** ou via `/memory-ui`, et renvoyer
   vers `/memory-promote` une fois le vault propre.

## Points d'attention

- **Une seule auto-correction** : `flat_frontmatter` (plat → bloc `metadata:`). Tout le reste est
  **signalé**, jamais réécrit (renommer un `name` ou déplacer un perso casserait les pointeurs).
- **Confirmation obligatoire** avant toute écriture — pas de mutation silencieuse.
- **Brouillons (étage 1)** : les corrections restent locales tant que `/memory-promote` n'a pas
  poussé une branche relue.
- **Pas de date inventée** : le lint signale l'absence de `reviewed` mais ne la stampe pas (dater
  est un jugement ; c'est `/memory-promote` qui stampe quand un fait est confirmé vrai).

## Ressources

- **`${CLAUDE_PLUGIN_ROOT}/scripts/lint.py`** — moteur (détection + correction mécanique).
- **`${CLAUDE_PLUGIN_ROOT}/docs/domain-convention.md`** — format canonique d'un fait, types valides.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/reshard.py`** — régénère `index/**` après correction.
- **`${CLAUDE_PLUGIN_ROOT}/scripts/lib.sh`** — résolution du vault.
```

- [ ] **Step 2 : Vérifier le frontmatter du skill**

Run :
```bash
head -7 skills/memory-lint/SKILL.md
grep -c "^name: memory-lint" skills/memory-lint/SKILL.md
```
Expected : frontmatter présent ; `grep` renvoie `1`.

- [ ] **Step 3 : Commit**

```bash
git add skills/memory-lint/SKILL.md
git commit -m "feat(lint): skill /memory-lint — rapport + fix opt-in du format des faits

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 : Garde-fou advisory dans `/memory-promote`

**Files:**
- Modify: `skills/memory-promote/SKILL.md`

- [ ] **Step 1 : Insérer une étape de lint avant le push**

Dans `skills/memory-promote/SKILL.md`, la procédure va jusqu'à l'étape `5.` (reshard) puis `6.`
(créer la branche + push). Insérer une nouvelle étape **entre l'étape 5 et l'étape 6**, et renuméroter
l'ancienne 6 en 7 et l'ancienne 7 en 8. Le texte à insérer (nouvelle étape 6) :

```markdown
6. **Garde-fou lint (advisory).** Avant de pousser, vérifier le format des faits du clone :

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT%/}/scripts/lint.py "<clone>"
   ```

   **S'il y a des erreurs** (`severity=error` : champ requis manquant, type invalide, `name` en
   double), les **afficher** et **demander** s'il faut les corriger d'abord (via `/memory-lint` ou
   à la main). **Advisory** : ne pas bloquer la promotion de force ; l'utilisateur décide. Les
   avertissements sont mentionnés mais ne retardent pas le push.
```

- [ ] **Step 2 : Vérifier la renumérotation**

Run : `grep -n "^6\.\|^7\.\|^8\." skills/memory-promote/SKILL.md`
Expected : trois étapes numérotées `6.` (garde-fou lint), `7.` (créer la branche + push), `8.`
(confirmer) — l'ordre logique est préservé.

- [ ] **Step 3 : Commit**

```bash
git add skills/memory-promote/SKILL.md
git commit -m "feat(promote): garde-fou lint advisory avant le push

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 : Documentation

**Files:**
- Modify: `README.md`
- Modify: `INSTALL.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/domain-convention.md`

- [ ] **Step 1 : README — tableau des skills**

Dans `README.md`, dans le tableau « ### Skills », après la ligne `| `/memory-ui` | … |`, insérer :

```markdown
| `/memory-lint` | **valider/nettoyer** les faits : rapport des problèmes de format + correction mécanique du frontmatter à plat (opt-in) |
```

- [ ] **Step 2 : README — puce « Sous le capot »**

Dans `README.md`, section « ### Sous le capot », après la puce « 🧬 Dédup sémantique », insérer :

```markdown
- **🧹 Lint des faits** — `/memory-lint` détecte les dérives de format (champs requis, type valide,
  `name` unique, date bien formée, wikilinks cassés) et **normalise** le frontmatter à plat vers le
  bloc `metadata:` canonique. Rapport d'abord ; **correction opt-in**, jamais silencieuse.
```

- [ ] **Step 3 : INSTALL — commandes utiles**

Dans `INSTALL.md`, dans le tableau « Commandes utiles », après la ligne `| /memory-ui | … |`, insérer :

```markdown
| `/memory-lint` | valider et nettoyer le format des faits du vault (rapport + fix opt-in) |
```

- [ ] **Step 4 : ARCHITECTURE — nouvelle section §13**

Dans `docs/ARCHITECTURE.md`, à la fin du fichier (après la dernière section §12), ajouter :

```markdown
## 13. Lint & normalisation des faits

Le format d'un fait peut **dériver** dans le temps (frontmatter à plat hérité, champ requis oublié,
date mal formée, `name` en double). `/memory-lint` (moteur `scripts/lint.py`) **détecte** ces
problèmes et **corrige mécaniquement** la seule dérive sûre : un frontmatter à plat
(`type:`/`reviewed:` de premier niveau) est réécrit sous un bloc **`metadata:`** canonique.

- **`lint_vault(vault)`** renvoie une liste de *findings* `{file, rule, severity, fixable, message}`
  (6 règles `error`, 7 `warn` dont une seule `fixable`). **`apply_fixes`** n'applique que les
  findings `fixable=True` (`flat_frontmatter`), de façon **idempotente**.
- **Rapport + fix opt-in** : le skill montre le rapport, applique la correction mécanique **après
  confirmation**, puis régénère les index (`reshard.py`). Le reste (`name` non-slug, doublons,
  description courte, wikilinks cassés, perso mal placé) est **signalé**, jamais réécrit — renommer
  ou déplacer casserait les pointeurs.
- **Garde-fou promote** : `/memory-promote` lance le lint avant le push et signale les erreurs
  (advisory, sans blocage dur).

Le format **canonique** d'un fait est le bloc `metadata:` imbriqué (cf. `assets/fact-template.md`,
`docs/domain-convention.md`). Le lint converge vers ce format ; il n'invente jamais de date
`reviewed` (dater reste un jugement, fait par `/memory-promote` à la vérification).
```

- [ ] **Step 5 : domain-convention — expliciter le format canonique**

Dans `docs/domain-convention.md`, juste après la section « ## Fraîcheur des faits (`reviewed`) »
(qui se termine avant la section suivante), ajouter la section suivante. **Important** : l'exemple
de frontmatter est un **bloc indenté de 4 espaces** (pas un fence ```` ``` ````), pour éviter tout
conflit de balises ; recopier exactement, y compris l'indentation :

> ## Format canonique d'un fait
>
> Le frontmatter **canonique** place `type` et `reviewed` sous un bloc **`metadata:`** imbriqué
> (cf. `assets/fact-template.md`) :
>
> &nbsp;&nbsp;&nbsp;&nbsp;`---`
> &nbsp;&nbsp;&nbsp;&nbsp;`name: <slug-kebab-case>`
> &nbsp;&nbsp;&nbsp;&nbsp;`description: <résumé discriminant en une ligne>`
> &nbsp;&nbsp;&nbsp;&nbsp;`metadata:`
> &nbsp;&nbsp;&nbsp;&nbsp;`  type: project        # project | reference | user | feedback`
> &nbsp;&nbsp;&nbsp;&nbsp;`  reviewed: AAAA-MM-JJ`
> &nbsp;&nbsp;&nbsp;&nbsp;`---`
>
> Le `name` doit être un **slug kebab-case** (il sert de pointeur dans `index/**` et les wikilinks ;
> le renommer casse ces liens). Un frontmatter **à plat** (`type:`/`reviewed:` de premier niveau)
> est une forme héritée : `/memory-lint` la **détecte** et la **normalise** vers le bloc `metadata:`.

Concrètement, le texte à écrire dans `docs/domain-convention.md` est (l'exemple est indenté de 4
espaces, ce qui en fait un bloc de code en markdown) :

    ## Format canonique d'un fait

    Le frontmatter **canonique** place `type` et `reviewed` sous un bloc **`metadata:`** imbriqué
    (cf. `assets/fact-template.md`) :

        ---
        name: <slug-kebab-case>
        description: <résumé discriminant en une ligne>
        metadata:
          type: project        # project | reference | user | feedback
          reviewed: AAAA-MM-JJ
        ---

    Le `name` doit être un **slug kebab-case** (il sert de pointeur dans `index/**` et les
    wikilinks ; le renommer casse ces liens). Un frontmatter **à plat** (`type:`/`reviewed:` de
    premier niveau) est une forme héritée : `/memory-lint` la **détecte** et la **normalise** vers
    le bloc `metadata:`.

- [ ] **Step 6 : Vérifier**

Run : `grep -c "memory-lint" README.md INSTALL.md docs/ARCHITECTURE.md && grep -c "Format canonique" docs/domain-convention.md`
Expected : chaque fichier ≥ 1.

- [ ] **Step 7 : Commit**

```bash
git add README.md INSTALL.md docs/ARCHITECTURE.md docs/domain-convention.md
git commit -m "docs(lint): documenter /memory-lint (README/INSTALL/ARCHITECTURE/convention)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 : Vérification

- [ ] **Step 1 : Suite complète (non-régression)**

Run : `python3 -m unittest discover -s . -p 'test_*.py' 2>&1 | tail -3`
Expected : OK — tous les tests passent (les existants + 16 de `test_lint`).

- [ ] **Step 2 : Fumée bout-en-bout sur une copie jetable**

Run :
```bash
TMP=$(mktemp -d)
printf -- '---\nname: bon-fait\ndescription: un fait propre et correctement formé pour le test\nmetadata:\n  type: project\n  reviewed: 2026-06-01\n---\nok\n' > "$TMP/a.md"
mkdir -p "$TMP/mailing"
printf -- '---\nname: herite\ndescription: un fait au format à plat à normaliser dans ce test\ntype: project\nreviewed: 2026-06-01\n---\nok\n' > "$TMP/mailing/b.md"
echo "=== rapport ===" ; python3 scripts/lint.py "$TMP"
echo "=== fix ===" ; python3 scripts/lint.py "$TMP" --fix
echo "=== re-lint (doit être propre) ===" ; python3 scripts/lint.py "$TMP"
rm -rf "$TMP"
```
Expected : le rapport signale `flat_frontmatter [auto-corrigeable]` sur `mailing/b.md` ; `--fix`
normalise 1 fait ; le re-lint affiche « ✅ Aucun problème détecté. ».

- [ ] **Step 3 : Relecture**

Vérifier de visu : `lint.py` n'utilise que la stdlib ; `apply_fixes` ne touche **que**
`flat_frontmatter` ; le skill `/memory-lint` demande confirmation avant `--fix` ; la doc §13 et la
section « Format canonique » sont cohérentes avec le moteur.

---

## Self-Review

**Couverture de la spec :**

| Élément du design | Tâche |
|---|---|
| `scripts/lint.py` : `lint_vault`, `format_report`, CLI rapport | Task 1 |
| Catalogue 6 erreurs + 7 avertissements | Task 1 (`_lint_fact`) + tests |
| Distinction plat vs imbriqué via `parse_md` | Task 1 (`metadata.type` vs `type`) + `test_flat_frontmatter_detected_fixable` |
| `duplicate_name` à l'échelle du vault | Task 1 + `test_duplicate_name` |
| `apply_fixes` (seul `flat_frontmatter`, idempotent) | Task 2 + `_normalize_frontmatter` + tests |
| CLI `--fix` | Task 2 |
| Skill `/memory-lint` (rapport → confirmation → fix → reshard) | Task 3 |
| Garde-fou advisory dans promote | Task 4 |
| Doc (README/INSTALL/ARCHITECTURE/convention) | Task 5 |
| Vérification (suite + fumée bout-en-bout) | Task 6 |

**Placeholders :** aucun — tout le code (`lint.py`, `test_lint.py`), le `SKILL.md`, les edits doc et
les insertions promote sont fournis intégralement.

**Cohérence des types/signatures :** `lint_vault(vault) -> list[Finding]`, `format_report(findings)`,
`apply_fixes(vault, findings) -> int`, `_normalize_frontmatter(text) -> (str, bool)` — mêmes
signatures partout (moteur, tests, CLI). Le `Finding` a les clés `{file, rule, severity, fixable,
message}` dans toutes les règles. `FM_RE` est défini une fois (Task 1) et réutilisé par
`_normalize_frontmatter` (Task 2). Les types valides `{project, reference, user, feedback}` sont
cohérents avec `docs/domain-convention.md`. `apply_fixes` est référencé par le `__main__` de Task 1
et défini en Task 2 (noté explicitement dans Task 1 Step 3).

**Note d'ordre :** Task 1 livre un `__main__` qui référence `apply_fixes` (défini en Task 2). Le
chemin `--fix` n'est exercé qu'en Task 2 ; les tests et la fumée de Task 1 n'utilisent que
`lint_vault`/`format_report`. C'est explicité dans Task 1 Step 3.
