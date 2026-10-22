import copy
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("backup_under_test", ROOT / "run_backup.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
RUN = "2026-09-13T160000Z_current-config"


def archive(files, extra=()):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for info in extra:
            tar.addfile(info)
    return buf.getvalue()


def sums(files):
    return "".join(backup.digest(data) + "  " + name + "\n" for name, data in sorted(files.items())).encode()


def metadata(files):
    return "".join("f\t644\t0\t0\t" + name + "\t\0" for name in files).encode()


def fixture(host, monitoring=None):
    files = {name: b"fixture-not-a-secret\n" for name in backup.REQUIRED[host]}
    if host == "timeweb":
        contract = {"hashes": {}}
        if monitoring:
            data = b"[]\n"
            contract["hashes"]["rules_with_monitoring"] = backup.digest(data)
            if monitoring != "missing":
                files["opt/timeweb-reality/bth-recovery/rules.monitoring.baseline"] = (
                    b"corrupt" if monitoring == "corrupt" else data)
        files["opt/timeweb-reality/bth-recovery/contract.json"] = json.dumps(contract).encode()
    bundle = {
        "schema-version.txt": b"3\n", "host.txt": host.encode(), "capture-errors.txt": b"0\n",
        "host-files.tar": archive(files), "host-source-before.sha256": sums(files),
        "host-source-after.sha256": sums(files), "host-source-final.sha256": sums(files),
        "host-metadata-before.nul": metadata(files), "host-metadata-after.nul": metadata(files),
        "host-metadata-final.nul": metadata(files),
    }
    runtime = {name: b"[]" for name in (
        "host-routes4.json", "host-routes6.json", "host-rules4.json", "host-rules6.json",
        "host-nft.json", "wg-routes4.json", "wg-routes6.json", "wg-rules4.json", "wg-rules6.json", "wg-nft.json")}
    runtime.update({name: b"unchanged" for name in (
        "boot-id.txt", "host-iptables.txt", "host-ip6tables.txt", "wg-runtime.conf", "wg-unit.txt",
        "wg-netns.txt", "wg-iptables.txt", "wg-ip6tables.txt", "xray-unit.txt",
        "awg-runtime.conf", "awg-firewall.txt")})
    runtime["bth-contract.txt"] = b"BTH_CONTRACT_VALID\n"
    runtime["commands.tsv"] = b"check.txt\t0\n"
    if host != "cenuta":
        names = backup.EXPECTED_CONTAINERS[host]
        bundle["container-inventory.txt"] = "\n".join(sorted(names)).encode()
        rows = [{"Name": "/" + name, "Id": name, "Image": "same", "Config": {}, "HostConfig": {},
                 "Mounts": [], "NetworkSettings": {"Networks": {}},
                 "State": {"Pid": 100, "Running": True, "StartedAt": "same"}} for name in names]
        runtime["docker-inspect.json"] = json.dumps(rows).encode()
        runtime["docker-networks.json"] = b"[]"
        for name in names - {"wg-exit", "wg-relay"}:
            config = {path: files.get(path, b"fixture") for path in backup.REQUIRED_CONTAINER[name]}
            bundle["containers/" + name + ".tar"] = archive(config)
            bundle["containers/" + name + ".before.sha256"] = sums(config)
            bundle["containers/" + name + ".after.sha256"] = sums(config)
            bundle["containers/" + name + ".final.sha256"] = sums(config)
            for when in ("before", "after", "final"):
                bundle["containers/" + name + ".metadata-" + when + ".nul"] = metadata(config)
    for state in ("state-before", "state-after"):
        bundle.update({state + "/" + name: data for name, data in runtime.items()})
    return bundle, files


def test_pilot_backup_requires_whole_bundle_if_any_file_exists():
    assert backup.pilot_required("timeweb", {}) == []
    files = {name: b"fixture" for name in backup.S2S_REQUIRED}
    assert backup.pilot_required("timeweb", files) == backup.S2S_REQUIRED
    for missing in backup.S2S_REQUIRED:
        with __import__("pytest").raises(ValueError, match="S2S"):
            backup.pilot_required("timeweb", {k: v for k, v in files.items() if k != missing})
    assert backup.pilot_required("fornex", files) == []


def test_s2s_console_backup_requires_code_state_and_both_private_identities():
    assert backup.s2s_console_required("timeweb", {}) == []
    files = {name: b"fixture" for name in backup.S2S_CONSOLE_REQUIRED}
    assert backup.s2s_console_required("timeweb", files) == backup.S2S_CONSOLE_REQUIRED
    for missing in backup.S2S_CONSOLE_REQUIRED:
        with __import__("pytest").raises(ValueError, match="S2S console"):
            backup.s2s_console_required("timeweb", {k:v for k,v in files.items() if k != missing})
    assert backup.s2s_console_required("fornex", files) == []


def test_sstp_backup_requires_entire_owned_manifest_without_external_paths():
    import pytest
    assert backup.sstp_required("timeweb", {}) == []
    files = {name: b"fixture" for name in backup.SSTP_REQUIRED}
    bound = {"/"+name: backup.digest(value) for name,value in files.items()
             if name != "etc/sstp-timeweb/manifest.json"}
    files["etc/sstp-timeweb/manifest.json"] = json.dumps({"files":bound}).encode()
    assert set(backup.sstp_required("timeweb", files)) == set(backup.SSTP_REQUIRED)
    for missing in backup.SSTP_REQUIRED:
        with pytest.raises(ValueError,match="SSTP"):
            backup.sstp_required("timeweb", {n:v for n,v in files.items() if n != missing})
    broken = dict(files, **{"etc/sstp-timeweb/server.key":b"drift"})
    with pytest.raises(ValueError,match="SSTP"):
        backup.sstp_required("timeweb", broken)
    bound["/etc/shadow"] = "a"*64
    files["etc/sstp-timeweb/manifest.json"] = json.dumps({"files":bound}).encode()
    with pytest.raises(ValueError,match="SSTP"):
        backup.sstp_required("timeweb", files)
    assert backup.sstp_required("fornex", files) == []


def test_new_ip_sstp_backup_requires_netplan_and_fstab():
    import pytest
    files={name:b"fixture" for name in backup.SSTP_REQUIRED}
    manifest=dict(endpoint='91.222.238.208',files={
        '/'+name:backup.digest(value) for name,value in files.items()
        if name!='etc/sstp-timeweb/manifest.json'})
    files['etc/sstp-timeweb/manifest.json']=json.dumps(manifest).encode()
    with pytest.raises(ValueError,match='SSTP persistent network'):
        backup.sstp_required('timeweb',files)
    files['etc/netplan/90-sstp-timeweb-additional-ip.yaml']=b'network: {}'
    with pytest.raises(ValueError,match='SSTP persistent network'):
        backup.sstp_required('timeweb',files)
    files['etc/fstab']=b'/swapfile-timeweb-maintenance none swap sw 0 0'
    assert {'etc/fstab','etc/netplan/90-sstp-timeweb-additional-ip.yaml'}<=set(backup.sstp_required('timeweb',files))


def test_split_sstp_backup_requires_connector_hooks_and_exact_recovery_dependency():
    import pytest
    files={name:b'fixture' for name in backup.SSTP_REQUIRED+backup.SSTP_SPLIT_REQUIRED}
    bound={'/'+name:backup.digest(value) for name,value in files.items() if name!='etc/sstp-timeweb/manifest.json'}
    files['etc/sstp-timeweb/manifest.json']=json.dumps(dict(files=bound,split_enabled=True)).encode()
    assert set(backup.sstp_required('timeweb',files))==set(backup.SSTP_REQUIRED+backup.SSTP_SPLIT_REQUIRED)
    for name in backup.SSTP_SPLIT_REQUIRED:
        with pytest.raises(ValueError):backup.sstp_required('timeweb',{k:v for k,v in files.items() if k!=name})


def write_bundle(folder, bundle):
    bundle = copy.deepcopy(bundle)
    bundle["SHA256SUMS"] = sums(bundle)
    data = archive({RUN + "/" + k: v for k, v in bundle.items()})
    (folder / "backup.tar.gz").write_bytes(data)
    (folder / "remote-sha256.txt").write_text(backup.digest(data))


class BackupTests(unittest.TestCase):
    def verify(self, host, bundle):
        with tempfile.TemporaryDirectory() as tmp, patch.object(backup.subprocess, "run", side_effect=AssertionError("Offline verify used SSH")):
            folder = Path(tmp)
            write_bundle(folder, bundle)
            return backup.verify(host, RUN, folder)

    def test_pilot_requires_runtime_capture_and_valid_guard(self):
        bundle, files = fixture("timeweb")
        files.update({name: b"fixture" for name in backup.S2S_REQUIRED})
        bundle["host-files.tar"] = archive(files)
        for when in ("before", "after", "final"):
            bundle["host-source-" + when + ".sha256"] = sums(files)
            bundle["host-metadata-" + when + ".nul"] = metadata(files)
        with self.assertRaisesRegex(ValueError, "S2S"):
            self.verify("timeweb", bundle)
        for state in ("state-before", "state-after"):
            bundle[state + "/host-s2s-runtime.conf"] = b"same peer\n"
            bundle[state + "/host-s2s-guard.txt"] = b"S2S_GUARD_VERIFIED\n"
        self.assertEqual(self.verify("timeweb", bundle)["status"], "VERIFIED")
        bundle["state-after/host-s2s-runtime.conf"] = b"foreign peer\n"
        with self.assertRaisesRegex(ValueError, "Runtime drift"):
            self.verify("timeweb", bundle)

    def test_each_host_offline_and_isolated_restore(self):
        for host in backup.HOSTS:
            with self.subTest(host=host):
                report = self.verify(host, fixture(host)[0])
                self.assertEqual(report["status"], "VERIFIED")
                self.assertEqual(report["temporary_restore_files"], len(backup.REQUIRED[host]))

    def test_missing_required_file_even_with_valid_manifest(self):
        bundle, files = fixture("cenuta")
        del files["etc/reality-c3/guard.sh"]
        bundle["host-files.tar"] = archive(files)
        for when in ("before", "after", "final"):
            bundle["host-source-" + when + ".sha256"] = sums(files)
            bundle["host-metadata-" + when + ".nul"] = metadata(files)
        with self.assertRaisesRegex(ValueError, "Missing required"):
            self.verify("cenuta", bundle)

    def test_optional_monitoring_rules_reference(self):
        report = self.verify("timeweb", fixture("timeweb", "valid")[0])
        self.assertEqual(report["temporary_restore_files"], len(backup.REQUIRED["timeweb"]) + 1)
        for variant in ("missing", "corrupt"):
            with self.subTest(variant=variant), self.assertRaisesRegex(ValueError, "Monitoring rules contract mismatch"):
                self.verify("timeweb", fixture("timeweb", variant)[0])

    def test_content_corruption(self):
        bundle, files = fixture("cenuta")
        files["etc/nftables.conf"] = b"corrupted"
        bundle["host-files.tar"] = archive(files)
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.verify("cenuta", bundle)

    def test_source_drift(self):
        bundle, _ = fixture("cenuta")
        bundle["host-source-after.sha256"] += b"changed"
        with self.assertRaisesRegex(ValueError, "source content changed"):
            self.verify("cenuta", bundle)

    def test_metadata_drift(self):
        bundle, _ = fixture("cenuta")
        bundle["host-metadata-after.nul"] = b"changed mode or link"
        with self.assertRaisesRegex(ValueError, "metadata changed"):
            self.verify("cenuta", bundle)

    def test_unlisted_file(self):
        bundle, files = fixture("cenuta")
        files["extra"] = b"unlisted"
        bundle["host-files.tar"] = archive(files)
        with self.assertRaisesRegex(ValueError, "inventory differ"):
            self.verify("cenuta", bundle)

    def test_runtime_route_drift(self):
        bundle, _ = fixture("timeweb")
        bundle["state-after/wg-rules4.json"] = b'[{"priority":42}]'
        with self.assertRaisesRegex(ValueError, "Runtime drift"):
            self.verify("timeweb", bundle)

    def test_awg_peer_order_is_not_runtime_drift(self):
        bundle, _ = fixture("fornex")
        before = (
            b"[Interface]\nPrivateKey = private\n"
            b"[Peer]\nPublicKey = peer-a\nAllowedIPs = 10.83.1.4/32\n"
            b"[Peer]\nPublicKey = peer-b\nAllowedIPs = 10.83.1.5/32\n"
        )
        after = (
            b"[Interface]\nPrivateKey = private\n"
            b"[Peer]\nPublicKey = peer-b\nAllowedIPs = 10.83.1.5/32\n"
            b"[Peer]\nPublicKey = peer-a\nAllowedIPs = 10.83.1.4/32\n"
        )
        bundle["state-before/awg-runtime.conf"] = before
        bundle["state-after/awg-runtime.conf"] = after
        self.verify("fornex", bundle)

        bundle["state-after/awg-runtime.conf"] = (
            b"[Interface]\nPrivateKey = private\n"
            b"[Peer]\nAllowedIPs = 10.83.1.5/32\nPublicKey = peer-b\n"
            b"[Peer]\nAllowedIPs = 10.83.1.4/32\nPublicKey = peer-a\n"
        )
        self.verify("fornex", bundle)

        bundle["state-after/awg-runtime.conf"] = after.replace(b"10.83.1.5", b"10.83.1.99")
        with self.assertRaisesRegex(ValueError, "awg-runtime.conf"):
            self.verify("fornex", bundle)

    def test_bth_failure(self):
        bundle, _ = fixture("timeweb")
        bundle["state-after/bth-contract.txt"] = b"REFUSED"
        with self.assertRaisesRegex(ValueError, "bth-contract-valid"):
            self.verify("timeweb", bundle)

    def test_capture_failure_not_hidden_by_counter(self):
        bundle, _ = fixture("cenuta")
        bundle["state-before/commands.tsv"] = b"nft\t1\n"
        with self.assertRaisesRegex(ValueError, "capture command failed"):
            self.verify("cenuta", bundle)

    def test_container_missing(self):
        bundle, _ = fixture("fornex")
        del bundle["containers/fornex-awg31.tar"]
        with self.assertRaisesRegex(ValueError, "coverage incomplete"):
            self.verify("fornex", bundle)

    def test_mount_order_is_not_drift_but_properties_are(self):
        bundle, _ = fixture("timeweb")
        rows = json.loads(bundle["state-before/docker-inspect.json"])
        rows[0]["Mounts"] = [{"Destination": "/a", "RW": True}, {"Destination": "/b", "RW": False}]
        bundle["state-before/docker-inspect.json"] = json.dumps(rows).encode()
        rows[0]["Mounts"].reverse()
        bundle["state-after/docker-inspect.json"] = json.dumps(rows).encode()
        self.verify("timeweb", bundle)
        rows[0]["Mounts"][0]["RW"] = True
        bundle["state-after/docker-inspect.json"] = json.dumps(rows).encode()
        with self.assertRaisesRegex(ValueError, "Runtime drift"):
            self.verify("timeweb", bundle)

    def test_container_inventory_unknown(self):
        bundle, _ = fixture("fornex")
        bundle["container-inventory.txt"] += b"\nunknown"
        with self.assertRaisesRegex(ValueError, "inventory drift"):
            self.verify("fornex", bundle)

    def test_container_critical_config_missing(self):
        bundle, _ = fixture("fornex")
        stem = "containers/amnezia-xray"
        config = {"opt/config": b"insufficient"}
        bundle[stem + ".tar"] = archive(config)
        for when in ("before", "after", "final"):
            bundle[stem + "." + when + ".sha256"] = sums(config)
            bundle[stem + ".metadata-" + when + ".nul"] = metadata(config)
        with self.assertRaisesRegex(ValueError, "Missing required container"):
            self.verify("fornex", bundle)

    def test_bind_config_split_generation(self):
        bundle, _ = fixture("fornex")
        stem = "containers/fornex-awg31"
        config = {path: b"different-but-validly-hashed" for path in backup.REQUIRED_CONTAINER["fornex-awg31"]}
        bundle[stem + ".tar"] = archive(config)
        for when in ("before", "after", "final"):
            bundle[stem + "." + when + ".sha256"] = sums(config)
        with self.assertRaisesRegex(ValueError, "Bind-mounted"):
            self.verify("fornex", bundle)

    def test_global_final_check_and_archive_modes(self):
        bundle, _ = fixture("cenuta")
        bundle["host-source-final.sha256"] = b"late change"
        with self.assertRaisesRegex(ValueError, "source content changed"):
            self.verify("cenuta", bundle)
        bundle, files = fixture("cenuta")
        for when in ("before", "after", "final"):
            bundle["host-metadata-" + when + ".nul"] = metadata(files).replace(b"644", b"600")
        with self.assertRaisesRegex(ValueError, "Archive metadata differs"):
            self.verify("cenuta", bundle)

    def test_network_address_drift(self):
        bundle, _ = fixture("timeweb")
        rows = json.loads(bundle["state-after/docker-inspect.json"])
        rows[0]["NetworkSettings"]["Networks"] = {"bridge": {"IPAddress": "10.0.0.42"}}
        bundle["state-after/docker-inspect.json"] = json.dumps(rows).encode()
        with self.assertRaisesRegex(ValueError, "Runtime drift"):
            self.verify("timeweb", bundle)

    def test_metadata_only_archive_limit(self):
        info = tarfile.TarInfo("directory")
        info.type = tarfile.DIRTYPE
        with patch.object(backup, "MAX_MEMBERS", 0), self.assertRaisesRegex(ValueError, "metadata exceeds"):
            backup.checked_tar(archive({}, [info]))

    def test_transfer_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write_bundle(folder, fixture("cenuta")[0])
            (folder / "remote-sha256.txt").write_text("0" * 64)
            with self.assertRaisesRegex(ValueError, "transfer checksum"):
                backup.verify("cenuta", RUN, folder)

    def test_wrong_host(self):
        bundle, _ = fixture("cenuta")
        with self.assertRaisesRegex(ValueError, "Wrong backup host"):
            self.verify("timeweb", bundle)

    def test_archive_paths(self):
        for name in ("../outside", "/absolute"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                backup.checked_tar(archive({name: b"test"}))
        duplicate = tarfile.TarInfo("same")
        duplicate.type = tarfile.DIRTYPE
        with self.assertRaises(ValueError):
            backup.checked_tar(archive({"same": b"test"}, [duplicate]))

    def test_links_are_never_extracted(self):
        info = tarfile.TarInfo("link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        self.assertEqual(backup.checked_tar(archive({}, [info])), {})
        info.type = tarfile.LNKTYPE
        with self.assertRaises(ValueError):
            backup.checked_tar(archive({}, [info]))

    def test_byte_limit(self):
        with patch.object(backup, "MAX_BYTES", 1), self.assertRaises(ValueError):
            backup.checked_tar(archive({"large": b"too big"}))

    def test_device_metadata_requires_explicit_exact_allowlist(self):
        info = tarfile.TarInfo("opt/unbound/etc/unbound/dev/null")
        info.type, info.devmajor, info.devminor = tarfile.CHRTYPE, 1, 3
        data = archive({}, [info])
        with self.assertRaises(ValueError):
            backup.checked_tar(data)
        self.assertEqual(backup.checked_tar(data, {info.name: (1, 3)}), {})
        with self.assertRaises(ValueError):
            backup.checked_tar(data, {info.name: (1, 8)})

    def test_escaped_hash_name(self):
        data = b"value"
        manifest = ("\\" + backup.digest(data) + "  a\\\\b\\nc\n").encode()
        self.assertEqual(backup.verify_hashlist(manifest, {"a\\b\nc": data}), 1)


if __name__ == "__main__":
    unittest.main()
