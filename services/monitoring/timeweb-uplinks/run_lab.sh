set -Eeuo pipefail
timeout 180 unshare --net bash /root/uplink-guards-stage-20260911/guards_lab.sh
