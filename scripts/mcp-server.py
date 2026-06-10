#!/usr/bin/env python3
"""Serveur MCP (stdio) exposant `search_memory` pour Claude Code.

Renvoie des POINTEURS de faits (jamais de body) : l'outil aiguille, le fait est la source.
Sémantique optionnelle (fastembed) ; fallback grep si absente (vector_inactive=true).
JSON-RPC 2.0 minimal, newline-delimited, stdlib pur.
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


bv = _load("build_viewer", "build-viewer.py")
embed = _load("embed", "embed.py")
paths = _load("sm_paths", "sm_paths.py")

PROTOCOL_VERSION = "2025-06-18"
TOOL = {
    "name": "search_memory",
    "description": (
        "Cherche des FAITS dans la mémoire d'équipe du projet et renvoie des POINTEURS "
        "(file, name, path, score) — JAMAIS le contenu. Lis ensuite chaque fait pointé avant "
        "d'affirmer quoi que ce soit : l'outil aiguille, le fait est la source. Si "
        "vector_inactive=true, la recherche sémantique est inactive (fallback grep) — signale-le "
        "à l'utilisateur et propose `pip install fastembed`."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Termes ou question."},
            "k": {"type": "integer", "description": "Nb de pointeurs (défaut 8).", "default": 8},
        },
        "required": ["query"],
    },
}


def handle_request(req, runner):
    """Dispatch JSON-RPC. `runner(query, k) -> dict` exécute la recherche (injecté → testable).
    Renvoie un dict réponse, ou None pour une notification (pas de réponse)."""
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        client_pv = (req.get("params") or {}).get("protocolVersion", PROTOCOL_VERSION)
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": client_pv,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "shared-memory", "version": "0.1.0"},
        }}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": [TOOL]}}
    if method == "tools/call":
        params = req.get("params") or {}
        if params.get("name") != "search_memory":
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32602, "message": "unknown tool"}}
        args = params.get("arguments") or {}
        out = runner(args.get("query", ""), int(args.get("k", 8) or 8))
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}]
        }}
    if rid is None:
        return None
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": -32601, "message": "method not found: %s" % method}}


def build_context():
    """Résout le vault du projet courant. Renvoie {'slug','vault'} ou {'error': ...}."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    s = paths.slug(project_dir)
    vault = paths.vault_clone_for_slug(s)
    if not vault or not os.path.isdir(vault):
        return {"error": "vault introuvable pour ce projet ; lance /memory-setup."}
    return {"slug": s, "vault": vault}


def run_search(ctx, query, k):
    """Charge les faits, rafraîchit le store si fastembed dispo, renvoie la recherche hybride."""
    facts, _ = bv.collect_facts(ctx["vault"], include_body=True)
    embed_fn = embed.load_fastembed_embed_fn()
    store = {}
    if embed_fn is not None:
        store_path = paths.store_path_for_slug(ctx["slug"])
        store = embed.refresh_store(facts, embed.load_store(store_path), embed_fn)
        embed.save_store(store_path, store)
    return embed.search(query, facts, store, embed_fn, k)


def main():
    ctx = build_context()

    def runner(query, k):
        if "error" in ctx:
            return {"results": [], "vector_inactive": True, "error": ctx["error"]}
        return run_search(ctx, query, k)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        resp = handle_request(req, runner)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
