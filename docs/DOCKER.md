# Docker

Docker is now a first-class deployment path for ClawLite. This flow is intentionally closer to `ref/nanobot` today: one image, one compose file, one persisted home directory. The target for later phases is `ref/openclaw` depth: richer setup helpers, optional browser/runtime variants, and heavier container smoke coverage.

## Requirements

- Docker Engine or Docker Desktop
- Docker Compose v2
- Enough disk for the image plus `~/.clawlite`

## Quick Start

From the repository root:

```bash
docker compose build
docker compose run --rm clawlite-cli configure --flow quickstart
docker compose up -d clawlite-gateway
```

Open `http://127.0.0.1:8787`.

ClawLite keeps config and runtime state in a bind mount:

- Host: `~/.clawlite`
- Container: `/root/.clawlite`

That means the normal config path still works inside the container:

```bash
docker compose run --rm clawlite-cli status
docker compose run --rm clawlite-cli run "summarize the latest session state"
docker compose run --rm clawlite-cli provider status
```

## Build Options

The image installs `telegram`, `media`, `observability`, and `runtime` extras by default. Override them with build args if you want a different surface:

```bash
CLAWLITE_PIP_EXTRAS=telegram,media,observability,runtime docker compose build
```

To bake Playwright + Chromium into the image:

```bash
CLAWLITE_PIP_EXTRAS=browser,telegram,media,observability \
CLAWLITE_INSTALL_BROWSER=1 \
docker compose build
```

The `runtime` extra installs the Redis Python client used by the optional Redis bus backend.

## Local Providers from the Container

The compose file adds `host.docker.internal:host-gateway` so the container can reach providers running on the host machine.

Examples:

- Ollama on host: `http://host.docker.internal:11434/v1`
- vLLM on host: `http://host.docker.internal:8000/v1`

Use those URLs in ClawLite config instead of `127.0.0.1`, because inside the container `127.0.0.1` refers to the container itself.

## Optional Redis Bus

ClawLite's runtime can scale the internal bus through Redis. The compose file now includes an optional `redis` profile:

```bash
CLAWLITE_BUS_BACKEND=redis docker compose --profile redis up -d
```

Default env wiring in the compose file:

- `CLAWLITE_BUS_BACKEND=inprocess`
- `CLAWLITE_BUS_REDIS_URL=redis://redis:6379/0`
- `CLAWLITE_BUS_REDIS_PREFIX=clawlite:bus`

If you want Redis enabled all the time, set those env vars before running `docker compose up` or place them in your shell environment.

## Security Notes

- The gateway binds `0.0.0.0` inside the container so Docker port publishing works.
- The compose services drop `NET_ADMIN` and `NET_RAW` and enable `no-new-privileges`.
- If you expose port `8787` beyond local development, configure gateway auth before doing so.
- `clawlite-cli` shares the gateway network namespace, similar to the convenience pattern used by `ref/openclaw`. Treat that as the same trust boundary.

## Current Scope

What this Docker path covers now:

- local build + compose startup
- persisted config/state under `~/.clawlite`
- gateway healthcheck via `/health`
- optional CLI sidecar container
- host access to local Ollama/vLLM
- optional Redis bus profile with persisted Redis data

What remains for later parity work:

- setup helper script similar to `openclaw/docker-setup.sh`
- CI container build smoke
- rootless image variant
- sandbox/browser-optimized runtime images
