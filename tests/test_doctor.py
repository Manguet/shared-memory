import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SPEC = importlib.util.spec_from_file_location(
    "doctor", os.path.join(HERE, "..", "scripts", "doctor.py"))
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)

ALL_OK = {"python_ok": lambda: True, "has_fastembed": lambda: True,
          "model_cached": lambda: True, "mcp_json_present": lambda: True}


def by_name(checks):
    return {c["name"]: c for c in checks}


class DiagnoseTest(unittest.TestCase):
    def test_all_present_all_ok(self):
        checks = D.diagnose(probes=ALL_OK)
        self.assertTrue(all(c["ok"] for c in checks))

    def test_fastembed_absent_flags_semantic_and_model_with_remedy(self):
        probes = dict(ALL_OK, has_fastembed=lambda: False, model_cached=lambda: False)
        checks = by_name(D.diagnose(probes=probes))
        fe = next(c for c in checks.values() if "fastembed" in c["name"])
        self.assertFalse(fe["ok"])
        self.assertIn("pip install fastembed", fe["remedy"])
        model = next(c for c in checks.values() if "modèle" in c["name"])
        self.assertFalse(model["ok"])

    def test_mcp_json_absent_flagged(self):
        probes = dict(ALL_OK, mcp_json_present=lambda: False)
        checks = by_name(D.diagnose(probes=probes))
        mj = next(c for c in checks.values() if ".mcp.json" in c["name"])
        self.assertFalse(mj["ok"])

    def test_default_probes_run_without_error(self):
        checks = D.diagnose()
        self.assertTrue(any("fastembed" in c["name"] for c in checks))


class ModelCacheProbeTest(unittest.TestCase):
    def test_has_onnx_detects_model_file(self):
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, "models--x", "snapshots", "abc")
            os.makedirs(sub)
            open(os.path.join(sub, "model_optimized.onnx"), "w").close()
            self.assertTrue(D._has_onnx([d]))

    def test_has_onnx_false_when_absent(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(D._has_onnx([d, os.path.join(d, "nope")]))


if __name__ == "__main__":
    unittest.main()
