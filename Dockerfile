# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV XDG_CACHE_HOME=/var/cache/latexapp
RUN mkdir -p /var/cache/latexapp

# tectonic's runtime shared-library deps (per its own docs: fontconfig,
# freetype2, graphite2, harfbuzz, ICU4C, libpng, zlib, openssl) — the ICU
# runtime package is version-numbered per Debian release (e.g. libicu72 on
# bookworm), so libicu-dev is used here instead of guessing the exact
# number; it pulls in whatever runtime .so the base image's release needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev libssl-dev python3-dev gcc \
    curl ca-certificates \
    libfontconfig1 libfreetype6 libgraphite2-3 libharfbuzz0b libpng16-16 libicu-dev zlib1g \
    && rm -rf /var/lib/apt/lists/*

# --- tectonic: pinned release binary, checksum-verified ---
# A self-contained, single-binary LaTeX engine (fetches/caches only the
# packages a given document needs) instead of a multi-GB TeX Live install.
ARG TECTONIC_VERSION=0.17.0
ARG TECTONIC_SHA256=1a715688baf591e650c8aeb160ae934e181685eecbb38b317de30b269ac5d606
RUN curl -fsSL -o /tmp/tectonic.tar.gz \
      "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-gnu.tar.gz" \
    && echo "${TECTONIC_SHA256}  /tmp/tectonic.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/tectonic.tar.gz -C /usr/local/bin tectonic \
    && chmod +x /usr/local/bin/tectonic \
    && rm /tmp/tectonic.tar.gz \
    && tectonic --version

# Pre-warm tectonic's format/package cache at build time (into
# XDG_CACHE_HOME, which persists in this image layer) so the *first* real
# compile a user runs against a fresh container isn't stuck downloading
# tectonic's bootstrap bundle: that cold-start alone measured ~55s
# locally, well past a request-level timeout. Baking it into the image
# means every container start already has a warm cache, without needing a
# Railway volume (which wouldn't persist this across redeploys anyway).
RUN mkdir -p /tmp/warmup && \
    printf '%s\n' \
      '\documentclass{article}' \
      '\usepackage{amsmath,amssymb,graphicx}' \
      '\begin{document}' \
      '$x^2 + y^2 = z^2$' \
      '\end{document}' \
      > /tmp/warmup/warmup.tex && \
    tectonic --outdir /tmp/warmup /tmp/warmup/warmup.tex && \
    rm -rf /tmp/warmup

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
