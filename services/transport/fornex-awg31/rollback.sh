#!/bin/sh
printf '%s\n' 'RETIRED: rollback.sh would stop the current 11-peer AWG31 service and disable its restart policy. AWG2 has been removed; stopping AWG31 does not restore AWG2. Review README.md, take a fresh backup of the current release, and prepare a separately reviewed recovery procedure. No bypass flag is supported.' >&2
exit 1

# Historical implementation below is intentionally unreachable; not an AWG2 restore.
set -eu
# Run on Fornex. Stop only the additive service; preserve its files for audit.
docker update --restart=no fornex-awg31
docker stop fornex-awg31
