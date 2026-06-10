import importlib.util
import json
import os
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


if __name__ == "__main__":
    unittest.main()
