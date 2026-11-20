import json
import os
import tempfile
import unittest
from unittest import mock

from e2e import stack


class StackArgs(unittest.TestCase):
    def test_pod_shape_and_secrets(self):
        s = {"pg": "PGPW", "redis": "RDPW", "secret_key": "SK"}
        a = stack.run_args("localhost/x:1", s)
        self.assertEqual(a[0][:4], ["pod", "create", "--name", "ota-e2e"])
        self.assertIn("127.0.0.1:3010:3000", a[0])
        self.assertIn("PRISMA_DATABASE_URL=postgresql://teable:PGPW@127.0.0.1:5432/teable", a[3])
        self.assertIn("BACKEND_CACHE_REDIS_URI=redis://default:RDPW@127.0.0.1:6379/0", a[3])
        self.assertEqual(a[3][-1], "localhost/x:1")
        self.assertEqual(a[2][-3:], ["redis-server", "--requirepass", "RDPW"])

    def test_secrets_differ_per_call(self):
        self.assertNotEqual(stack.new_secrets(), stack.new_secrets())

    def test_image_tag(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "upstream.lock.json"), "w") as f:
                json.dump({"image": {"tag": "localhost/t:1"}}, f)
            self.assertEqual(stack.image_tag(d), "localhost/t:1")

    def test_podman_is_the_shim(self):
        self.assertTrue(stack.PODMAN.endswith(os.path.join("e2e", "bin", "podman")))


class EnsureInfraImage(unittest.TestCase):
    @mock.patch("e2e.stack.prune_dangling_images")
    @mock.patch("e2e.stack.podman")
    def test_prunes_after_a_successful_build(self, mock_podman, mock_prune):
        mock_podman.side_effect = [mock.Mock(returncode=1), mock.Mock(returncode=0)]
        stack.ensure_infra_image()
        mock_prune.assert_called_once_with(podman_bin=stack.PODMAN)

    @mock.patch("e2e.stack.prune_dangling_images")
    @mock.patch("e2e.stack.podman")
    def test_no_prune_when_image_already_present(self, mock_podman, mock_prune):
        mock_podman.return_value = mock.Mock(returncode=0)
        stack.ensure_infra_image()
        mock_prune.assert_not_called()

    @mock.patch("e2e.stack.prune_dangling_images")
    @mock.patch("e2e.stack.podman")
    def test_no_prune_when_build_fails(self, mock_podman, mock_prune):
        def fake_podman(*args, **kwargs):
            if args[0] == "image":
                return mock.Mock(returncode=1)
            raise RuntimeError("build failed")
        mock_podman.side_effect = fake_podman
        with self.assertRaises(RuntimeError):
            stack.ensure_infra_image()
        mock_prune.assert_not_called()


if __name__ == "__main__":
    unittest.main()
