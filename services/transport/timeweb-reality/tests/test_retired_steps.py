"""Retired CLIs must refuse before imports, credentials, SSH or local writes."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    "stage4_fornex.py", "stage56.py", "stage8_cenuta.py", "stage9_bth.py", "prepare_stage3.py",
    "prepare_rollback.py", "prepare_bth_recovery.py", "stage56_target_update.py", "issue_stage56_clients.py",
)


class RetiredStepTests(unittest.TestCase):
    def test_cli_fails_before_imports_and_external_tools(self):
        for script in SCRIPTS:
            for options in ([], ["apply"], ["--force"], ["--help"]):
                with self.subTest(script=script, options=options):
                    result = subprocess.run([sys.executable, "-B", "-O", str(ROOT / script), *options],
                                            capture_output=True, env={"PATH": ""}, timeout=5)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(b"RETIRED one-shot", result.stderr)
                    self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
