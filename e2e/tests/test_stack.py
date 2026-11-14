import json
import os
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
