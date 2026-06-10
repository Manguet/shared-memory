#!/usr/bin/env python3
"""Recherche mémoire : embeddings locaux OPTIONNELS + hybride grep.

Cœur pur et testable : `embed_fn` est INJECTÉ (aucun import fastembed au niveau module).
embed_fn(list[str]) -> list[list[float]]. Si embed_fn is None, `search` (Task 4) retombe
sur le grep et signale vector_inactive.
"""
import hashlib
import json
import math
import os


def fact_text(fact):
    """Texte embeddé/hashé d'un fait : name + description + body."""
    return "\n".join((fact.get("name", ""), fact.get("description", ""), fact.get("body", "")))


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_store(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_store(path, store):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f)
    os.replace(tmp, path)


def refresh_store(facts, store, embed_fn):
    """Store à jour {file: {hash, vec}} ; ne (ré)embedde que les hash changés (lazy).
    Les faits disparus sortent du store. embed_fn(list[str]) -> list[list[float]]."""
    fresh, to_embed, keys = {}, [], []
    for fact in facts:
        h = content_hash(fact_text(fact))
        prev = store.get(fact["file"])
        if prev and prev.get("hash") == h and "vec" in prev:
            fresh[fact["file"]] = prev
        else:
            to_embed.append(fact_text(fact))
            keys.append((fact["file"], h))
    if to_embed:
        vecs = embed_fn(to_embed)
        for (file, h), vec in zip(keys, vecs):
            fresh[file] = {"hash": h, "vec": [float(x) for x in vec]}
    return fresh


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


def semantic_topk(query_vec, store, k):
    """Top-k (file, score) par cosine décroissant."""
    scored = [(file, cosine(query_vec, rec["vec"]))
              for file, rec in store.items() if "vec" in rec]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:k]
