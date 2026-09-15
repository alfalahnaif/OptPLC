# OptPLC reference backend image (plan item P0-05).

# Stage 1: build the MATIEC IEC 61131-3 compiler from a pinned upstream commit.
FROM python:3.11-slim-bookworm AS builder

ARG MATIEC_REPO=https://github.com/beremiz/matiec.git
# Upstream HEAD resolved on 2026-09-14 with `git ls-remote <repo> HEAD`.
ARG MATIEC_COMMIT=79410c7660cf337ec7991a167e53ef141a26caf9

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates gcc g++ make git bison flex autoconf automake \
    && rm -rf /var/lib/apt/lists/*

RUN git init /matiec \
    && cd /matiec \
    && git remote add origin "$MATIEC_REPO" \
    && git fetch --depth 1 origin "$MATIEC_COMMIT" \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "$MATIEC_COMMIT" \
    && autoreconf -i \
    && ./configure \
    && make -j"$(nproc)" \
    && install -m 0755 /matiec/iec2c /usr/local/bin/iec2c \
    && mkdir -p /usr/local/share/matiec \
    && cp -r /matiec/lib /usr/local/share/matiec/lib \
    && echo "$MATIEC_COMMIT" > /usr/local/share/matiec/COMMIT

# Stage 2: runtime. No PLCverif binary is installed; formal validation reports it as unavailable.
FROM python:3.11-slim-bookworm

WORKDIR /app

COPY --from=builder /usr/local/bin/iec2c /usr/local/bin/iec2c
COPY --from=builder /usr/local/share/matiec /usr/local/share/matiec

# Hashed lock compiled from backend/requirements-docker.in with `uv pip compile --generate-hashes`.
# The extra index serves the CPU-only torch wheel pinned in the lock.
COPY backend/requirements-docker.lock .
RUN python -m pip install --no-cache-dir --require-hashes --default-timeout=1000 --retries 10 \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements-docker.lock

COPY backend/ .

# Run as an unprivileged user. Each compile writes its C output to its own temp dir (P1-02, D-030),
# so the MATIEC install stays owned by root and read-only for the app user.
RUN useradd --create-home --uid 10001 optplc \
    && mkdir -p /app/rag_db \
    && chown -R optplc:optplc /app
USER optplc

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
