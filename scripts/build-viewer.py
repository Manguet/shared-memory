#!/usr/bin/env python3
"""Construit un viewer HTML autonome (lecture seule) à partir d'un vault mémoire.

Usage: build-viewer.py <vault-dir> <output-html> <template-html>
Lit chaque fichier .md du vault (frontmatter + corps), injecte les données dans
le template et écrit un fichier HTML autonome. Imprime le chemin de sortie.
"""
import json
import os
import re
import sys


def parse_md(path):
    """Renvoie (frontmatter_dict, body) pour un fichier markdown.

    Gère le frontmatter imbriqué sur un niveau : un bloc `metadata:` suivi de lignes
    indentées `  type: project` produit la clé plate `metadata.type`. Les clés de premier
    niveau restent telles quelles. Évite la capture accidentelle d'une clé `type` indentée.
    """
    text = open(path, encoding="utf-8").read()
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


def collect_facts(vault):
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
            facts.append({
                "file": rel,
                "name": fm.get("name", fn[:-3]),
                "description": fm.get("description", ""),
                "type": fm.get("metadata.type") or fm.get("type", "project"),
                "domain": domain,
                "path": path,
                "body": body,
            })
    facts.sort(key=lambda f: (f["domain"], f["name"]))
    return facts, index_body


def main():
    vault = sys.argv[1]
    out = sys.argv[2]
    tmpl = sys.argv[3]
    facts, index_body = collect_facts(vault)
    data = {"facts": facts, "index": index_body, "vault": vault, "count": len(facts)}
    html = open(tmpl, encoding="utf-8").read()
    html = html.replace("/*__DATA__*/", json.dumps(data, ensure_ascii=False))
    open(out, "w", encoding="utf-8").write(html)
    print(out)


if __name__ == "__main__":
    main()
