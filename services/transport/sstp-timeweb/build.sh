#!/bin/bash
# Run inside the pinned disposable amd64 builder, never on the live VPS.
set -Eeuo pipefail
test "$(uname -m)" = x86_64
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gcc make cmake git libssl-dev libpcre2-dev
test "$(git -c safe.directory=/src -C /src rev-parse HEAD)" = b8a3c54aa34434312aa0053686ec37a133fb54e6
prefix=/opt/sstp-timeweb/releases/b8a3c54
cmake -S /src -B /build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" \
    -DIGNORE_GIT=TRUE -DRADIUS=FALSE -DSHAPER=FALSE -DNETSNMP=FALSE \
    -DBUILD_IPOE_DRIVER=FALSE -DBUILD_VLAN_MON_DRIVER=FALSE -DBUILD_PPPOSEQ_DRIVER=FALSE
cmake --build /build -j2
DESTDIR=/out/stage cmake --install /build
mkdir -p "/out/stage$prefix/runtime-libs"
cp -L /usr/lib/x86_64-linux-gnu/libssl.so.3 /usr/lib/x86_64-linux-gnu/libcrypto.so.3 \
    /usr/lib/x86_64-linux-gnu/libpcre2-8.so.0 "/out/stage$prefix/runtime-libs/"
dpkg-query -W > /out/build-packages.txt
find "/out/stage$prefix" -type f -exec sha256sum {} + > /out/build-sha256.txt
tar -C /out/stage -czf /out/accel-ppp-b8a3c54-linux-amd64.tar.gz "opt/sstp-timeweb/releases/b8a3c54"
