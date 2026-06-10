#!/usr/bin/env python3
"""Vérification à l'échelle de reshard : copie d'un vault source + 30 domaines synthétiques,
reshard à un seuil bas (force la récursion), puis assertions de lisibilité.

Usage: verify-scale.py <dest> [--source <clone>] [--max-entries 25]
Sort 0 si tout index <= seuil et récursion présente, 1 sinon."""
import argparse
import importlib.util
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gen = _load("gen_synth", "gen-synth-vault.py")
reshard = _load("reshard", "reshard.py")


def index_files(vault):
    out = []
    for root, _dirs, files in os.walk(os.path.join(vault, "index")):
        for fn in files:
            if fn.endswith(".md"):
                out.append(os.path.join(root, fn))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dest")
    ap.add_argument("--source", default=os.path.expanduser("~/.shared-memory/vaults/negocian-memory"))
    ap.add_argument("--max-entries", type=int, default=15)
    args = ap.parse_args()

    src = os.path.realpath(args.source) if args.source else None
    dst = os.path.realpath(args.dest)
    if src and (dst == src or src.startswith(dst + os.sep)):
        sys.exit("refus : dest (%s) est la source ou la contient" % args.dest)
    if dst == os.path.realpath(os.sep):
        sys.exit("refus : dest = racine du système")
    if os.path.exists(args.dest):
        shutil.rmtree(args.dest)
    gen.generate(args.dest, source=args.source, domains=30, fmin=120, fmax=500, seed=0)
    rcounts = reshard.reshard(args.dest, max_entries=args.max_entries)

    idx = os.path.join(args.dest, "index")
    files = index_files(args.dest)
    over = []
    maxdepth = 0
    for f in files:
        entries = [l for l in open(f, encoding="utf-8").read().splitlines() if l.startswith("- ")]
        if len(entries) > args.max_entries:
            over.append((os.path.relpath(f, args.dest), len(entries)))
        maxdepth = max(maxdepth, len(os.path.relpath(f, idx).split(os.sep)))

    total_facts = sum(rcounts.values())
    print("Domaines: %d | faits totaux: %d | fichiers d'index: %d | profondeur max: %d | seuil: %d"
          % (len(rcounts), total_facts, len(files), maxdepth, args.max_entries))
    if over:
        print("ÉCHEC — index au-dessus du seuil :", over[:5])
        sys.exit(1)
    if maxdepth < 3:
        print("ÉCHEC — pas de récursion réelle : profondeur %d < 3 (un sous-domaine devrait "
              "lui-même être scindé). Baisse --max-entries ou augmente la taille des domaines." % maxdepth)
        sys.exit(1)
    print("OK — tous les index ≤ %d lignes ; récursion réelle (profondeur %d : un sous-domaine "
          "est lui-même redécoupé en sous-domaines)." % (args.max_entries, maxdepth))


if __name__ == "__main__":
    main()
