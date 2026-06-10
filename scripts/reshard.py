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
    if n < 2:
        raise ValueError("max_entries doit être ≥ 2 (un seuil de 1 n'a pas de sens hiérarchique)")
    if len(items) <= n:
        return {"leaf": list(items)}
    k = min(n, math.ceil(len(items) / n))
    return {"children": [split_tree(c, n) for c in balanced_chunks(items, k)]}


def _read_raw(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _domain_facts(vault):
    """Groupe les faits par domaine de 1er niveau (path non vide). Faits racine ignorés.
    Les faits perso (type user/feedback) égarés dans un domaine sont renvoyés à part pour
    être relogés en racine (jamais shardés). Chaque fait porte 'raw', trié par name."""
    facts, _ = bv.collect_facts(vault, include_body=False)
    by_domain, perso = {}, []
    for fa in facts:
        if not fa["path"]:                  # fait déjà à la racine -> laissé tel quel
            continue
        fa = dict(fa, raw=_read_raw(os.path.join(vault, fa["file"])))
        if fa["type"] in ("user", "feedback"):
            perso.append(fa)                # perso égaré dans un domaine -> à reloger en racine
            continue
        by_domain.setdefault(fa["path"][0], []).append(fa)
    for d in by_domain:
        by_domain[d].sort(key=lambda f: f["name"])
    return by_domain, perso


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
    by_domain, perso = _domain_facts(vault)
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
    for domain in by_domain:
        shutil.rmtree(os.path.join(vault, domain), ignore_errors=True)
    shutil.rmtree(os.path.join(vault, "index"), ignore_errors=True)
    for fa in perso:                        # reloger les faits perso égarés à la racine
        dest = os.path.join(vault, fa["name"] + ".md")
        if not os.path.exists(dest):
            with open(dest, "w", encoding="utf-8") as f:
                f.write(fa["raw"])
    for rel, raw in all_placements:
        dest = os.path.join(vault, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(raw)
    for seg, kind, entries in all_indexes:
        _write_index(vault, seg, kind, entries)
    _write_memory(vault, counts)
    return counts


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
