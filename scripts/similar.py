#!/usr/bin/env python3
"""Quasi-doublons sémantiques d'un texte candidat dans un vault. Réutilise embed.find_similar.

Usage : similar.py <vault> --text "<texte>" [--threshold 0.80] [--exclude <file>]
Imprime un JSON {"similar": [...], "vector_inactive": bool}.
"""
import argparse
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bv = _load("build_viewer", "build-viewer.py")
embed = _load("embed", "embed.py")


def run(vault, text, threshold=0.80, exclude=None, embed_fn="auto"):
    """`embed_fn="auto"` charge fastembed ; passer un factice pour les tests, ou None."""
    facts, _ = bv.collect_facts(vault, include_body=True)
    if embed_fn == "auto":
        embed_fn = embed.load_fastembed_embed_fn()
    store = {} if embed_fn is None else embed.refresh_store(facts, {}, embed_fn)
    return embed.find_similar(text, facts, store, embed_fn, threshold=threshold, exclude=exclude)


def main():
    ap = argparse.ArgumentParser(description="Quasi-doublons d'un texte candidat dans un vault.")
    ap.add_argument("vault")
    ap.add_argument("--text", required=True)
    ap.add_argument("--threshold", type=float, default=0.80)
    ap.add_argument("--exclude", default=None)
    args = ap.parse_args()
    print(json.dumps(run(args.vault, args.text, args.threshold, args.exclude), ensure_ascii=False))


if __name__ == "__main__":
    main()
