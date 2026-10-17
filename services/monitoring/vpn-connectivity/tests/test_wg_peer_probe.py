import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "peer", Path(__file__).resolve().parents[1] / "probe/wg_peer_probe.py"
)
peer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(peer)

dashboard_spec = importlib.util.spec_from_file_location(
    "dashboards", Path(__file__).resolve().parents[1] / "grafana/dashboard_source/build_device_dashboards.py"
)
dashboards = importlib.util.module_from_spec(dashboard_spec)
dashboard_spec.loader.exec_module(dashboards)


class PeerTests(unittest.TestCase):
    def test_host_namespace_probe_does_not_read_container_or_private_keys(self):
        script = peer.remote_script("timeweb-s2s", [dict(id="pilot", interface="wg-s2s", address="10.60.60.3/32")])
        self.assertNotIn("docker", script)
        self.assertNotIn("private-key", script)
        self.assertNotIn("'dump'", script)
        self.assertIn("ifindex", script)
        self.assertIn("public-key", script)
        compile(script, "host-probe", "exec")

    def setUp(self):
        self.a = dict(
            identity="a",
            present=True,
            mono=10,
            server_time=100,
            rx=100,
            tx=200,
            handshake=50,
            observed=100,
        )
        self.b = dict(self.a, mono=25, server_time=115, rx=130, tx=260)

    def sample_set(self, **overrides):
        samples = {}
        for item in peer.PEERS:
            sample = dict(self.b, handshake=0, rates=(0, 0))
            sample.update(overrides.get(item["id"], {}))
            samples[item["id"]] = sample
        return samples

    def xray_sample_set(self, **overrides):
        samples = {}
        for item in peer.XRAY_CLIENTS:
            sample = dict(present=True, mono=25, server_time=115, activity=0, observed=115)
            sample.update(overrides.get(item["id"], {}))
            samples[item["id"]] = sample
        return samples

    def test_direction(self):
        self.assertEqual(peer.speeds(self.a, self.b), (32, 16))

    def test_first_sample_has_no_rate(self):
        self.assertIsNone(peer.speeds(None, self.b))

    def test_generation_or_counter_reset_invalidates_rate(self):
        self.assertIsNone(peer.speeds(self.a, dict(self.b, identity="b")))
        self.assertIsNone(peer.speeds(self.a, dict(self.b, rx=0)))

    def test_active_device_uses_newest_fresh_handshake(self):
        samples = self.sample_set(
            **{
                "macbook-wg-tw-fx": dict(self.b, handshake=100, rates=(32, 16)),
                "macbook-wg-tw-bth": dict(self.b, handshake=108, rates=(64, 24)),
            }
        )
        values, active = peer.device_values("macbook", samples, self.xray_sample_set(), 26)
        self.assertEqual(active["tunnel"], "WG-TW-BTH")
        self.assertEqual(values["active_tunnel_code"], 3)
        self.assertEqual(values["activity"], 1)
        self.assertEqual(values["active_client_in_bps"], 64)

    def test_awg31_competes_with_timeweb_for_the_active_tunnel(self):
        samples = self.sample_set(
            **{
                "iphone-sergey-wg-tw-fx": dict(self.b, handshake=100, rates=(32, 16)),
                "iphone-awg31-fx": dict(self.b, handshake=110, rates=(64, 24)),
            }
        )
        values, active = peer.device_values("iphone", samples, {}, 26)
        self.assertEqual(active["tunnel"], "AWG31-FX")
        self.assertEqual(active["source"], "fornex-awg31")
        self.assertEqual(values["active_tunnel_code"], 3)
        self.assertEqual(values["active_source_code"], 2)

    def test_missing_second_source_does_not_claim_no_active_tunnel(self):
        samples = self.sample_set()
        samples.pop("iphone-awg31-fx")
        values, active = peer.device_values("iphone", samples, {}, 26)
        self.assertIsNone(active)
        self.assertEqual(
            values,
            {"activity": 0, "active_tunnel_code": -1, "active_source_code": -1},
        )

    def test_device_without_fresh_handshake_is_not_active(self):
        samples = self.sample_set()
        values, active = peer.device_values("macbook", samples, self.xray_sample_set(), 26)
        self.assertIsNone(active)
        self.assertEqual(
            values,
            {"activity": 2, "active_tunnel_code": 0, "active_source_code": 0},
        )

    def test_missing_peer_is_not_reported_as_disconnected_client(self):
        values = peer.peer_values(dict(self.b, present=False), 26)
        self.assertEqual(values["peer_present"], 0)
        self.assertEqual(values["activity"], 0)
        self.assertNotIn("client_in_bps", values)

    def test_empty_collection_is_unknown_not_no_connection(self):
        values, active = peer.device_values("iphone", {}, {}, 26)
        self.assertIsNone(active)
        self.assertEqual(
            values,
            {"activity": 0, "active_tunnel_code": -1, "active_source_code": -1},
        )

    def test_metrics_are_labeled_by_device_and_tunnel(self):
        samples = self.sample_set(
            **{
                "macbook-wg-tw-fx": dict(self.b, handshake=100, rates=(32, 16)),
            }
        )
        output = peer.prometheus_metrics(samples, 26)
        self.assertIn(
            'vpn_device_active_tunnel_code{device="macbook",device_name="MacBook Sergey"} 1',
            output,
        )
        self.assertIn(
            'device="macbook",device_name="MacBook Sergey",interface="wg0",source="timeweb-wg",tunnel="WG-TW-FX"',
            output,
        )
        self.assertIn(
            'vpn_source_observation_fresh{source="fornex-awg31",source_name="Fornex AWG 3.1"} 0',
            output,
        )
        self.assertIn("vpn_wg_peer_client_in_bps", output)
        self.assertNotIn("vpn_macbook_wg_", output)

    def test_client_health_is_not_claimed(self):
        self.assertNotIn("client_health", peer.prometheus_metrics({}, 26))

    def test_xray_activity_is_exported_as_a_device_tunnel(self):
        xray = self.xray_sample_set(
            **{
                "iphone-xray-tw-cen": dict(
                    present=True,
                    mono=25,
                    server_time=115,
                    activity=112,
                    observed=115,
                )
            }
        )
        output = peer.prometheus_metrics(
            self.sample_set(),
            26,
            {"timeweb-xray": 25},
            xray,
        )
        self.assertIn(
            'vpn_xray_client_activity{device="iphone",device_name="iPhone Sergey",source="timeweb-xray",tunnel="XRAY-TW-CEN"} 3',
            output,
        )
        self.assertIn(
            'vpn_device_active_tunnel{device="iphone",device_name="iPhone Sergey",source="timeweb-xray",tunnel="XRAY-TW-CEN · access <90s"} 1',
            output,
        )
        self.assertIn('vpn_device_activity{device="iphone",device_name="iPhone Sergey"} 3', output)

    def test_old_xray_access_does_not_mark_a_stopped_tunnel_active(self):
        xray = self.xray_sample_set(
            **{"macbook-socks-tw-flex": dict(mono=25, server_time=500, activity=174)}
        )
        self.assertEqual(peer.xray_client_values(xray["macbook-socks-tw-flex"], 26)["activity"], 2)
        values, active = peer.device_values("macbook", self.sample_set(), xray, 26)
        self.assertIsNone(active)
        self.assertEqual(values["active_tunnel_code"], 0)
        self.assertEqual(values["activity"], 2)

    def test_flex_route_is_visible_only_with_fresh_controller_readback(self):
        xray = self.xray_sample_set(
            **{"macbook-socks-tw-flex": dict(mono=25, server_time=115, activity=112)}
        )
        route = {"exit": "cen", "ru_direct": True, "observed": "ready", "mono": 25}
        values, active = peer.device_values("macbook", self.sample_set(), xray, 26, {"macbook": route})
        self.assertEqual(values["active_tunnel_code"], 84)
        self.assertEqual(values["activity"], 3)
        self.assertEqual(active["tunnel"], "SOCKS-TW-FLEX · CEN · RU TW · access <90s")
        output = peer.prometheus_metrics(self.sample_set(), 26, xray_samples=xray, flex_sample={"macbook": route})
        self.assertIn('vpn_flex_route_exit_code{device="macbook"} 2', output)
        self.assertIn('vpn_flex_route_ru_direct{device="macbook"} 1', output)

        xray["macbook-socks-tw-flex"]["mono"] = 79
        unknown, active = peer.device_values("macbook", self.sample_set(), xray, 80, {"macbook": route})
        self.assertEqual(unknown["active_tunnel_code"], 8)
        self.assertEqual(active["tunnel"], "SOCKS-TW-FLEX · access <90s")
        stale = peer.prometheus_metrics(self.sample_set(), 80, flex_sample={"macbook": route})
        self.assertIn('vpn_flex_route_observation_fresh{device="macbook"} 0', stale)
        self.assertNotIn("vpn_flex_route_exit_code", stale)

    def test_flex_status_requires_verified_readback(self):
        with patch.object(peer.subprocess, "run") as run, patch.object(peer.time, "monotonic", return_value=25):
            ready = {"exit": "fx", "ru_direct": False, "observed": "ready"}
            run.return_value.stdout = json.dumps({"devices": {name: {"route": "ready", "observed": ready}
                                                              for name in ("macbook", "iphone12", "macmini")}})
            self.assertEqual(peer.collect_flex_status()["iphone"]["mono"], 25)
            run.return_value.stdout = json.dumps({"devices": {"macbook": {"route": "ready", "observed": ready}}})
            with self.assertRaises(ValueError):
                peer.collect_flex_status()

    def test_inventory_covers_each_registry_device_once(self):
        self.assertEqual(len(peer.DEVICES), 22)
        self.assertEqual(len(peer.PEERS), 49)
        self.assertEqual(len(peer.XRAY_CLIENTS), 15)
        self.assertEqual(len({item["device"] for item in peer.PEERS}), 22)
        self.assertEqual(len({item["address"] for item in peer.PEERS}), 49)
        self.assertEqual(peer.DEVICES[:3], ("macbook", "iphone", "macmini"))
        self.assertEqual(len(peer.PEERS_BY_SOURCE["timeweb-wg"]), 36)
        self.assertEqual(len(peer.PEERS_BY_SOURCE["fornex-awg31"]), 11)
        self.assertEqual(len(peer.PEERS_BY_SOURCE["timeweb-s2s"]), 2)
        self.assertEqual({item["address"] for item in peer.PEERS_BY_SOURCE["timeweb-s2s"]},
                         {"10.60.60.2/32", "10.60.60.3/32"})
        self.assertEqual({item["tunnel"] for item in peer.PEERS_BY_SOURCE["timeweb-s2s"]},
                         {"WG-S2S-TW (LAN/IPIP)"})
        self.assertIn("84", dashboards.DEVICES[0]["tunnel_codes"])
        self.assertEqual(dashboards.DEVICES[0]["tunnel_codes"]["84"],
                         ("SOCKS-TW-FLEX · CEN · RU TW · access <90s", "yellow"))

    def test_device_tile_uses_responsive_compact_canvas(self):
        dashboard = json.loads(dashboards.MAIN_DASHBOARD.read_text(encoding="utf-8"))
        template = dashboard["spec"]["elements"]["panel-100"]
        tile = dashboards.device_tile(template, dashboards.DEVICES[0], 100)

        self.assertEqual(tile["spec"]["vizConfig"]["group"], "canvas")
        elements = tile["spec"]["vizConfig"]["spec"]["options"]["root"]["elements"]
        self.assertEqual(
            [element["name"] for element in elements],
            [
                "active-tunnel",
                "observation-kind",
                "in-label",
                "out-label",
                "observation-age",
                "in-value",
                "out-value",
            ],
        )
        self.assertTrue(
            all(element["constraint"]["horizontal"] == "scale" for element in elements)
        )
        self.assertEqual(
            tile["spec"]["vizConfig"]["spec"]["fieldConfig"]["overrides"][0]["properties"][0]["value"][0]["options"]["0"]["text"],
            "Нет активного наблюдаемого тоннеля",
        )

    def test_newer_xray_activity_wins_over_old_wireguard_handshake(self):
        wg = self.sample_set(
            **{
                "iphone-sergey-wg-tw-fx": dict(self.b, handshake=100, rates=(32, 16)),
            }
        )
        xray = self.xray_sample_set(
            **{
                "iphone-xray-tw-cen": dict(
                    present=True,
                    mono=25,
                    server_time=115,
                    activity=112,
                    observed=115,
                )
            }
        )
        values, active = peer.device_values("iphone", wg, xray, 26)
        self.assertEqual(active["tunnel"], "XRAY-TW-CEN · access <90s")
        self.assertEqual(values["active_source_code"], 3)
        self.assertEqual(values["active_observation_kind"], 2)
        self.assertEqual(values["active_rate_valid"], 0)

    def test_old_xray_access_does_not_claim_a_current_session(self):
        xray = self.xray_sample_set(
            **{
                "iphone-xray-tw-cen": dict(
                    present=True,
                    mono=25,
                    server_time=115,
                    activity=-400,
                    observed=115,
                )
            }
        )
        values, active = peer.device_values("iphone", self.sample_set(), xray, 26)
        self.assertIsNone(active)
        self.assertEqual(values["active_tunnel_code"], 0)

    def test_missing_xray_source_does_not_claim_device_is_inactive(self):
        wg = self.sample_set(
            **{
                "iphone-sergey-wg-tw-fx": dict(self.b, handshake=100, rates=(32, 16)),
            }
        )
        values, active = peer.device_values("iphone", wg, {}, 26)
        self.assertEqual(active["tunnel"], "WG-TW-FX")
        self.assertEqual(values["activity"], 1)


if __name__ == "__main__":
    unittest.main()
