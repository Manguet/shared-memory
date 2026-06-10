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
    """Top-k (file, score) par cosine décroissant. Vectorisé via numpy si dispo (rapide à
    grande échelle ; le cosine pur Python coûte ~550 ms sur ~9000 vecteurs), sinon pur Python."""
    items = [(f, rec["vec"]) for f, rec in store.items() if "vec" in rec]
    if not items:
        return []
    try:
        import numpy as np
        files = [f for f, _ in items]
        mat = np.asarray([v for _, v in items], dtype=np.float32)      # (n, d)
        q = np.asarray(query_vec, dtype=np.float32)                    # (d,)
        denom = np.linalg.norm(mat, axis=1) * np.linalg.norm(q)
        sims = np.divide(mat @ q, denom, out=np.zeros(len(items), dtype=np.float32),
                         where=denom > 0)
        top = np.argsort(-sims, kind="stable")[:k]
        return [(files[i], float(sims[i])) for i in top]
    except Exception:
        scored = [(f, cosine(query_vec, v)) for f, v in items]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:k]


def grep_matches(query, facts):
    """Fichiers dont name+description+body contient `query` (insensible casse).
    Même logique que /search du viewer (serve-viewer.py)."""
    q = (query or "").strip().lower()
    if not q:
        return []
    out = []
    for f in facts:
        hay = " ".join((f.get("name", ""), f.get("description", ""), f.get("body", ""))).lower()
        if q in hay:
            out.append(f["file"])
    return out


def _pointer(fact, score):
    return {"file": fact["file"], "name": fact.get("name", ""),
            "path": fact.get("path", []), "score": score}


def search(query, facts, store, embed_fn, k=8):
    """Recherche hybride -> {"results": [pointeurs], "vector_inactive": bool}.

    - embed_fn None : grep seul, vector_inactive=True.
    - embed_fn fourni : top-k sémantique PUIS union des matches grep exacts, dédupliqué
      (exhaustivité : un terme exact présent n'est jamais raté).
    Ne renvoie JAMAIS de body : l'outil aiguille, le fait est la source.
    """
    by_file = {f["file"]: f for f in facts}
    grep_files = grep_matches(query, facts)
    if embed_fn is None:
        results = [_pointer(by_file[fp], None) for fp in grep_files if fp in by_file]
        return {"results": results, "vector_inactive": True}
    qvec = embed_fn([query])[0]
    ordered, seen = [], set()
    for file, score in semantic_topk(qvec, store, k):
        if file in by_file and file not in seen:
            ordered.append(_pointer(by_file[file], round(score, 4)))
            seen.add(file)
    for fp in grep_files:
        if fp in by_file and fp not in seen:
            ordered.append(_pointer(by_file[fp], None))
            seen.add(fp)
    return {"results": ordered, "vector_inactive": False}


# Modèle multilingue (FR inclus), 384 dims, ~225 Mo — local, sans préfixe spécial.
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def load_fastembed_embed_fn():
    """Renvoie un embed_fn fastembed, ou None si fastembed indisponible.
    Import GARDÉ : aucune dépendance au niveau module ; ne lève jamais."""
    try:
        from fastembed import TextEmbedding
    except Exception:
        return None
    try:
        # cache PERSISTANT (sinon fastembed télécharge dans /tmp, effacé au reboot → re-download)
        cache = os.path.join(os.path.expanduser("~"), ".shared-memory", "models")
        os.makedirs(cache, exist_ok=True)
        model = TextEmbedding(model_name=EMBED_MODEL, cache_dir=cache)  # multilingue, local
    except Exception:
        return None
    def embed_fn(texts):
        return [[float(x) for x in v] for v in model.embed(list(texts))]
    return embed_fn
