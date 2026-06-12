#!/usr/bin/env python3
"""Digest mémoire au démarrage : description compacte d'un vault, bornée.

`build_digest(vault, max_lines=120, today=None) -> str` réutilise `collect_facts`
(de build-viewer.py) et la règle de péremption SP2 (STALE_DAYS=90). Pur lecture de
fichiers, aucun fastembed. Émis par `hook-memory.sh start` au SessionStart.

- Sous le budget (len(facts) <= max_lines) : une ligne par fait, groupée par domaine,
  avec ⚠ si périmé ; inclut la section « Patterns & Conventions » de MEMORY.md.
- Au-dessus : digest dégradé (domaines + comptes + renvoi search_memory/-list).
- Vault vide : chaîne vide (rien à émettre).
"""
import datetime
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "build_viewer", os.path.join(_HERE, "build-viewer.py")
)
_bv = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_bv)

_SPEC_STALE = importlib.util.spec_from_file_location(
    "stale", os.path.join(_HERE, "stale.py")
)
_stale = importlib.util.module_from_spec(_SPEC_STALE)
_SPEC_STALE.loader.exec_module(_stale)

STALE_DAYS = _stale.STALE_DAYS


def _is_stale(reviewed, today):
    """Délègue à la source unique de la péremption (scripts/stale.py)."""
    return _stale.is_stale(reviewed, today)


def _patterns_section(index_body):
    """Renvoie la section markdown dont le titre contient « Patterns » (sinon "")."""
    lines = index_body.splitlines()
    out, capturing = [], False
    for line in lines:
        is_heading = line.startswith("#")
        if is_heading and "pattern" in line.lower():
            capturing = True
            out.append(line)
            continue
        if capturing and is_heading:   # heading suivant -> fin de section
            break
        if capturing:
            out.append(line)
    return "\n".join(out).strip()


def _count(n, word):
    """« 1 fait », « 2 faits » — pluriel français simple (ajout d'un -s au pluriel)."""
    return "%d %s%s" % (n, word, "s" if n > 1 else "")


def build_digest(vault, max_lines=120, today=None):
    today = today or datetime.date.today()
    facts, index_body = _bv.collect_facts(vault, include_body=False)
    n = len(facts)
    if n == 0:
        return ""

    by_domain = {}
    for f in facts:
        by_domain.setdefault(f["domain"], []).append(f)
    domains = sorted(by_domain)

    if n > max_lines:
        lines = ["## Mémoire d'équipe (%s, %s) — digest complet trop volumineux"
                 % (_count(n, "fait"), _count(len(domains), "domaine"))]
        for d in domains:
            lines.append("- %s — %s" % (d, _count(len(by_domain[d]), "fait")))
        lines.append("Pour le détail, utilise `search_memory` (MCP) ou `/memory-list`.")
        return "\n".join(lines)

    lines = ["## Mémoire d'équipe (%s)" % _count(n, "fait")]
    for d in domains:
        lines.append("")
        lines.append("### %s" % d)
        for f in by_domain[d]:
            warn = "⚠ " if _is_stale(f["reviewed"], today) else ""
            lines.append("- %s`%s` — %s · %s" % (warn, f["name"], f["description"], f["type"]))

    patterns = _patterns_section(index_body)
    if patterns:
        lines.append("")
        lines.append(patterns)

    return "\n".join(lines)


def build_summary(vault, max_domains=6):
    """Ligne unique « N faits (domaine1, domaine2, …) » pour le rappel compact du hook.

    Réutilise collect_facts ; vault vide -> "". Tronque au-delà de max_domains avec « … »."""
    facts, _ = _bv.collect_facts(vault, include_body=False)
    n = len(facts)
    if n == 0:
        return ""
    domains = sorted({f["domain"] for f in facts})
    shown = domains[:max_domains]
    if len(domains) > max_domains:
        shown.append("…")
    return "%s (%s)" % (_count(n, "fait"), ", ".join(shown))


if __name__ == "__main__":
    args = sys.argv[1:]
    summary = "--summary" in args
    rest = [a for a in args if a != "--summary"]
    vault = rest[0] if rest else "."
    out = build_summary(vault) if summary else build_digest(vault)
    if out:
        print(out)
