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
        for fn in files:
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
    parsed = {}
    names = {}
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
