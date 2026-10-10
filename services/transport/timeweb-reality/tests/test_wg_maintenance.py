"""No SSH or filesystem mutations: legacy writers must fail before first action."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "maintenance-wg/commands.sh"
MUTATORS = (
    "init_dirs ensure_server_key gen_upstream ensure_client_key gen_client render_client_config "
    "sync_wg_interface selector_runtime_cmd apply_selector_client_runtime apply_all_selector_runtime "
    "soft_reload_selector remove_peer_block_by_client update_clients_list delete_selector_client "
    "delete_file_client delete_selected_client regenerate_file_client regenerate_selected_client "
    "render_upstream render_clients render apply_sysctl apply_firewall apply_ru_bth clear_ru_bth "
    "up refresh_clients rotate_client delete_client regenerate_client add_selector_client add_bth_client "
    "add_client backup"
).split()


class MaintenanceTests(unittest.TestCase):
    def test_all_direct_functions_refuse_before_io(self):
        for name in MUTATORS:
            with self.subTest(name=name):
                result = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-c",
                    'cat() { while IFS= read -r line; do printf "%s\\n" "$line"; done; }; '
                    'script=$1; fn=$2; set -- help; source "$script" >/dev/null; "$fn"',
                    "test", str(SCRIPT), name], env={"PATH": ""}, capture_output=True, timeout=3)
                self.assertEqual(result.returncode, 1)
                self.assertIn(b"RETIRED mutation", result.stderr)
                self.assertNotIn(b"command not found", result.stderr)
                self.assertEqual(result.stdout, b"")

    def test_help_remains_available(self):
        result = subprocess.run(["/bin/bash", str(SCRIPT), "help"],
                                env={"PATH": "/usr/bin:/bin"}, capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"viewing remains available", result.stdout)

    def test_no_recreate_fallback_remains(self):
        source = SCRIPT.read_text()
        self.assertNotIn("falling back to full container recreate", source)
        self.assertEqual(source.count("REFUSED without container recreate"), 3)


if __name__ == "__main__":
    unittest.main()
