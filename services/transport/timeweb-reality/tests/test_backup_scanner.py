import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "backup_readonly.sh"


class ScannerTests(unittest.TestCase):
    def scan_link(self, target):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            # The scanner runs on Linux; emulate GNU stat's fixed output on Mac.
            stat = root / "stat"
            stat.write_text("#!/bin/sh\nprintf 'a1ff 777 501 20 8 0 0\\n'\n")
            stat.chmod(0o700)
            link = root / "link"
            link.symlink_to(target)
            return subprocess.run(
                ["bash", "-c", 'source "$1"; sh -c "$MEMBER_PROGRAM" sh "$2"',
                 "scanner-test", str(SCRIPT), str(link)],
                env={**os.environ, "PATH": str(root) + os.pathsep + os.defpath},
                capture_output=True, text=True, timeout=5,
            )

    def test_link_target_not_truncated(self):
        for target in ("target", "target.", "../target", "target with space"):
            with self.subTest(target=target):
                result = self.scan_link(target)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.rstrip("\n").split("\t")[6], target)

    def test_control_characters_rejected_without_stripping(self):
        for target in ("target\n", "target\n\n", "target\t", "target\r"):
            with self.subTest(target=repr(target)):
                result = self.scan_link(target)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "SCAN_ERROR\n")


if __name__ == "__main__":
    unittest.main()
