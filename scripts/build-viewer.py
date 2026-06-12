#!/usr/bin/env python3
"""Lecture d'un vault mémoire : `parse_md` + `collect_facts`.

Module utilitaire (plus de CLI). Importé par `serve-viewer.py`, qui sert le viewer.
`collect_facts(vault, include_body=True)` parcourt récursivement le vault et renvoie
`(facts, index_body)` ; chaque fait porte file/name/description/type/domain/path (+ body).
"""
import os
import re


def parse_md(path):
    """Renvoie (frontmatter_dict, body) pour un fichier markdown.

    Gère le frontmatter imbriqué sur un niveau : un bloc `metadata:` suivi de lignes
    indentées `  type: project` produit la clé plate `metadata.type`. Les clés de premier
    niveau restent telles quelles. Évite la capture accidentelle d'une clé `type` indentée.
    """
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fm, body = {}, text
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if m:
        block, body = m.group(1), m.group(2)
        parent = None
        for line in block.splitlines():
            if not line.strip():
                continue
            indented = line[0] in " \t"
            mm = re.match(r"\s*([\w.\-]+)\s*:\s*(.*?)\s*$", line)
            if not mm:
                continue
            key, val = mm.group(1), mm.group(2).strip()
            if indented and parent:
                fm["%s.%s" % (parent, key)] = val
            else:
                fm[key] = val
                parent = key if val == "" else None
    return fm, body.strip()


def collect_facts(vault, include_body=True):
    """Renvoie (facts, index_body) en parcourant récursivement le vault.

    - `MEMORY.md` à la racine -> index_body (la carte).
    - tout `.md` sous `index/` -> ignoré (sous-index niveau 1).
    - tout autre `.md` -> un fait ; `domain` = 1er segment du chemin relatif
      s'il est dans un sous-dossier, sinon « général » (faits à la racine = mode mixte).
    `file` = chemin relatif au vault (unique même entre domaines).
    """
    facts, index_body = [], ""
    for root, _dirs, files in os.walk(vault):
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, vault)
            parts = rel.split(os.sep)
            if rel == "MEMORY.md":   # racine uniquement ; un sous/MEMORY.md devient un fait normal
                _, index_body = parse_md(full)
                continue
            if parts[0] == "index":  # sous-index niveau 1 (index/<domaine>.md) -> jamais un fait
                continue
            domain = parts[0] if len(parts) > 1 else "général"
            path = parts[:-1]   # segments du dossier (arbre N-niveaux) ; [] à la racine
            fm, body = parse_md(full)
            fact = {
                "file": rel,
                "name": fm.get("name", fn[:-3]),
                "description": fm.get("description", ""),
                "type": fm.get("metadata.type") or fm.get("type", "project"),
                "reviewed": fm.get("metadata.reviewed") or fm.get("reviewed", ""),
                "domain": domain,
                "path": path,
            }
            if include_body:
                fact["body"] = body
            facts.append(fact)
    facts.sort(key=lambda f: (f["domain"], f["name"]))
    return facts, index_body
