# TimeWeb -> Cenuta WireGuard WSS fallback

This is a backup transport for both TimeWeb -> Cenuta WireGuard paths:
`wg-relay/wg-up-cenuta` and the userspace WireGuard outbound `wg-cenuta` in
`xray-timeweb-reality`. Client profiles remain independent of the carrier.
Native mode uses `89.252.153.129:51840/UDP`; backup mode maps the relay peer
to `127.0.0.1:51922/UDP` and Xray to `127.0.0.1:51924/UDP`, both carried over
mutual-TLS WSS on TCP/8443.

The Cenuta WSS server is restricted to `127.0.0.1:51840`; it is not a general
proxy. The TimeWeb wrapper maintains a `/32` eth0 bypass route for the WSS
carrier so the carrier cannot recurse into `wg-up-cenuta`.

The Cenuta private CA must be installed in the TimeWeb system trust store as
`/usr/local/share/ca-certificates/timeweb-cenuta-wg-fallback-ca.crt`, followed
by `update-ca-certificates`. The client keeps `--tls-verify-certificate`; do
not replace this with disabled verification. The controller proves a switch by
sending a bound ICMP probe to `10.40.40.1` through the local WSS listener and
then verifying that the WireGuard endpoint is still local. A new handshake is
not required because an existing WireGuard session may carry the probe.

Controls on TimeWeb:

```sh
/usr/local/sbin/timeweb-cenuta-wg-transport status
/usr/local/sbin/timeweb-cenuta-wg-transport backup
/usr/local/sbin/timeweb-cenuta-wg-transport native
```

The loopback console must call
`/usr/local/sbin/timeweb-cenuta-wg-console-transport`. Its mutating actions
run in a dedicated root oneshot unit; the console process itself retains no
write permission to `/opt/timeweb-reality`.

`backup` starts both WSS clients and changes both endpoints, first validating
the Xray JSON. `native` restores the Xray UDP endpoint and stops both WSS
clients before restoring the relay peer endpoint. A partial state is reported
as unavailable to the console. Both controllers record their selected mode in
`/var/lib/vpn-uplink-pilot/transport-state.json` for the monitoring exporter.
Before applying `backup`, the controller waits up to six seconds for the
namespace-local UDP listener and the WSS carrier bypass route. It leaves the
native endpoint unchanged when either readiness check does not pass. If the
WSS peer probe cannot be established, it restores native UDP and stops the
WSS client without recording `backup` mode.

The Cenuta monitoring pilot may call `backup` automatically after two
consecutive qualified native-UDP failures. It never returns to native on its
own. The decision state is `/var/lib/vpn-uplink-pilot/cenuta-auto-failover.json`;
Fornex remains manual.
