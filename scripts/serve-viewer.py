#!/usr/bin/env python3
"""Serveur local (lecture seule) du vault mémoire.

Usage: serve-viewer.py <vault-dir> <template-html> [port]
- GET /            -> HTML du viewer + index métadonnées (sans body)
- GET /fact?f=…    -> body d'UN fait (chemin validé : reste dans le vault, .md)
- GET /search?q=…  -> grep full-text sur les faits, renvoie les métadonnées matchantes
Bind 127.0.0.1 uniquement.
"""
import importlib.util
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "build_viewer", os.path.join(_HERE, "build-viewer.py"))
bv = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bv)


def make_handler(vault, template):
    vault_real = os.path.realpath(vault)

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
                data = {"facts": facts, "index": index_body, "vault": vault, "count": len(facts)}
                html = open(template, encoding="utf-8").read().replace(
                    "/*__DATA__*/", json.dumps(data, ensure_ascii=False))
                self._send(200, html, "text/html; charset=utf-8")
            else:
                self._send(404, "not found")

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
