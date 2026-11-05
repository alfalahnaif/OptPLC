FROM debian:trixie-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends xz-utils libxml2 libedit2 libgmp10 libstdc++6 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY nuXmv-2.2.0-linux64.tar.xz /tmp/nuxmv.tar.xz
RUN mkdir -p /opt/nuxmv && tar -xJf /tmp/nuxmv.tar.xz -C /opt/nuxmv --strip-components=1 && rm /tmp/nuxmv.tar.xz
ENTRYPOINT ["/opt/nuxmv/usr/local/bin/nuXmv"]
