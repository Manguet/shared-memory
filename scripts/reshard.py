#!/usr/bin/env python3
"""Redécoupage automatique d'un vault en sous-domaines (invariant ≤ N par dossier).

Restructure les faits sur disque puis régénère tout `index/**` + `MEMORY.md`.
Réutilise collect_facts/parse_md de build-viewer.py. Pur fichiers, zéro dépendance.
"""
import argparse
import importlib.util
import math
import os
import re
import shutil

STAGING_DIRNAME = ".reshard-staging"

PART_RE = re.compile(r"^part-\d+$")

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


def _semantic_segments(path):
    """Chemin de dossiers sémantique d'un fait : son path moins les segments `part-NN`."""
    return [s for s in path if not PART_RE.match(s)]


def _semantic_tree(vault):
    """Arbre des dossiers sémantiques. Renvoie (root, perso, local).
    root : {domaine: node} ; node = {'facts': [...], 'children': {nom: node}}.
    perso : faits user/feedback égarés en domaine (relogés en racine).
    local : [(relpath, raw)] des faits `metadata.local: true` — passthrough : réécrits à leur
            place, hors arbre/index/seuil (sinon le rmtree(vault/<domaine>) les détruirait)."""
    facts, _ = bv.collect_facts(vault, include_body=False)
    root, perso, local = {}, [], []
    for fa in facts:
        if fa.get("local"):        # fait local (racine ou domaine) : passthrough, hors arbre/index/seuil
            local.append((fa["file"], _read_raw(os.path.join(vault, fa["file"]))))
            continue
        if not fa["path"]:
            continue
        raw = _read_raw(os.path.join(vault, fa["file"]))
        fa = dict(fa, raw=raw)
        if fa["type"] in ("user", "feedback"):
            perso.append(fa)
            continue
        segs = _semantic_segments(fa["path"])
        if not segs:
            continue
        children = root
        node = None
        for s in segs:
            node = children.setdefault(s, {"facts": [], "children": {}})
            children = node["children"]
        node["facts"].append(fa)
    return root, perso, local


def _count_node_facts(node):
    """Total des faits sous un nœud sémantique (directs + tous descendants)."""
    return len(node["facts"]) + sum(_count_node_facts(c) for c in node["children"].values())


def _count_leaf_facts(node):
    if "leaf" in node:
        return len(node["leaf"])
    return sum(_count_leaf_facts(c) for c in node["children"])


def _materialize(node, segments):
    """Matérialise un sous-arbre `split_tree` (faits) en part-NN. Renvoie (placements, indexes).
    placements : [(relpath, raw)]. indexes : [(seg, entries)] ; entries taguées ('fact'|'node')."""
    seg = "/".join(segments)
    placements, indexes, entries = [], [], []
    if "leaf" in node:
        for fa in node["leaf"]:
            rel = seg + "/" + fa["name"] + ".md"
            placements.append((rel, fa["raw"]))
            entries.append(("fact", fa["name"], fa["description"], fa["type"], rel))
    else:
        children = node["children"]
        w = max(2, len(str(len(children))))
        for i, child in enumerate(children):
            label = "part-%0*d" % (w, i + 1)
            child_seg = segments + [label]
            sub_p, sub_i = _materialize(child, child_seg)
            placements.extend(sub_p)
            indexes.extend(sub_i)
            entries.append(("node", label, _count_leaf_facts(child), "/".join(child_seg)))
    indexes.append((seg, entries))
    return placements, indexes


def _materialize_semantic(node, segments, max_entries):
    """Matérialise un nœud sémantique : faits directs (leaf ou part-NN si débordement) + enfants
    sémantiques. Renvoie (placements, indexes) ; l'index du nœud est MIXTE (faits + nœuds)."""
    seg = "/".join(segments)
    placements, indexes, entries = [], [], []
    direct = sorted(node["facts"], key=lambda f: f["name"])
    names = [f["name"] for f in direct]
    if len(names) != len(set(names)):
        raise ValueError("noms en double dans %s" % seg)
    collide = set(names) & set(node["children"])
    if collide:
        raise ValueError("un fait masque un sous-domaine homonyme dans %s : %s"
                         % (seg, ", ".join(sorted(collide))))
    if direct:
        if len(direct) <= max_entries:
            for fa in direct:
                rel = seg + "/" + fa["name"] + ".md"
                placements.append((rel, fa["raw"]))
                entries.append(("fact", fa["name"], fa["description"], fa["type"], rel))
        else:
            sub = split_tree(direct, max_entries)["children"]
            w = max(2, len(str(len(sub))))
            for i, child in enumerate(sub):
                label = "part-%0*d" % (w, i + 1)
                child_seg = segments + [label]
                sub_p, sub_i = _materialize(child, child_seg)
                placements.extend(sub_p)
                indexes.extend(sub_i)
                entries.append(("node", label, _count_leaf_facts(child), "/".join(child_seg)))
    for cname in sorted(node["children"]):
        child_seg = segments + [cname]
        sub_p, sub_i = _materialize_semantic(node["children"][cname], child_seg, max_entries)
        placements.extend(sub_p)
        indexes.extend(sub_i)
        entries.append(("node", cname, _count_node_facts(node["children"][cname]),
                        "/".join(child_seg)))
    indexes.append((seg, entries))
    return placements, indexes


def _index_relpath_content(seg, entries):
    """(relpath, content) pour index/<seg>.md ; entries mixtes ('fact'|'node')."""
    lines = ["# %s" % seg, ""]
    for e in entries:
        if e[0] == "fact":
            _, name, desc, typ, rel = e
            lines.append("- `%s` — %s · %s → `%s`" % (name, desc, typ, rel))
        else:
            _, label, count, child_seg = e
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
    root, perso, local = _semantic_tree(vault)
    files, counts = [], {}
    for domain in sorted(root):
        placements, indexes = _materialize_semantic(root[domain], [domain], max_entries)
        files.extend(placements)
        for seg, entries in indexes:
            files.append(_index_relpath_content(seg, entries))
        counts[domain] = _count_node_facts(root[domain])
    placed = {rel for rel, _ in files}
    for rel, _raw in local:
        if rel in placed:
            raise ValueError("collision : le fait local « %s » entre en conflit avec un fait placé" % rel)
    files.extend(local)        # faits locaux : réécrits à leur chemin d'origine, hors index/counts
    reloc = []
    for fa in perso:
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
