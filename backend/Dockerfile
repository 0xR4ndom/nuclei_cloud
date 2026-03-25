# ─── Stage 1: Python dependency builder ──────────────────────────────────────
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─── Stage 2: Nuclei binary fetcher ──────────────────────────────────────────
FROM alpine:3.20 AS nuclei-fetcher

# Pin nuclei version for reproducible builds — update via ARG at build time:
# docker build --build-arg NUCLEI_VERSION=3.3.0 ...
ARG NUCLEI_VERSION=3.2.9

RUN apk add --no-cache wget unzip ca-certificates && \
    wget -q "https://github.com/projectdiscovery/nuclei/releases/download/v${NUCLEI_VERSION}/nuclei_${NUCLEI_VERSION}_linux_amd64.zip" \
        -O /tmp/nuclei.zip && \
    unzip -q /tmp/nuclei.zip -d /tmp/nuclei-bin/ && \
    install -m 0755 /tmp/nuclei-bin/nuclei /usr/local/bin/nuclei && \
    rm -rf /tmp/nuclei.zip /tmp/nuclei-bin


# ─── Stage 3: Runtime image ───────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git ca-certificates libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd --system --gid 1001 nucleicloud && \
    useradd --system --uid 1001 --gid 1001 --no-create-home nucleicloud

# Copy Python packages from builder
COPY --from=builder /install /usr/local

# Copy nuclei binary from fetcher
COPY --from=nuclei-fetcher /usr/local/bin/nuclei /usr/local/bin/nuclei

WORKDIR /app

# Copy source code
COPY --chown=nucleicloud:nucleicloud . .

# Create runtime directories with correct ownership
RUN mkdir -p /opt/nuclei-templates /opt/custom-templates /opt/nuclei-output && \
    chown -R nucleicloud:nucleicloud /opt/nuclei-templates /opt/custom-templates /opt/nuclei-output

USER nucleicloud

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--no-access-log"]
