import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
VERIFY_PY = os.path.join(HERE, "..", "scripts", "verify-scale.py")


class GuardTest(unittest.TestCase):
    def test_refuses_dest_equals_source(self):
        with tempfile.TemporaryDirectory() as d:
            marker = os.path.join(d, "keep.txt")
            with open(marker, "w") as f:
                f.write("x")
            r = subprocess.run([sys.executable, VERIFY_PY, d, "--source", d],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertTrue(os.path.exists(marker))   # rien n'a été détruit


if __name__ == "__main__":
    unittest.main()
