<div align="center">

<img src="assets/logo.svg" alt="ClawLite" width="120" />

# ClawLite

**Linux/Termux-first AI runtime — built to run, not just respond.**

A production-grade agent runtime combining an HTTP/WebSocket gateway, persistent memory, a cron scheduler, and Telegram-first delivery reliability — all in a single Python process.

[![CI](https://github.com/eobarretooo/ClawLite/actions/workflows/ci.yml/badge.svg)](https://github.com/eobarretooo/ClawLite/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/eobarretooo/ClawLite)](https://github.com/eobarretooo/ClawLite/releases)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3b82f6?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20termux-0ea5e9)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e)](LICENSE)

</div>

---

## What is ClawLite?

Most AI runtimes are built for interactive use — you prompt, you wait, you read. **ClawLite is built for operational use.** It runs continuously, handles incoming messages from multiple channels, executes scheduled tasks, and persists memory — all from a single command.

It was designed for Linux servers and Android Termux environments where reliability, low overhead, and headless operation matter.

---

## Architecture at a Glance

```
         CLI  (clawlite)
   start / run / status / cron / memory
                   |
          Gateway (HTTP + WS)          <-- control plane
          /v1/chat  /api/message
                   |
       .-----------+-----------.
       |                       |
   Scheduler               Channels
   heartbeat                Telegram
   cron / lease
       |
   Persistent Memory
   runtime / backend / monitor
```

---

## Features

| Capability | Details |
|---|---|
| 🌐 **HTTP + WebSocket gateway** | Full control plane with health, status, diagnostics, chat, and control endpoints |
| 🔐 **Auth modes** | `off` · `optional` · `required` — configurable per deployment |
| 📬 **Telegram reliability** | Retry/backoff, deduplication, polling and webhook modes |
| 🗓️ **Cron scheduler** | Lease/claim/finalize semantics for idempotent job execution |
| 💓 **Heartbeat loop** | Periodic state tracking with manual trigger support |
| 🧠 **Persistent memory** | Runtime memory stack with monitoring |
| 🔌 **Provider failover** | Registry-based provider selection with reliability and failover layers |
| 🛠️ **Tools & skills** | Pluggable tool registry and skill integration |
| ⚙️ **Single binary feel** | One `clawlite` entrypoint for everything |

---

## Installation

### From Source (recommended)

```bash
git clone https://github.com/eobarretooo/ClawLite.git
cd ClawLite
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e .
```

> Module entrypoint also available: `python -m clawlite.cli`

### Installer Script

```bash
bash scripts/install.sh
```

The script handles venv creation, bootstrap, and symlinking automatically.

---

## Quickstart

> ⏱️ From zero to running agent in ~2–5 minutes.

**1. Onboard and validate**

```bash
clawlite onboard --wizard
clawlite validate config
clawlite validate provider
```

**2. Start the gateway**

```bash
clawlite start --host 127.0.0.1 --port 8787
```

**3. Send your first message** _(in a new terminal)_

```bash
clawlite run "health check: respond with gateway status"
clawlite status
```

---

## Configuration

Config lives at `~/.clawlite/config.json`. The key sections are:

| Section | What it controls |
|---|---|
| `gateway.auth` | Auth mode (`off` · `optional` · `required`) |
| `providers` | Active provider and fallback chain |
| `channels.telegram` | Mode (`polling` or `webhook`), token, webhook URL |
| `scheduler` | Heartbeat interval, cron defaults |
| `diagnostics` | Token masking, log verbosity |

Environment variables override config values — useful for secrets in CI/CD.

📄 Full reference: [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) · [`docs/config.example.json`](docs/config.example.json)

---

## Gateway Endpoints

| Method | Route | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/v1/status` | Runtime status |
| `GET` | `/v1/diagnostics` | Diagnostics (with token masking) |
| `POST` | `/v1/chat` | Send a message |
| `POST` | `/api/message` | Alias for `/v1/chat` |
| `POST` | `/v1/cron/add` | Add a cron job |
| `GET` | `/v1/cron/list` | List cron jobs |
| `DELETE` | `/v1/cron/{job_id}` | Remove a cron job |
| `POST` | `/v1/control/heartbeat/trigger` | Trigger heartbeat manually |
| `WS` | `/v1/ws` | WebSocket channel |

📄 Full API reference: [`docs/API.md`](docs/API.md)

---

## Testing

```bash
# Full suite (CI canonical)
python -m pytest tests/ -q --tb=short

# Smoke test
bash scripts/smoke_test.sh

# Focused subsets
python -m pytest tests/gateway/test_server.py -q
python -m pytest tests/channels/test_telegram.py -q
python -m pytest tests/scheduler/ -q
```

---

## Status

**✅ Shipped**

- Core CLI and onboarding flow
- HTTP/WebSocket gateway with compatibility aliases
- Telegram reliability with documented semantics
- Cron scheduler with lease/idempotency guarantees
- Heartbeat loop and state persistence
- Persistent memory runtime and monitoring
- Provider registry with failover and reliability layers
- Tools and skills plumbing

**🚧 In Progress**

- Rich dashboard UI *(not yet in scope — `GET /` serves a minimal status page)*

---

## Contributing

Contributions are welcome. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a PR.

- 🐛 **Issues:** [github.com/eobarretooo/ClawLite/issues](https://github.com/eobarretooo/ClawLite/issues)
- 🗺️ **Roadmap:** [`ROADMAP.md`](ROADMAP.md)
- 🔒 **Security:** [`SECURITY.md`](SECURITY.md)

---

## Related Projects

- [OpenClaw](https://github.com/openclaw/openclaw) — upstream project
- [nanobot](https://github.com/HKUDS/nanobot) — lightweight bot runtime
- [memU](https://github.com/NevaMind-AI/memU) — memory layer reference

---

<div align="center">

MIT License © [eobarretooo](https://github.com/eobarretooo)

</div>
