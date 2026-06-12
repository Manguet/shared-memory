#!/usr/bin/env python3
"""Harnais d'évaluation du rappel : le bon fait remonte-t-il au bon moment ?

Mesure, pour des cas {query, expect}, si le fait attendu ressort dans le top-k via le VRAI chemin
de recherche (embed.search, comme search_memory). Métriques : recall@k, MRR, rang #1
(discriminabilité). Diagnostique (pas de seuil). Réutilise embed.py / build-viewer.py.

CLI :
  python3 eval-recall.py <vault> [--k 8]                 -> éval auto (description -> fait)
  python3 eval-recall.py <vault> --cases cas.json [--k 8] -> éval des cas fournis
"""
import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_bv = _load("build_viewer", "build-viewer.py")
_embed = _load("embed", "embed.py")


def recall_at_k(ranked, expected, k):
    """Vrai si `expected` est dans les k premiers de `ranked`."""
    return expected in ranked[:k]


def reciprocal_rank(ranked, expected):
    """1/rang (1-indexé) si `expected` est trouvé, sinon 0.0."""
    for i, name in enumerate(ranked, start=1):
        if name == expected:
            return 1.0 / i
    return 0.0


def eval_cases(cases, query_fn, k):
    """Agrège l'éval sur des cas {query, expect}. `query_fn(query) -> [noms classés]`."""
    n = len(cases)
    hits = 0
    rr_sum = 0.0
    rank1 = 0
    misses = []
    for c in cases:
        ranked = query_fn(c["query"])
        expected = c["expect"]
        rr = reciprocal_rank(ranked, expected)
        rr_sum += rr
        if rr == 1.0:
            rank1 += 1
        if recall_at_k(ranked, expected, k):
            hits += 1
        else:
            misses.append({"query": c["query"], "expect": expected})
    return {
        "n": n,
        "hits": hits,
        "recall_pct": round(100 * hits / n) if n else 0,
        "mrr": round(rr_sum / n, 3) if n else 0.0,
        "rank1": rank1,
        "misses": misses,
    }


def auto_cases(facts):
    """Éval automatique : chaque fait -> {query: sa description, expect: son nom}.

    Ignore les faits sans description (rien à interroger)."""
    out = []
    for f in facts:
        desc = (f.get("description") or "").strip()
        name = f.get("name")
        if desc and name:
            out.append({"query": desc, "expect": name})
    return out


def _format_report(report, k, vector_inactive):
    lines = []
    if vector_inactive:
        lines.append("⚠ fastembed absent — recall mesuré en lexical (grep), proxy faible ; "
                     "lance /memory-doctor pour l'éval sémantique.")
    mode = "grep (proxy faible)" if vector_inactive else "sémantique"
    lines.append("Éval rappel — %d cas, k=%d, mode %s" % (report["n"], k, mode))
    lines.append("recall@k : %d/%d (%d%%)" % (report["hits"], report["n"], report["recall_pct"]))
    lines.append("MRR      : %.3f" % report["mrr"])
    lines.append("rang #1  : %d/%d (discriminabilité)" % (report["rank1"], report["n"]))
    if report["misses"]:
        lines.append("Ratés (fait absent du top-k) :")
        for m in report["misses"]:
            lines.append('- "%s" → attendu `%s`' % (m["query"], m["expect"]))
    return "\n".join(lines)


def search_query_fn(vault, k=8, embed_fn="auto"):
    """Renvoie (query_fn, vector_inactive, facts) basé sur le VRAI chemin de recherche (embed.search).

    `embed_fn="auto"` charge fastembed si dispo (None -> repli grep). Injectable pour les tests.
    `facts` (chargés une fois) sont renvoyés pour éviter une relecture du vault (auto_cases)."""
    facts, _ = _bv.collect_facts(vault, include_body=True)
    if embed_fn == "auto":
        embed_fn = _embed.load_fastembed_embed_fn()
    store = {}
    vector_inactive = embed_fn is None
    if embed_fn is not None:
        try:
            store = _embed.refresh_store(facts, {}, embed_fn)
        except Exception:
            embed_fn, store, vector_inactive = None, {}, True

    def query_fn(query):
        res = _embed.search(query, facts, store, embed_fn, k)
        return [r["name"] for r in res["results"]]

    return query_fn, vector_inactive, facts


if __name__ == "__main__":
    argv = sys.argv[1:]
    k = 8
    cases_file = None
    positional = []
    i = 0
    while i < len(argv):
        if argv[i] == "--k" and i + 1 < len(argv):
            k = int(argv[i + 1]); i += 2
        elif argv[i] == "--cases" and i + 1 < len(argv):
            cases_file = argv[i + 1]; i += 2
        else:
            positional.append(argv[i]); i += 1
    vault = positional[0] if positional else "."
    query_fn, vector_inactive, facts = search_query_fn(vault, k)
    if cases_file:
        with open(cases_file, encoding="utf-8") as fh:
            cases = json.load(fh)
    else:
        cases = auto_cases(facts)
    report = eval_cases(cases, query_fn, k)
    print(_format_report(report, k, vector_inactive))
