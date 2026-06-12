#!/usr/bin/env python3
"""Serveur local (lecture seule) du vault mémoire.

Usage: serve-viewer.py <vault-dir> <template-html> [port]
- GET /            -> HTML du viewer + index métadonnées (sans body)
- GET /fact?f=…    -> body d'UN fait (chemin validé : reste dans le vault, .md)
- GET /search?q=…  -> grep full-text sur les faits, renvoie les métadonnées matchantes
Bind 127.0.0.1 uniquement.
"""
import datetime
import importlib.util
import json
import os
import re
import secrets
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bv = _load("build_viewer", "build-viewer.py")
reshard = _load("reshard", "reshard.py")
embed = _load("embed", "embed.py")

SLUG_RE = re.compile(r"^[a-z0-9-]+$")
TYPES = {"project", "reference", "user", "feedback"}


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _fact_text(name, description, type_, body, reviewed=None):
    reviewed = reviewed or datetime.date.today().isoformat()
    return ("---\nname: %s\ndescription: %s\nmetadata:\n  type: %s\n  reviewed: %s\n---\n%s\n"
            % (name, description, type_, reviewed, body))


def _validate(data):
    name = (data.get("name") or "").strip()
    typ = (data.get("type") or "").strip()
    if not SLUG_RE.match(name):
        raise ApiError(400, "nom invalide (slug attendu : a-z 0-9 -)")
    if typ not in TYPES:
        raise ApiError(400, "type invalide")
    domain = (data.get("domain") or "").strip()
    if typ in ("user", "feedback"):
        domain = ""
    elif domain and not SLUG_RE.match(domain):
        raise ApiError(400, "domaine invalide (slug attendu)")
    desc = (data.get("description") or "").replace("\r", " ").replace("\n", " ").strip()
    return name, typ, domain, desc, data.get("body", "") or ""


def _rel_for(name, domain):
    return (domain + "/" + name + ".md") if domain else (name + ".md")


def _safe_path(vault, rel):
    vault_real = os.path.realpath(vault)
    try:
        full = os.path.realpath(os.path.join(vault, rel))
    except (ValueError, OSError):
        raise ApiError(404, "chemin invalide")
    inside = full == vault_real or full.startswith(vault_real + os.sep)
    if not rel or not inside or not full.endswith(".md"):
        raise ApiError(404, "chemin hors vault")
    return full


def _metadata(vault):
    facts, index_body = bv.collect_facts(vault, include_body=False)
    return {"facts": facts, "index": index_body, "vault": vault, "count": len(facts)}


def create_fact(vault, data):
    name, typ, domain, desc, body = _validate(data)
    full = _safe_path(vault, _rel_for(name, domain))
    if os.path.exists(full):
        raise ApiError(400, "un fait « %s » existe déjà ici" % name)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(_fact_text(name, desc, typ, body))
    reshard.reshard(vault)
    return _metadata(vault)


def update_fact(vault, file, data):
    old = _safe_path(vault, file)
    if not os.path.isfile(old):
        raise ApiError(404, "fait introuvable")
    name, typ, domain, desc, body = _validate(data)
    new = _safe_path(vault, _rel_for(name, domain))
    if new != old and os.path.exists(new):
        raise ApiError(400, "un fait « %s » existe déjà à cet emplacement" % name)
    os.makedirs(os.path.dirname(new), exist_ok=True)
    with open(new, "w", encoding="utf-8") as f:
        f.write(_fact_text(name, desc, typ, body))
    if new != old:
        os.remove(old)
    reshard.reshard(vault)
    return _metadata(vault)


def delete_fact(vault, file):
    full = _safe_path(vault, file)
    if not os.path.isfile(full):
        raise ApiError(404, "fait introuvable")
    os.remove(full)
    reshard.reshard(vault)
    return _metadata(vault)


def _safe_dir(vault, name):
    vault_real = os.path.realpath(vault)
    full = os.path.realpath(os.path.join(vault, name))
    inside = full.startswith(vault_real + os.sep)
    if not name or not inside:
        raise ApiError(404, "domaine hors vault")
    return full


def _patch_memory_domain(vault, old, new):
    path = os.path.join(vault, "MEMORY.md")
    if not os.path.isfile(path):
        return
    ptr_old, ptr_new = "index/%s.md" % old, "index/%s.md" % new
    out = []
    with open(path, encoding="utf-8") as _fh:
        _content = _fh.read()
    for line in _content.splitlines(keepends=True):
        if ptr_old in line:                      # ligne de domaine : patch pointeur + libellé en gras
            line = line.replace(ptr_old, ptr_new).replace("**%s**" % old, "**%s**" % new)
        out.append(line)
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(out))


def rename_domain(vault, old, new):
    if not SLUG_RE.match(old or "") or not SLUG_RE.match(new or ""):
        raise ApiError(400, "domaine invalide (slug attendu)")
    old_dir, new_dir = _safe_dir(vault, old), _safe_dir(vault, new)
    if not os.path.isdir(old_dir):
        raise ApiError(404, "domaine introuvable")
    if os.path.exists(new_dir):
        raise ApiError(400, "le domaine « %s » existe déjà" % new)
    os.rename(old_dir, new_dir)
    _patch_memory_domain(vault, old, new)
    reshard.reshard(vault)
    return _metadata(vault)


def similar(vault, data):
    text = "\n".join(((data.get("name") or "").strip(),
                      (data.get("description") or "").strip(),
                      data.get("body", "") or ""))
    facts, _ = bv.collect_facts(vault, include_body=True)
    embed_fn = embed.load_fastembed_embed_fn()
    store = {} if embed_fn is None else embed.refresh_store(facts, {}, embed_fn)
    return embed.find_similar(text, facts, store, embed_fn, exclude=(data.get("exclude") or None))


def make_handler(vault, template):
    vault_real = os.path.realpath(vault)
    token = secrets.token_hex(16)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="text/plain; charset=utf-8"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                facts, index_body = bv.collect_facts(vault, include_body=False)
                data = {"facts": facts, "index": index_body, "vault": vault,
                        "count": len(facts), "token": token}
                with open(template, encoding="utf-8") as _tf:
                    html = _tf.read().replace(
                    "/*__DATA__*/", json.dumps(data, ensure_ascii=False))
                self._send(200, html, "text/html; charset=utf-8")
            elif u.path == "/fact":
                f = (parse_qs(u.query).get("f") or [""])[0]
                try:
                    full = os.path.realpath(os.path.join(vault, f))
                except (ValueError, OSError):   # ex. null byte dans f -> 404 propre, pas 500
                    self._send(404, "not found"); return
                inside = full == vault_real or full.startswith(vault_real + os.sep)
                if not f or not full.endswith(".md") or not inside or not os.path.isfile(full):
                    self._send(404, "not found"); return
                _, body = bv.parse_md(full)
                self._send(200, body, "text/markdown; charset=utf-8")
            elif u.path == "/search":
                q = (parse_qs(u.query).get("q") or [""])[0].strip().lower()
                facts, _ = bv.collect_facts(vault, include_body=True)
                res = []
                for f in facts:
                    hay = " ".join((f["name"], f["description"], f["body"])).lower()
                    if q and q in hay:
                        res.append({k: f[k] for k in ("file", "name", "description", "type", "path")})
                self._send(200, json.dumps(res, ensure_ascii=False),
                           "application/json; charset=utf-8")
            else:
                self._send(404, "not found")

        def _json_body(self):
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            return json.loads(raw or b"{}")

        def _require_token(self):
            if not secrets.compare_digest(self.headers.get("X-SM-Token") or "", token):
                raise ApiError(403, "jeton manquant ou invalide")

        def _ok(self, data):
            self._send(200, json.dumps(data, ensure_ascii=False),
                       "application/json; charset=utf-8")

        def do_POST(self):
            u = urlparse(self.path)
            if u.path == "/api/similar":                 # requête en lecture : pas de jeton
                try:
                    self._ok(similar(vault, self._json_body()))
                except (ValueError, OSError) as e:
                    self._send(400, "erreur: %s" % e)
                return
            try:
                self._require_token()
                if u.path == "/api/fact":
                    self._ok(create_fact(vault, self._json_body()))
                elif u.path == "/api/rename-domain":
                    d = self._json_body()
                    self._ok(rename_domain(vault, d.get("old"), d.get("new")))
                else:
                    self._send(404, "not found")
            except ApiError as e:
                self._send(e.status, e.message)
            except (ValueError, OSError) as e:
                self._send(400, "erreur: %s" % e)

        def do_PUT(self):
            u = urlparse(self.path)
            try:
                self._require_token()
                if u.path == "/api/fact":
                    f = (parse_qs(u.query).get("f") or [""])[0]
                    self._ok(update_fact(vault, f, self._json_body()))
                else:
                    self._send(404, "not found")
            except ApiError as e:
                self._send(e.status, e.message)
            except (ValueError, OSError) as e:
                self._send(400, "erreur: %s" % e)

        def do_DELETE(self):
            u = urlparse(self.path)
            try:
                self._require_token()
                if u.path == "/api/fact":
                    f = (parse_qs(u.query).get("f") or [""])[0]
                    self._ok(delete_fact(vault, f))
                else:
                    self._send(404, "not found")
            except ApiError as e:
                self._send(e.status, e.message)
            except (ValueError, OSError) as e:
                self._send(400, "erreur: %s" % e)

        def log_message(self, *a):
            pass

    return Handler


def main():
    vault, template = sys.argv[1], sys.argv[2]
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    httpd = HTTPServer(("127.0.0.1", port), make_handler(vault, template))
    print("http://127.0.0.1:%d" % httpd.server_address[1])
    httpd.serve_forever()


if __name__ == "__main__":
    main()
