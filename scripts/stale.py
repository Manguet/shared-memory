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
    # 1) une ligne `reviewed:` existe (indentée ou à plat) -> remplacer sa valeur
    for i, ln in enumerate(lines):
        mm = re.match(r"^(\s*)reviewed\s*:\s*.*$", ln)
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
        lines.append("- [%s] `%s` — %s · %s → %s"
                     % (age, f["name"], f["description"], f["type"], f["file"]))
    lines.append("(Le `→ chemin` est relatif au vault — utilisable tel quel avec --restamp.)")
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
        if len(argv) < 2:
            print("Usage: stale.py --restamp <fichier> [date]", file=sys.stderr)
            sys.exit(1)
        path = argv[1]
        date = argv[2] if len(argv) > 2 else datetime.date.today().isoformat()
        _restamp_file(path, date)
        print("reviewed=%s -> %s" % (date, path))
    else:
        vault = argv[0] if argv else "."
        print(_format_list(stale_facts(vault)))
