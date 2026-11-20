"""Unit tests for the shared Chain-D post-build prune helper (scripts/podman_prune.py)."""
import subprocess
import unittest
from unittest import mock

from scripts import podman_prune


class PruneDanglingImages(unittest.TestCase):
    @mock.patch("scripts.podman_prune.subprocess.run")
    def test_calls_exactly_podman_image_prune_f(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["podman", "image", "prune", "-f"], returncode=0,
            stdout="Total reclaimed space: 12B\n", stderr="")
        podman_prune.prune_dangling_images(podman_bin="podman")
        mock_run.assert_called_once_with(["podman", "image", "prune", "-f"], capture_output=True, text=True)

    @mock.patch("scripts.podman_prune.subprocess.run")
    def test_uses_the_configured_podman_binary(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        podman_prune.prune_dangling_images(podman_bin="/path/to/shim-podman")
        mock_run.assert_called_once_with(["/path/to/shim-podman", "image", "prune", "-f"], capture_output=True, text=True)

    @mock.patch("scripts.podman_prune.subprocess.run")
    def test_nonzero_exit_warns_and_does_not_raise(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")
        podman_prune.prune_dangling_images(podman_bin="podman")  # must not raise

    @mock.patch("scripts.podman_prune.subprocess.run", side_effect=FileNotFoundError("no podman"))
    def test_missing_binary_warns_and_does_not_raise(self, mock_run):
        podman_prune.prune_dangling_images(podman_bin="podman")  # must not raise


if __name__ == "__main__":
    unittest.main()
