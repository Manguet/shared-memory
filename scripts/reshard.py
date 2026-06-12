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

STAGING_DIRNAME = ".reshard-staging"

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


def _index_relpath_content(seg, kind, entries):
    """Renvoie (relpath, content) pour un fichier index/<seg>.md (chemin relatif au vault)."""
    lines = ["# %s" % seg, ""]
    if kind == "leaf":
        for _, name, desc, typ, rel in entries:
            lines.append("- `%s` — %s · %s → `%s`" % (name, desc, typ, rel))
    else:
        for _, label, count, child_seg in entries:
            lines.append("- %s (%d faits) → index/%s.md" % (label, count, child_seg))
    return (os.path.join("index", seg + ".md"), "\n".join(lines) + "\n")


def _ensure_memory(vault, domain_counts):
    """Crée une carte MEMORY.md minimale UNIQUEMENT si elle est absente. Ne touche JAMAIS une
    carte existante : elle est curée à la main (intro, sections « Patterns & Conventions » /
    « Général », descriptions de domaines) — la réécrire détruirait du contenu humain irremplaçable.
    La carte des domaines reste maintenue par l'humain/les skills (elle ne change qu'à la création
    d'un domaine, ce que reshard ne fait pas : il ne fait que redécouper l'intérieur des domaines)."""
    path = os.path.join(vault, "MEMORY.md")
    if os.path.exists(path):
        return
    lines = ["# Mémoire — carte des domaines", "", "## Domaines", ""]
    for domain in sorted(domain_counts):
        lines.append("- %s (%d faits) → index/%s.md" % (domain, domain_counts[domain], domain))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _plan_layout(vault, max_entries):
    """Construit en mémoire la TOTALITÉ de la nouvelle structure sans rien écrire.
    Renvoie (files, counts, reloc) où :
      - files  : [(relpath, content)] des faits shardés ET des fichiers index/** ;
      - counts : {domaine: nb_faits} ;
      - reloc  : [(relpath_racine, content)] des faits perso égarés à reloger en racine
                 (seulement ceux dont la cible n'existe pas encore)."""
    by_domain, perso = _domain_facts(vault)
    files, counts = [], {}
    for domain, facts in sorted(by_domain.items()):
        names = [f["name"] for f in facts]
        if len(names) != len(set(names)):
            raise ValueError("noms en double dans le domaine %s" % domain)
        tree = split_tree(facts, max_entries)
        placements, indexes = _materialize(tree, [domain])
        files.extend(placements)
        for seg, kind, entries in indexes:
            files.append(_index_relpath_content(seg, kind, entries))
        counts[domain] = len(facts)
    reloc = []
    for fa in perso:                        # reloger les faits perso égarés à la racine
        rel = fa["name"] + ".md"
        if not os.path.exists(os.path.join(vault, rel)):
            reloc.append((rel, fa["raw"]))
    return files, counts, reloc


def _write_all(root, items):
    """Écrit chaque (relpath, content) sous `root` (crée les dossiers). Lève si une écriture échoue."""
    for rel, content in items:
        dest = os.path.join(root, rel)
        os.makedirs(os.path.dirname(dest) or root, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(content)


def reshard(vault, max_entries=DEFAULT_MAX):
    """Applique l'invariant ≤ max_entries par dossier ; régénère `index/**`.
    PRÉSERVE la carte `MEMORY.md` curée (ne la crée que si absente). Idempotent.

    Sûreté anti perte de données : la nouvelle structure complète (faits shardés +
    `index/**`) est d'abord écrite dans un dossier de staging à l'intérieur du vault.
    Tant que TOUTES les écritures n'ont pas réussi, AUCUN fait d'origine n'est supprimé.
    Si une écriture échoue, le staging est jeté et le vault reste intact. Ce n'est qu'une
    fois le staging complet que l'on supprime l'ancienne structure puis qu'on bascule
    le staged en place. Le staging est toujours nettoyé (succès ou échec).
    Renvoie {domaine: nb_faits}."""
    files, counts, reloc = _plan_layout(vault, max_entries)

    staging = os.path.join(vault, STAGING_DIRNAME)
    shutil.rmtree(staging, ignore_errors=True)        # reste éventuel d'un run interrompu
    try:
        os.makedirs(staging)
        # 1) Écrire TOUTE la nouvelle structure dans le staging (si ça échoue, vault intact).
        _write_all(staging, files)
        # 2) Tout est écrit -> on peut maintenant supprimer l'ancienne structure...
        for domain in counts:
            shutil.rmtree(os.path.join(vault, domain), ignore_errors=True)
        shutil.rmtree(os.path.join(vault, "index"), ignore_errors=True)
        # ... puis basculer le staged en place.
        for rel, _content in files:
            src = os.path.join(staging, rel)
            dest = os.path.join(vault, rel)
            os.makedirs(os.path.dirname(dest) or vault, exist_ok=True)
            shutil.move(src, dest)
        # 3) Reloger les faits perso égarés à la racine (cibles inexistantes uniquement).
        for rel, content in reloc:
            dest = os.path.join(vault, rel)
            if not os.path.exists(dest):
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(content)
    finally:
        shutil.rmtree(staging, ignore_errors=True)    # toujours nettoyer le staging

    _ensure_memory(vault, counts)
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
