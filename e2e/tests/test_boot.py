"""Container-backed boot proof: the patched community image (patch 0002) starts and serves /health.

Not part of TEST_TARGETS (needs podman and the built image); run via `make e2e` (single-goal `make e2e-boot` is rejected by the top-level Makefile).
Without patches/0002 the image dies at startup with
"Attempted to resolve unregistered dependency token: Symbol(v2.commandExplain.previewPlannerRegistry)".
"""
import os
import subprocess
import sys
import unittest

from e2e import stack

BAD = "unregistered dependency token"


class PatchedImageBoots(unittest.TestCase):
    def tearDown(self):
        subprocess.run([sys.executable, os.path.join(stack.HERE, "stack.py"), "down"], check=False)

    def test_boot_reaches_health_without_di_error(self):
        tag = stack.image_tag()
        up = subprocess.run([sys.executable, os.path.join(stack.HERE, "stack.py"), "up"],
                            text=True, capture_output=True)
        logs = stack.podman("logs", f"{stack.POD}-teable", check=False, capture=True)
        text = logs.stdout + logs.stderr
        self.assertFalse(BAD in text, f"{tag}: '{BAD}' in the teable log")
        self.assertEqual(up.returncode, 0, f"{tag}: stack up failed: {up.stderr[-2000:]}")
        self.assertIn("ready", up.stdout)
        self.assertTrue(stack.healthy(), f"{tag}: GET /health is not 200")


if __name__ == "__main__":
    unittest.main()
