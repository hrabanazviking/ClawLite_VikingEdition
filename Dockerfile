FROM python:3.12-slim-bookworm

ARG CLAWLITE_PIP_EXTRAS="telegram,media,observability,runtime"
ARG CLAWLITE_INSTALL_BROWSER=""
ARG CLAWLITE_UID=1000
ARG CLAWLITE_GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/clawlite \
    PLAYWRIGHT_BROWSERS_PATH=/home/clawlite/.cache/ms-playwright

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      tini && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY clawlite ./clawlite

RUN python -m pip install --upgrade pip && \
    if [ -n "${CLAWLITE_PIP_EXTRAS}" ]; then \
      python -m pip install ".[${CLAWLITE_PIP_EXTRAS}]"; \
    else \
      python -m pip install .; \
    fi

RUN if [ -n "${CLAWLITE_INSTALL_BROWSER}" ]; then \
      python -m playwright install --with-deps chromium; \
    fi

RUN groupadd --gid "${CLAWLITE_GID}" clawlite && \
    useradd --uid "${CLAWLITE_UID}" --gid "${CLAWLITE_GID}" --create-home --home-dir /home/clawlite --shell /bin/bash clawlite && \
    mkdir -p /home/clawlite/.clawlite "${PLAYWRIGHT_BROWSERS_PATH}" && \
    chown -R clawlite:clawlite /home/clawlite

VOLUME ["/home/clawlite/.clawlite"]
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8787/health || exit 1

USER clawlite

ENTRYPOINT ["tini", "--", "clawlite"]
CMD ["status"]
