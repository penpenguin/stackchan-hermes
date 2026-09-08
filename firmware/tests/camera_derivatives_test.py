from __future__ import annotations

import json
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from verify_camera_derivatives import verify_camera_derivatives


class CameraDerivativesTest(unittest.TestCase):
    def test_hashes_and_actual_compiled_inputs_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, derivative = root / "original.c", root / "reviewed.c"
            source.write_text("original")
            derivative.write_text("reviewed")
            manifest = root / "camera.json"
            manifest.write_text(json.dumps({"files": [{
                "source": "original.c", "source_sha256": sha256(source.read_bytes()).hexdigest(),
                "derivative": "reviewed.c", "derivative_sha256": sha256(derivative.read_bytes()).hexdigest(),
            }]}))
            commands = [{"file": str(derivative)}]
            verify_camera_derivatives(root, manifest, commands)
            for changed in (source, derivative):
                before = changed.read_bytes()
                changed.write_text("unreviewed")
                with self.assertRaises(ValueError):
                    verify_camera_derivatives(root, manifest, commands)
                changed.write_bytes(before)
            for bad in ([], [{"file": str(source)}], commands + [{"file": str(source)}]):
                with self.assertRaises(ValueError):
                    verify_camera_derivatives(root, manifest, bad)


if __name__ == "__main__":
    unittest.main()
