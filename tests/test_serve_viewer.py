import importlib.util
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer


def _token_of(base_get):
    """Extrait le jeton CSRF injecté dans la page (DATA.token)."""
    html = base_get
    data = json.loads(html[html.index("<x>") + 3: html.index("</x>")])
    return data.get("token")


def write_req(port, method, path, body=None, token="SKIP"):
    url = "http://127.0.0.1:%d%s" % (port, path)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token != "SKIP":
        req.add_header("X-SM-Token", token)
    return urllib.request.urlopen(req)

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "serve_viewer", os.path.join(HERE, "..", "scripts", "serve-viewer.py"))
sv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sv)


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class ServerTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.vault = os.path.join(self.root, "vault")
        write(os.path.join(self.vault, "mailing", "audit.md"),
              "---\nname: audit\ndescription: desc audit\nmetadata:\n  type: project\n---\nle corps secret du fait")
        self.tmpl = os.path.join(self.root, "tmpl.html")
        write(self.tmpl, "<x>/*__DATA__*/</x>")
        self.httpd = HTTPServer(("127.0.0.1", 0), sv.make_handler(self.vault, self.tmpl))
        self.port = self.httpd.server_address[1]
        self.t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.t.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self._tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return r.status, r.read().decode("utf-8")


class IndexRouteTest(ServerTestBase):
    def test_root_serves_html_with_metadata_no_body(self):
        status, html = self.get("/")
        self.assertEqual(status, 200)
        data = json.loads(html[html.index("<x>") + 3: html.index("</x>")])
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["facts"][0]["name"], "audit")
        self.assertEqual(data["facts"][0]["path"], ["mailing"])
        self.assertNotIn("body", data["facts"][0])


class FactRouteTest(ServerTestBase):
    def test_fact_returns_body(self):
        status, body = self.get("/fact?f=mailing/audit.md")
        self.assertEqual(status, 200)
        self.assertIn("le corps secret du fait", body)

    def test_fact_rejects_traversal(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/fact?f=../../../../etc/passwd")
        self.assertEqual(cm.exception.code, 404)

    def test_fact_missing_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get("/fact?f=mailing/nope.md")
        self.assertEqual(cm.exception.code, 404)


class SearchRouteTest(ServerTestBase):
    def test_search_matches_body(self):
        status, payload = self.get("/search?q=corps%20secret")
        self.assertEqual(status, 200)
        res = json.loads(payload)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["name"], "audit")
        self.assertNotIn("body", res[0])

    def test_search_no_match_is_empty(self):
        status, payload = self.get("/search?q=zzzznotfound")
        self.assertEqual(json.loads(payload), [])


class CreateTest(ServerTestBase):
    def _token(self):
        _, html = self.get("/")
        return _token_of(html)

    def test_get_injects_token(self):
        self.assertTrue(self._token())

    def test_create_without_token_is_403(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            write_req(self.port, "POST", "/api/fact",
                      {"name": "x", "type": "project", "description": "d", "body": "b", "domain": "mailing"})
        self.assertEqual(cm.exception.code, 403)

    def test_create_writes_fact_and_index(self):
        r = write_req(self.port, "POST", "/api/fact",
                      {"name": "relance", "type": "project", "description": "relance 72h",
                       "body": "corps", "domain": "mailing"}, token=self._token())
        self.assertEqual(r.status, 200)
        self.assertTrue(os.path.isfile(os.path.join(self.vault, "mailing", "relance.md")))
        self.assertIn("relance", open(os.path.join(self.vault, "index", "mailing.md"), encoding="utf-8").read())

    def test_create_personal_goes_to_root_not_indexed(self):
        write_req(self.port, "POST", "/api/fact",
                  {"name": "note-perso", "type": "feedback", "description": "d", "body": "b", "domain": "mailing"},
                  token=self._token())
        self.assertTrue(os.path.isfile(os.path.join(self.vault, "note-perso.md")))
        self.assertFalse(os.path.isfile(os.path.join(self.vault, "mailing", "note-perso.md")))

    def test_create_invalid_slug_is_400(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            write_req(self.port, "POST", "/api/fact",
                      {"name": "Pas Valide", "type": "project", "description": "d", "body": "b", "domain": "mailing"},
                      token=self._token())
        self.assertEqual(cm.exception.code, 400)

    def test_create_duplicate_is_400(self):
        body = {"name": "audit", "type": "project", "description": "d", "body": "b", "domain": "mailing"}
        with self.assertRaises(urllib.error.HTTPError) as cm:
            write_req(self.port, "POST", "/api/fact", body, token=self._token())
        self.assertEqual(cm.exception.code, 400)


class UpdateTest(ServerTestBase):
    def _token(self):
        _, html = self.get("/"); return _token_of(html)

    def test_update_changes_fields(self):
        write_req(self.port, "PUT", "/api/fact?f=mailing/audit.md",
                  {"name": "audit", "type": "reference", "description": "maj", "body": "neuf", "domain": "mailing"},
                  token=self._token())
        txt = open(os.path.join(self.vault, "mailing", "audit.md"), encoding="utf-8").read()
        self.assertIn("type: reference", txt)
        self.assertIn("neuf", txt)

    def test_update_rename_moves_file(self):
        write_req(self.port, "PUT", "/api/fact?f=mailing/audit.md",
                  {"name": "audit-2", "type": "project", "description": "d", "body": "b", "domain": "mailing"},
                  token=self._token())
        self.assertFalse(os.path.isfile(os.path.join(self.vault, "mailing", "audit.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.vault, "mailing", "audit-2.md")))

    def test_update_change_domain_relocates(self):
        write_req(self.port, "PUT", "/api/fact?f=mailing/audit.md",
                  {"name": "audit", "type": "project", "description": "d", "body": "b", "domain": "ui"},
                  token=self._token())
        self.assertFalse(os.path.isfile(os.path.join(self.vault, "mailing", "audit.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.vault, "ui", "audit.md")))

    def test_update_missing_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            write_req(self.port, "PUT", "/api/fact?f=mailing/nope.md",
                      {"name": "nope", "type": "project", "description": "d", "body": "b", "domain": "mailing"},
                      token=self._token())
        self.assertEqual(cm.exception.code, 404)


class DeleteTest(ServerTestBase):
    def _token(self):
        _, html = self.get("/"); return _token_of(html)

    def test_delete_removes_fact(self):
        write_req(self.port, "DELETE", "/api/fact?f=mailing/audit.md", token=self._token())
        self.assertFalse(os.path.isfile(os.path.join(self.vault, "mailing", "audit.md")))

    def test_delete_missing_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            write_req(self.port, "DELETE", "/api/fact?f=mailing/nope.md", token=self._token())
        self.assertEqual(cm.exception.code, 404)

    def test_delete_traversal_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            write_req(self.port, "DELETE", "/api/fact?f=../../../etc/passwd", token=self._token())
        self.assertEqual(cm.exception.code, 404)


class RenameDomainTest(ServerTestBase):
    def _token(self):
        _, html = self.get("/"); return _token_of(html)

    def test_rename_moves_folder(self):
        write_req(self.port, "POST", "/api/rename-domain", {"old": "mailing", "new": "emailing"},
                  token=self._token())
        self.assertFalse(os.path.isdir(os.path.join(self.vault, "mailing")))
        self.assertTrue(os.path.isfile(os.path.join(self.vault, "emailing", "audit.md")))

    def test_rename_patches_memory(self):
        with open(os.path.join(self.vault, "MEMORY.md"), "w", encoding="utf-8") as f:
            f.write("# Carte\n\n## Domaines\n- **mailing** (1) → `index/mailing.md` — emails\n")
        write_req(self.port, "POST", "/api/rename-domain", {"old": "mailing", "new": "emailing"},
                  token=self._token())
        mem = open(os.path.join(self.vault, "MEMORY.md"), encoding="utf-8").read()
        self.assertIn("index/emailing.md", mem)
        self.assertNotIn("index/mailing.md", mem)

    def test_rename_to_existing_is_400(self):
        os.makedirs(os.path.join(self.vault, "ui"), exist_ok=True)
        with self.assertRaises(urllib.error.HTTPError) as cm:
            write_req(self.port, "POST", "/api/rename-domain", {"old": "mailing", "new": "ui"},
                      token=self._token())
        self.assertEqual(cm.exception.code, 400)

    def test_rename_missing_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            write_req(self.port, "POST", "/api/rename-domain", {"old": "nope", "new": "x"},
                      token=self._token())
        self.assertEqual(cm.exception.code, 404)


class HardeningTest(ServerTestBase):
    def _token(self):
        _, html = self.get("/"); return _token_of(html)

    def test_description_newline_is_flattened(self):
        write_req(self.port, "POST", "/api/fact",
                  {"name": "nl", "type": "project", "description": "ligne1\nligne2", "body": "corps", "domain": "mailing"},
                  token=self._token())
        fm = open(os.path.join(self.vault, "mailing", "nl.md"), encoding="utf-8").read().split("---")[1]
        self.assertIn("description: ligne1 ligne2", fm)
        self.assertNotIn("ligne1\nligne2", fm)

    def test_rename_domain_preserves_prose(self):
        with open(os.path.join(self.vault, "MEMORY.md"), "w", encoding="utf-8") as f:
            f.write("# Carte\n\n## Domaines\n- **mailing** (1) → `index/mailing.md`\n\n"
                    "## Notes\n- La stratégie **mailing** est centrale.\n")
        write_req(self.port, "POST", "/api/rename-domain", {"old": "mailing", "new": "emailing"}, token=self._token())
        mem = open(os.path.join(self.vault, "MEMORY.md"), encoding="utf-8").read()
        self.assertIn("`index/emailing.md`", mem)
        self.assertIn("La stratégie **mailing** est centrale.", mem)


if __name__ == "__main__":
    unittest.main()
