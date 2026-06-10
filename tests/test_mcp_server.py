import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "mcp_server", os.path.join(HERE, "..", "scripts", "mcp-server.py"))
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def fake_runner(query, k):
    return {"results": [{"file": "d/a.md", "name": "a", "path": ["d"], "score": 0.5}],
            "vector_inactive": False, "echo": [query, k]}


class HandleRequestTest(unittest.TestCase):
    def test_initialize_echoes_protocol_and_serverinfo(self):
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2025-06-18"}}
        resp = M.handle_request(req, fake_runner)
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(resp["result"]["serverInfo"]["name"], "shared-memory")
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_initialized_notification_returns_none(self):
        self.assertIsNone(M.handle_request(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}, fake_runner))

    def test_tools_list_exposes_search_memory(self):
        resp = M.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, fake_runner)
        names = [t["name"] for t in resp["result"]["tools"]]
        self.assertEqual(names, ["search_memory"])
        self.assertIn("query", resp["result"]["tools"][0]["inputSchema"]["properties"])

    def test_tools_call_runs_search_and_wraps_text(self):
        req = {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
               "params": {"name": "search_memory", "arguments": {"query": "relance", "k": 5}}}
        resp = M.handle_request(req, fake_runner)
        payload = json.loads(resp["result"]["content"][0]["text"])
        self.assertEqual(payload["echo"], ["relance", 5])
        self.assertEqual(payload["results"][0]["file"], "d/a.md")
        self.assertNotIn("body", payload["results"][0])

    def test_unknown_tool_is_error(self):
        req = {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
               "params": {"name": "nope", "arguments": {}}}
        resp = M.handle_request(req, fake_runner)
        self.assertIn("error", resp)

    def test_unknown_method_is_error(self):
        resp = M.handle_request({"jsonrpc": "2.0", "id": 5, "method": "foo/bar"}, fake_runner)
        self.assertEqual(resp["error"]["code"], -32601)


class ContextTest(unittest.TestCase):
    def test_build_context_errors_when_vault_unresolved(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["SM_REGISTRY"] = os.path.join(d, "registry.json")  # absent
            os.environ["CLAUDE_PROJECT_DIR"] = "/no/such/project"
            try:
                ctx = M.build_context()
            finally:
                os.environ.pop("SM_REGISTRY", None)
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            self.assertIn("error", ctx)

    def test_run_search_grep_fallback_returns_pointers(self):
        with tempfile.TemporaryDirectory() as d:
            vault = os.path.join(d, "vault", "mailing")
            os.makedirs(vault)
            with open(os.path.join(vault, "a.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: relance-j3\ndescription: relance paniers 72h\n"
                        "metadata:\n  type: project\n---\ncorps relance")
            ctx = {"slug": "-t", "vault": os.path.join(d, "vault")}
            out = M.run_search(ctx, "relance", 8)
            files = [r["file"] for r in out["results"]]
            self.assertIn(os.path.join("mailing", "a.md"), files)
            self.assertTrue(all("body" not in r for r in out["results"]))


class McpJsonTest(unittest.TestCase):
    def test_mcp_json_declares_server_with_plugin_root(self):
        path = os.path.join(HERE, "..", ".mcp.json")
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        srv = cfg["mcpServers"]["shared-memory"]
        self.assertEqual(srv["command"], "python3")
        self.assertTrue(any("${CLAUDE_PLUGIN_ROOT}" in a and a.endswith("mcp-server.py")
                            for a in srv["args"]))


if __name__ == "__main__":
    unittest.main()
