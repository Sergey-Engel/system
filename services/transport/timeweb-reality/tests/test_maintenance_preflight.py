"""Offline tests only: synthetic masters, mocked SSH and a stubbed local shell."""

import ast
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import maintenance_preflight as preflight

LOCAL_RUN = subprocess.run
SECRET = "SYNTHETIC-SECRET-MUST-NOT-APPEAR"


def evidence(**changes):
    checks = dict.fromkeys(preflight.REMOTE_CHECKS, "PASSED")
    checks.update(changes)
    return "".join(name + "\t" + status + "\n" for name, status in checks.items()).encode()


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for local, _ in preflight.FILE_TARGETS.values():
            path = self.root / local
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((SECRET + ":" + path.name).encode())
        self.release = self.root / "bth-recovery-release"
        config = json.dumps({"synthetic_secret": SECRET}).encode()
        (self.root / "stage9-bth/config.after").write_bytes(config)
        (self.release / "xray.baseline").write_bytes(config)
        (self.root / "stage9-bth/guard.expected.after").write_bytes(
            (self.release / "hostguard.baseline").read_bytes())
        (self.root / "bth_recover.sh").write_bytes((self.release / "bth_recover.sh").read_bytes())
        self.contract = {
            "image": "sha256:" + "a" * 64,
            "hashes": {key: preflight.sha256((self.release / name).read_bytes())
                       for key, name in preflight.CONTRACT_FILES.items()},
        }
        self.write_contract()
        self.ssh = mock.patch.object(preflight.run_backup, "ssh_args", return_value=["FAKE-SSH", "timeweb"]).start()
        self.addCleanup(mock.patch.stopall)
        self.run = mock.patch.object(preflight.subprocess, "run").start()
        self.run.return_value = subprocess.CompletedProcess([], 0, evidence(), SECRET.encode())

    def write_contract(self):
        (self.release / "contract.json").write_text(json.dumps(self.contract))

    def report(self, **kwargs):
        result = preflight.preflight(self.root, **kwargs)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertIs(result["wg_changes_authorized"], False)
        self.assertIs(result["contract_update_authorized"], False)
        return result

    def test_pass_is_check_only_with_bounded_ssh(self):
        report = self.report()
        self.assertEqual(report["status"], "PASSED")
        self.ssh.assert_called_once_with("timeweb")
        args, kwargs = self.run.call_args
        self.assertEqual(args[0][:-1], ["FAKE-SSH", "timeweb"])
        self.assertIn("timeout --signal=TERM --kill-after=3s 85s", args[0][-1])
        self.assertEqual(kwargs["timeout"], 90)
        self.assertTrue(kwargs["capture_output"])
        payload = kwargs["input"].decode()
        self.assertNotIn(SECRET, payload)
        self.assertIn("bash /opt/timeweb-reality/bth-recovery/bth_recover.sh --check", payload)
        self.assertIn('exec 3<"/proc/$pid/ns/net"', payload)
        self.assertIn('nsenter --net="$ns_path"', payload)
        self.assertNotIn("nsenter -t", payload)
        for mutation in ("wg set", "nft -f", "systemctl start", "systemctl restart", "chmod"):
            self.assertNotIn(mutation, payload)
        self.assertNotRegex(payload, r"(?:^|\s)--(?:renew|sign)(?:\s|$)")

    def test_each_local_input_missing_refuses_ssh(self):
        for local in {pair[0] for pair in preflight.FILE_TARGETS.values()} | {"bth_recover.sh"}:
            with self.subTest(local=local):
                path = self.root / local
                saved = path.read_bytes()
                path.unlink()
                self.assertEqual(self.report()["checks"], {"local_reference": "FAILED"})
                path.write_bytes(saved)
        self.run.assert_not_called()

    def test_each_contract_hash_mismatch_refuses_ssh(self):
        for name in preflight.CONTRACT_FILES:
            with self.subTest(name=name):
                original = self.contract["hashes"][name]
                self.contract["hashes"][name] = "0" * 64
                self.write_contract()
                self.assertEqual(self.report()["status"], "FAILED")
                self.contract["hashes"][name] = original
        self.run.assert_not_called()

    def test_current_stage9_master_required(self):
        (self.root / "stage9-bth/config.after").write_text('{"obsolete_stage56": true}')
        self.assertEqual(self.report()["checks"]["local_reference"], "FAILED")
        self.run.assert_not_called()

    def test_current_top_level_helper_must_match_release(self):
        (self.root / "bth_recover.sh").write_text("drift")
        self.assertEqual(self.report()["status"], "FAILED")
        self.run.assert_not_called()

    def test_nonexecutable_helper_is_accepted_without_chmod(self):
        path = self.release / "bth_recover.sh"
        path.chmod(0o600)
        self.assertEqual(self.report()["status"], "PASSED")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_symlink_reference_refused(self):
        path = self.root / "stage9-bth/config.after"
        path.unlink()
        path.symlink_to(self.release / "xray.baseline")
        self.assertEqual(self.report()["status"], "FAILED")
        self.run.assert_not_called()

    def test_invalid_contract_shapes_are_sanitized(self):
        for value in (None, [], {"image": SECRET}, {"hashes": []}, SECRET):
            with self.subTest(value=type(value).__name__):
                (self.release / "contract.json").write_text(json.dumps(value))
                self.assertEqual(self.report()["status"], "FAILED")
        self.run.assert_not_called()

    def test_timeout_and_ssh_errors_never_leak_output(self):
        for error in (subprocess.TimeoutExpired(SECRET, 90, SECRET.encode(), SECRET.encode()),
                      OSError(SECRET), subprocess.SubprocessError(SECRET)):
            with self.subTest(error=type(error).__name__):
                self.run.side_effect = error
                self.assertEqual(self.report()["status"], "FAILED")

    def test_timeout_bound_refuses_ssh(self):
        for value in (0, -1, 14, 121, 10**12, float("nan"), 90.0, True):
            with self.subTest(timeout=value):
                self.assertEqual(self.report(timeout=value)["checks"], {"timeout_bound": "FAILED"})
        self.run.assert_not_called()

    def test_every_remote_failure_or_skip_is_fatal(self):
        for name in preflight.REMOTE_CHECKS:
            for status in ("FAILED", "SKIPPED"):
                with self.subTest(name=name, status=status):
                    self.run.return_value.stdout = evidence(**{name: status})
                    report = self.report()
                    self.assertEqual(report["status"], "FAILED")
                    self.assertEqual(report["checks"][name], status)

    def test_exit_code_required_even_with_pass_payload(self):
        self.run.return_value.returncode = 255
        report = self.report()
        self.assertEqual(report["status"], "FAILED")
        self.assertEqual(report["checks"]["ssh_exit"], "FAILED")

    def test_untrusted_or_incomplete_remote_output_rejected(self):
        for output in (b"", SECRET.encode(), evidence() + b"namespace_final\tPASSED\n",
                       evidence().split(b"\n", 1)[1], evidence() + b"unknown\tPASSED\n",
                       evidence().replace(b"PASSED", SECRET.encode(), 1), b"\xff", b"x" * 32769):
            with self.subTest(length=len(output)):
                self.run.return_value.stdout = output
                report = self.report()
                self.assertEqual(report["status"], "FAILED")
                self.assertEqual(report["checks"]["evidence_complete"], "FAILED")

    def test_reference_changes_during_probe_fail(self):
        def run(*args, **kwargs):
            (self.root / "stage9-bth/guard.nft.after").write_text("changed locally")
            return subprocess.CompletedProcess([], 0, evidence(), b"")
        self.run.side_effect = run
        self.assertEqual(self.report()["checks"]["local_reference_stable"], "FAILED")

    def test_cli_saves_private_sanitized_json_and_exit_status(self):
        for status, code in (("PASSED", 0), ("FAILED", 1)):
            with self.subTest(status=status):
                report = self.report()
                report["status"] = status
                output = self.root / (status + ".json")
                stream = io.StringIO()
                with mock.patch.object(preflight, "preflight", return_value=report), redirect_stdout(stream):
                    self.assertEqual(preflight.main(["--check", "--output", str(output)]), code)
                self.assertEqual(json.loads(output.read_text()), report)
                self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
                self.assertNotIn(SECRET, stream.getvalue())
                self.assertIn("not authorization for WG changes", stream.getvalue())

    def test_cli_refuses_existing_or_symlink_output_before_ssh(self):
        source = self.root / "stage9-bth/config.after"
        original = source.read_bytes()
        alias = self.root / "output.json"
        alias.symlink_to(source)
        for output in (source, alias, self.root / "missing" / "out.json"):
            with redirect_stderr(io.StringIO()) as stream:
                self.assertEqual(preflight.main(["--check", "--output", str(output)]), 1)
                self.assertNotIn(SECRET, stream.getvalue())
        self.run.assert_not_called()
        self.assertEqual(source.read_bytes(), original)

    def test_cli_requires_check_and_rejects_mutation_flags(self):
        for args in ([], ["--check", "--renew"], ["--check", "--sign"],
                     ["--check", "--restart"], ["--check", "--timeout", "121"]):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                preflight.main(args)
            self.assertEqual(error.exception.code, 2)
        self.run.assert_not_called()

    def test_import_has_no_execution_and_no_deployment_imports(self):
        path = ROOT / "maintenance_preflight.py"
        spec = importlib.util.spec_from_file_location("preflight_import_test", path)
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
        self.run.assert_not_called()
        tree = ast.parse(path.read_text())
        local_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                local_imports.extend(alias.name for alias in node.names if (ROOT / (alias.name + ".py")).exists())
            elif isinstance(node, ast.ImportFrom) and (ROOT / (str(node.module) + ".py")).exists():
                local_imports.append(node.module)
        self.assertEqual(local_imports, ["run_backup"])

    def shell(self, override=""):
        # Run the actual orchestration locally, replacing every remote operation
        # with a shell function. No SSH, Docker, /proc access, helper, or nsenter.
        stubs = r'''
hash_matches() { return 0; }
pin_namespace() { ns_path=synthetic; return 0; }
fresh_namespace() { return 0; }
timeout() {
    [ "$*" = '--signal=TERM --kill-after=2s 35s bash /opt/timeweb-reality/bth-recovery/bth_recover.sh --check' ] || return 99
    printf 'BTH_CONTRACT_VALID\n'
}
systemctl() {
    local unit="${@: -1}" active=active sub=running enabled=enabled type=simple
    case "$unit" in
      bth-recovery.service) active=inactive; sub=dead; enabled=static; type=oneshot;;
      bth-recovery.timer) sub=waiting; type=timer;;
    esac
    printf '%s\n' LoadState=loaded "ActiveState=$active" "SubState=$sub" \
      "UnitFileState=$enabled" "FragmentPath=/etc/systemd/system/$unit" \
      "DropInPaths=${DROPINS:-}" "NeedDaemonReload=${RELOAD:-no}" "Type=$type" \
      "Result=${RESULT:-success}" ExecMainStatus=0 MainPID=321 \
      ExecMainStartTimestampMonotonic=42 NRestarts=0
}
'''
        script = preflight.remote_script(preflight.load_reference(self.root)).decode()
        script = script.replace("\nfiles before\n", "\n" + stubs + override + "\nfiles before\n", 1)
        result = LOCAL_RUN(["/bin/bash", "--noprofile", "--norc"], input=script.encode(),
                           capture_output=True, timeout=5, env={"PATH": "/usr/bin:/bin"})
        self.assertNotIn(SECRET, result.stdout.decode())
        self.run.assert_not_called()
        return result.returncode, preflight.parse_checks(result.stdout)

    def test_remote_shell_all_checks_pass(self):
        code, checks = self.shell()
        self.assertEqual(code, 0)
        self.assertEqual(set(checks.values()), {"PASSED"})

    def test_remote_shell_drift_skips_helper(self):
        code, checks = self.shell('hash_matches() { [ "$2" != /opt/timeweb-reality/config.json ]; }')
        self.assertEqual(code, 1)
        self.assertEqual(checks["before:xray_config"], "FAILED")
        self.assertEqual(checks["bth_helper_check"], "SKIPPED")

    def test_remote_shell_helper_failure_and_wrong_sentinel(self):
        for override in ('timeout() { return 124; }', 'timeout() { printf "' + SECRET + '"; }'):
            with self.subTest(override=override):
                code, checks = self.shell(override)
                self.assertEqual(code, 1)
                self.assertEqual(checks["bth_helper_check"], "FAILED")

    def test_remote_shell_namespace_failure_skips_helper(self):
        code, checks = self.shell('pin_namespace() { return 1; }')
        self.assertEqual(code, 1)
        self.assertEqual(checks["namespace_pinned"], "FAILED")
        self.assertEqual(checks["bth_helper_check"], "SKIPPED")

    def test_remote_shell_namespace_changes_after_helper(self):
        code, checks = self.shell('''
fresh_count=0
fresh_namespace() { fresh_count=$((fresh_count + 1)); [ "$fresh_count" -eq 1 ]; }
''')
        self.assertEqual(code, 1)
        self.assertEqual(checks["bth_helper_check"], "PASSED")
        self.assertEqual(checks["namespace_after_helper"], "FAILED")
        self.assertEqual(checks["namespace_final"], "FAILED")

    def test_remote_shell_unit_drift_and_failed_oneshot(self):
        for override in ("DROPINS=/unexpected.conf", "RELOAD=yes", "RESULT=exit-code"):
            with self.subTest(override=override):
                code, checks = self.shell(override)
                self.assertEqual(code, 1)
                self.assertEqual(checks["before:bth-recovery.service"], "FAILED")
                self.assertEqual(checks["bth_helper_check"], "SKIPPED")

    def test_remote_shell_detects_file_drift_after_helper(self):
        code, checks = self.shell('''
hash_matches() { [ "$phase" = before ] || [ "$2" != /opt/timeweb-reality/config.json ]; }
''')
        self.assertEqual(code, 1)
        self.assertEqual(checks["bth_helper_check"], "PASSED")
        self.assertEqual(checks["after:xray_config"], "FAILED")

    def test_remote_shell_detects_xray_restart(self):
        code, checks = self.shell('''
eval "$(declare -f property | sed '1s/property/original_property/')"
property() {
    if [ "$phase" = after ] && [ "$1" = MainPID ]; then printf 654
    else original_property "$@"; fi
}
''')
        self.assertEqual(code, 1)
        self.assertEqual(checks["unit_generation_stable"], "FAILED")

    def test_fresh_namespace_checks_identity_inode_and_pinned_fd(self):
        functions = preflight.REMOTE_SCRIPT.split("\nfiles before\n", 1)[0]
        setup = r'''
original=container-pid-start-image
pid=321
ns_path=/synthetic/fd/3
inode='net:[123]'
identity() { printf '%s' "${IDENTITY:-container-pid-start-image}"; }
readlink() {
    if [ "$1" = /proc/321/ns/net ]; then printf '%s' "${LIVE_INODE:-net:[123]}"
    else printf '%s' "${PIN_INODE:-net:[123]}"; fi
}
nsenter() {
    [ "$*" = '--net=/synthetic/fd/3 -- ip -j link show dev wg-home' ] &&
    [ "${NO_INTERFACE:-0}" = 0 ]
}
'''
        for override, expected in (("", 0), ("IDENTITY=changed-container-pid-start-image", 1),
                                   ("LIVE_INODE='net:[456]'", 1), ("PIN_INODE='net:[456]'", 1),
                                   ("NO_INTERFACE=1", 1)):
            with self.subTest(override=override):
                result = LOCAL_RUN(["/bin/bash", "--noprofile", "--norc"],
                                   input=(functions + setup + override + "\nfresh_namespace\n").encode(),
                                   capture_output=True, timeout=5, env={"PATH": "/usr/bin:/bin"})
                self.assertEqual(result.returncode, expected)
                self.assertEqual(result.stdout, b"")
        self.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
