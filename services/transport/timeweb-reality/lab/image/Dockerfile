FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl iproute2 iptables wireguard-tools openssl \
    procps util-linux python3-venv tcpdump \
    && python3 -m venv /opt/lab/.venv \
    && /opt/lab/.venv/bin/pip install --no-cache-dir dnspython==2.8.0 \
    && rm -rf /var/lib/apt/lists/*
RUN /opt/lab/.venv/bin/pip install --no-cache-dir h2==4.3.0
CMD ["bash"]
