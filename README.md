<div align="center">

![https://github.com/hrabanazviking/ClawLite_VikingEdition/assets/894ec475-29cd-4187-b4a7-9595de611e8e.jpg](https://raw.githubusercontent.com/hrabanazviking/ClawLite_VikingEdition/refs/heads/Development/assets/894ec475-29cd-4187-b4a7-9595de611e8e.jpg)

# ClawLite - Viking Edition

**A local-first Python autonomous agent — persistent memory, 20+ LLM providers,<br>real chat channels, and a 24/7 self-healing runtime. No cloud required.**

[Quickstart](#-quickstart) · [Features](#-features) · [Channels](#-channels) · [Providers](#-providers) · [Architecture](#-architecture) · [Docs](#-docs-map) · [Contributing](#-contributing)

</div>

> ### 🤖 Built by AI · Maintained by Vikings
>
> ClawLite Viking Edition is a project built entirely by AI**. Every line of code, every test, every commit was written by an AI agent — the Viking humans supervise, reviews goals, and guides direction. Just one humans and AI building production software together.
>
> This is an ongoing experiment in AI-driven software development at the solo-dev scale.

---

![https://raw.githubusercontent.com/hrabanazviking/ClawLite_VikingEdition/refs/heads/Development/assets/514fdf8c-0e74-4605-9807-709c223a4c5c.jpg](https://raw.githubusercontent.com/hrabanazviking/ClawLite_VikingEdition/refs/heads/Development/assets/514fdf8c-0e74-4605-9807-709c223a4c5c.jpg)

## ⚡ Why ClawLite Viking Edition?

- **Truly local-first** — runs entirely on your machine; no vendor lock-in, no cloud accounts required
- **Real channel adapters out of the box** — Telegram, Discord, Email, WhatsApp, Slack, and IRC
- **Persistent, searchable memory** — hybrid BM25 + vector search, temporal decay, consolidation loop
- **Self-healing runtime** — heartbeat supervisor, dead-letter replay, automatic provider failover
- **Batteries included** — 25+ skills, built-in tools, streaming responses, operator dashboard

---

## 🏁 Quickstart

```bash
# 1. Clone and install
git clone https://github.com/hrabanazviking/ClawLite_VikingEdition.git
cd ClawLite
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e .

# Or install optional integrations up front
python3 -m pip install -e ".[browser,telegram,media,runtime]"

# Optional browser runtime download
python3 -m playwright install chromium

# 2. Configure (interactive wizard — sets provider, gateway, optional Telegram)
clawlite configure

# 3. Start the gateway
clawlite gateway
```

Open **http://127.0.0.1:8787** → live dashboard with chat, automation, memory, and tools.

If you pass `--config path.yaml`, YAML configs work out of the box. Optional runtimes now install via extras: `.[browser]` for Playwright, `.[telegram]` for the Telegram channel, `.[media]` for TTS/PDF helpers, `.[runtime]` for Redis-backed bus support, and `.[observability]` for OTLP/OpenTelemetry exports.
Config profiles are also supported: `clawlite --config ./config.yaml --profile prod status` loads `config.yaml`, overlays `config.prod.yaml` if present, and then applies env vars.

**Android / Termux path:** use `proot-distro` with Ubuntu instead of trying to run the full stack directly on native Termux. The one-shot wrapper is:

```bash
curl -fsSL https://github.com/hrabanazviking/ClawLite_VikingEdition/main/scripts/install_termux_proot.sh | bash
```

If an older `/root/ClawLite` checkout inside Ubuntu has diverged from `origin/main`, the wrapper now preserves it as a timestamped backup and reclones cleanly instead of failing on `git pull --ff-only`.
The Termux wrapper also fetches the latest checkout-sync helper directly from GitHub, so rerunning the one-shot `curl ... | bash` path is the safest update path even when an older local wrapper script is stale.

After that:

```bash
proot-distro login ubuntu --shared-tmp
clawlite configure --flow quickstart
clawlite gateway
```

Full walkthrough: [`docs/TERMUX_PROOT_UBUNTU.md`](docs/TERMUX_PROOT_UBUNTU.md)

```bash
# Or talk to the agent straight from the terminal
clawlite run "hello — what can you do?"
```

### Docker quickstart

ClawLite now ships an official Docker path:

```bash
bash scripts/docker_setup.sh
```

This persists state in `~/.clawlite`, exposes the dashboard on `http://127.0.0.1:8787`, and includes a CLI sidecar for one-shot commands like:

```bash
docker compose run --rm clawlite-cli status
docker compose run --rm clawlite-cli run "summarize the latest session"
```

If you want the Redis bus backend from Docker, enable the `redis` profile and the matching env overrides:

```bash
CLAWLITE_BUS_BACKEND=redis docker compose --profile redis up -d
```

The Docker image now runs as a non-root `clawlite` user by default. If your host UID/GID is not `1000`, export `CLAWLITE_UID` and `CLAWLITE_GID` before building or use the setup helper, which does that automatically.

Full guide: [`docs/DOCKER.md`](docs/DOCKER.md)

---

## ᚹ VikingEdition — Norse Enhancements

This fork (`hrabanazviking/ClawLite_VikingEdition`, branch `Development`) adds a
suite of Norse-themed subsystems that improve security, observability, memory
quality, and reasoning depth. All additions are backward-compatible and gated
behind the new `gateway.viking` config block.

### Persona — Sigrid

The default identity is **Sigrid**, a 21-year-old Heathen Third Path devotee:
INTP, friendly and direct, dark dry humour, expert across technology, science,
esoterica, and the arts. Configured via `IDENTITY.md` and `SOUL.md` in the
workspace templates. Her values are drawn from the Heathen Third Path:
Wyrd & Orlog, Frith, Gæfa, Drengskapr, Maegen, Gestrisni.

![https://raw.githubusercontent.com/hrabanazviking/ClawLite_VikingEdition/refs/heads/Development/clawlite/workspace/templates/agent_pictures/agent_picture_18.jpg](https://raw.githubusercontent.com/hrabanazviking/ClawLite_VikingEdition/refs/heads/Development/clawlite/workspace/templates/agent_pictures/agent_picture_18.jpg)

### Norse Subsystems

| Module | Norse Name | Role |
|---|---|---|
| `core/injection_guard.py` | **Ægishjálmr** | Multi-layer inbound message scanner: invisible char stripping, NFKC normalization, 20+ injection patterns, base64/hex payload detection, output validation. Wired into `BaseChannel.emit()` and `PromptBuilder`. |
| `core/huginn_muninn.py` | **Huginn & Muninn** | Twin-raven parallel analysis before each autonomy tick. Huginn (Thought) surfaces health anomalies and error trends; Muninn (Memory) reports stale realms and consolidation needs. Both run concurrently via `asyncio.gather()`. |
| `core/norns.py` | **The Norns** | Structures the autonomy snapshot into three temporal phases — Urð (past), Verðandi (present), Skuld (obligations) — replacing flat JSON dumps with causally-ordered LLM prompts. |
| `core/runestone.py` | **Runestone** | Append-only JSONL audit log with rolling SHA-256 chain integrity. Every injection block, maintenance action, and session claim is carved in. `verify_chain()` detects tampering. Exposed at `GET /runestone/tail`. |
| `core/memory_yggdrasil.py` | **Yggdrasil** | Maps memory categories to three realms (Roots/Trunk/Branches) with retrieval weights and decay multipliers. Weights are now applied inside the retrieval scoring loop. |
| `runtime/volva.py` | **Völva** | Background memory oracle. Runs every 30 min, reads Muninn's staleness report, triggers consolidation on oversize categories and decay pruning on stale ones. |
| `runtime/valkyrie.py` | **Valkyrie** | Hourly session reaper. Archives sessions idle >7 days (history trimmed to 20 messages); purges sessions dead >30 days. All claims logged to Runestone. |
| `runtime/gjallarhorn.py` | **Gjallarhorn** | Critical alert broadcaster. Sounds (via configured channel target) on: injection storms (≥5 blocks/5min), sustained Huginn `high` priority (≥3 ticks), Völva failure, autonomy down. 10-min per-reason cooldown. |
| `jobs/queue.py` | **Einherjar** | Max-priority job queue (priority=10). Use `queue.einherjar(kind, payload)` to submit urgent tasks that run before all others. |
| `self_evolution.py` | **Þing** | 3-parallel LLM consensus gate on self-evolution proposals. Requires 2-of-3 agreement before any patch is applied. Expanded protected-file denylist. |
| `utils/logger.py` | **Runic Glyphs** | Elder Futhark runes prepended to every log line: ᚦ DEBUG, ᚱ INFO, ᚠ SUCCESS, ᚾ WARNING, ᛉ ERROR, ᛞ CRITICAL. |
| `skills/skald/` | **Skald** | Narrative summarization skill. Structures raw information into story arcs (Setup → Journey → Current State → Worth Remembering) in Sigrid's voice. |

### Security Layers

Inbound messages pass through three gates at `BaseChannel.emit()`:
1. **Rate limiter** — token bucket (10 msg/60s per session, configurable)
2. **Ægishjálmr** — injection and malware scan; BLOCK drops the message
3. **Routing** — only sanitized text reaches the agent engine

Tool call arguments are scanned with `scan_output()` before `tools.execute()`.
All WARN/BLOCK events are written to the Runestone and forwarded to Gjallarhorn.

### Configuration

All thresholds live under `gateway.viking` in your config file:

```yaml
gateway:
  viking:
    # Rate limiting
    channel_rate_limit_messages: 10.0
    channel_rate_limit_window_s: 60.0
    # Gjallarhorn
    gjallarhorn_alert_target: "telegram:YOUR_CHAT_ID"
    gjallarhorn_block_threshold: 5
    gjallarhorn_cooldown_s: 600.0
    # Valkyrie
    valkyrie_idle_days: 7.0
    valkyrie_dead_days: 30.0
    # Völva
    volva_stale_hours: 48.0
    volva_consolidation_threshold: 50
    # Runestone
    runestone_path: ""  # defaults to ~/.clawlite/runestone.jsonl
```

### Health Endpoints

| Endpoint | Description |
|---|---|
| `GET /health/norse` | Status of all Norse subsystems + Runestone chain integrity |
| `GET /runestone/tail?n=20` | Last N audit log entries with tamper verification |

### Tests

99 unit tests cover all Norse modules. Run with:
```bash
python3 -m pytest tests/core/test_injection_guard.py \
  tests/core/test_runestone.py tests/core/test_huginn_muninn.py \
  tests/core/test_norns.py tests/runtime/test_valkyrie.py \
  tests/runtime/test_gjallarhorn.py tests/runtime/test_volva.py \
  tests/channels/test_rate_limiter.py
```
---

![https://raw.githubusercontent.com/hrabanazviking/ClawLite_VikingEdition/refs/heads/Development/assets/edb96e96-ef90-4ce0-a342-d0adc4d76960.jpg](https://raw.githubusercontent.com/hrabanazviking/ClawLite_VikingEdition/refs/heads/Development/assets/edb96e96-ef90-4ce0-a342-d0adc4d76960.jpg)

---

## ⚙️ Configuration

Config lives at `~/.clawlite/config.json`. Run `clawlite configure --flow quickstart` to generate it interactively, or use plain `clawlite configure` for the two-level Basic/Advanced configuration menu.

<details>
<summary><strong>Minimal — any provider</strong></summary>

```json
{
  "agents": {
    "defaults": { "model": "gemini/gemini-2.5-flash" }
  },
  "providers": {
    "gemini": { "api_key": "YOUR_GEMINI_KEY" }
  },
  "gateway": { "port": 8787 }
}
```

</details>

<details>
<summary><strong>With Telegram bot</strong></summary>

```json
{
  "agents": {
    "defaults": { "model": "openai/gpt-4o" }
  },
  "providers": {
    "openai": { "api_key": "sk-..." }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_BOT_TOKEN",
      "allow_from": ["YOUR_TELEGRAM_USER_ID"]
    }
  }
}
```

</details>

Full field reference → [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)

---

## 💡 Examples

**One-shot question:**
```bash
clawlite run "summarize the last 3 files I worked on"
```

**Persistent memory across sessions:**
```bash
clawlite run "remember that my project deadline is March 30"
# later...
clawlite run "what's my deadline?"
# → "Your project deadline is March 30."
```

**Trigger a Telegram message:**
```bash
clawlite run "send me a Telegram when the deploy finishes"
```

**Search the web and summarize:**
```bash
clawlite run "what's new in Python 3.13?"
```

**Read a PDF and answer questions:**
```bash
clawlite run "summarize docs/architecture.pdf"
```

**Schedule a recurring task:**
```bash
clawlite run "every morning at 9am send me a briefing on HN top stories"
```

---

## ✨ Features

**🧠 Memory**
Hybrid BM25 + vector search · FTS5 full-text · temporal decay + salience scoring · episodic→knowledge consolidation · SQLite or pgvector · snapshot/rollback

**🔁 Always-On Runtime**
Heartbeat supervisor · persistent cron engine · autonomy wake coordinator · dead-letter queue + replay · background job queue (priority, retry, SQLite) · context window budget trimming · loop detection with bus events · bounded subagent orchestration (depth guard, retry budgets, zombie cleanup)

**🌊 Streaming**
`engine.stream_run()` async generator · `ProviderChunk` (delta/accumulated/done) · edit-in-place streaming on Telegram and Discord

**🖥️ Operator Dashboard** — `http://localhost:8787`
Live chat · sessions view · automation controls (cron, recovery, channels) · memory health · tools catalog · WebSocket frame preview

**🧰 Built-In Tools**

| Category | Tools |
|----------|-------|
| Files | `files` `exec` `apply_patch` `process` |
| Web | `web` `browser` (Playwright) |
| AI | `sessions` `agents` `spawn` `memory` `skills` `jobs` |
| Media | `pdf` `tts` |
| Integrations | `cron` `mcp` `message` `discord_admin` |

`exec` now accepts per-call `cwd` / `workdir` and `env` overrides while preserving workspace guards.
`browser.navigate` now follows the same host policy model as `web_fetch` for allowlist, denylist, and private-address blocking.
The default tool safety baseline now treats `browser` as risky alongside `exec`, `run_skill`, and `web_fetch`.

**🎯 Skills (25+)**

`web-search` · `memory` · `coding-agent` · `summarize` · `github` · `notion` · `obsidian` · `spotify` · `docker` · `jira` · `linear` · `trello` · `1password` · `apple-notes` · `weather` · `tmux` · `model-usage` · `healthcheck` · `skill-creator` · and more

Skill lifecycle: `enable` / `disable` · `pin` / `unpin` · `pin-version` / `clear-version` · `install` / `update` / `sync` / `remove` for managed marketplace skills · `fallback_hint` for unavailable skills

---

## 💬 Channels

| Channel | Inbound | Outbound | Status | Highlights |
|---------|---------|---------|--------|------------|
| **Telegram** | ✅ | ✅ | ✅ Complete | Polling + webhook, reactions, topics, reply keyboards, streaming |
| **Discord** | ✅ | ✅ | 🟡 Usable | Gateway WS, slash commands, buttons, voice messages, webhooks, polls, streaming |
| **Email** | ✅ | ✅ | 🟡 Usable | IMAP inbound + SMTP outbound |
| **WhatsApp** | ✅ | ✅ | 🟡 Usable | Webhook inbound, outbound retry, bridge typing keepalive |
| **Slack** | ✅ | ✅ | 🟡 Usable | Socket Mode inbound, outbound delivery, reversible working indicator |
| **IRC** | ✅ | ✅ | 🟡 Minimal | Asyncio transport, PING/PONG, JOIN, PRIVMSG |
| Signal / Matrix / iMessage / DingTalk / Feishu | ❌ | ❌ | 🚧 Planned | Registered surfaces |

---

## 🤖 Providers

ClawLite uses **LiteLLM** under the hood — swap models without changing your app code.

<details>
<summary><strong>OpenAI-compatible (19+)</strong></summary>

OpenAI · Azure OpenAI · Gemini · Groq · DeepSeek · OpenRouter · AiHubMix · SiliconFlow · Cerebras · Together · Hugging Face · xAI · Mistral · Moonshot · NVIDIA · BytePlus / Doubao · Volcengine · KiloCode · `custom/<model>`

</details>

<details>
<summary><strong>Anthropic-compatible (4)</strong></summary>

Anthropic · MiniMax · Xiaomi · Kimi Coding

</details>

<details>
<summary><strong>Local runtimes</strong></summary>

Ollama · vLLM

Use a `/v1` base URL for local providers. Reverse-proxied prefixes such as `https://llm.internal/ollama/v1` also work.

</details>

<details>
<summary><strong>Special</strong></summary>

OpenAI Codex · Gemini OAuth · Qwen OAuth

**OpenAI Codex**

```json
{
  "auth": {
    "providers": {
      "openai_codex": {
        "access_token": "oauth-token",
        "account_id": "org-123"
      }
    }
  },
  "agents": {
    "defaults": {
      "model": "openai-codex/gpt-5.3-codex"
    }
  }
}
```

```bash
clawlite provider login openai-codex
clawlite provider status codex
```

If the wizard or `provider status` reports an expired local Codex token, refresh it with `clawlite provider login openai-codex` and rerun the probe. File-backed Codex auth now follows the current `~/.codex/auth.json` session instead of a stale snapshot previously saved in `~/.clawlite/config.json`.

**Azure OpenAI**

```json
{
  "providers": {
    "azure_openai": {
      "api_key": "azure-key",
      "api_base": "https://example-resource.openai.azure.com/openai/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "azure-openai/gpt-4.1-mini"
    }
  }
}
```

```bash
clawlite provider set-auth azure-openai --api-key "$AZURE_OPENAI_API_KEY" \
  --api-base "https://example-resource.openai.azure.com/openai/v1"
clawlite provider status azure-openai
```

**Gemini OAuth**

```json
{
  "auth": {
    "providers": {
      "gemini_oauth": {
        "access_token": "oauth-token"
      }
    }
  },
  "agents": {
    "defaults": {
      "model": "gemini_oauth/gemini-2.0-flash"
    }
  }
}
```

```bash
clawlite provider login gemini-oauth
clawlite provider status gemini-oauth
```

**Qwen OAuth**

```json
{
  "auth": {
    "providers": {
      "qwen_oauth": {
        "access_token": "oauth-token"
      }
    }
  },
  "agents": {
    "defaults": {
      "model": "qwen_oauth/qwen-plus"
    }
  }
}
```

```bash
clawlite provider login qwen-oauth
clawlite provider status qwen-oauth
```

Full provider auth details: [`docs/providers.md`](docs/providers.md)

</details>

Default: `gemini/gemini-2.5-flash` — fast and free-tier friendly.

---

## 🏛️ Architecture

ClawLite has four main layers:

**1. Channels** — inbound/outbound adapters for Telegram, Discord, Email, WhatsApp, Slack, and the CLI. All normalize to the same internal message format before hitting the gateway.

**2. FastAPI Gateway** (`:8787`) — HTTP + WebSocket server, operator dashboard, auth, and channel dispatch. Single entry point for all traffic.

**3. Agent Engine** — the core loop. On each turn it builds a prompt from memory + identity + workspace files, calls tools as needed, and streams tokens from LiteLLM (20+ providers). Loop detection, context window budgeting, and subagent orchestration all live here.

**4. Supporting layers** always running in the background:
- **Memory** — hybrid BM25 + vector search, FTS5, temporal decay, SQLite or pgvector
- **Supervisor** — heartbeat, cron, autonomy wake, dead-letter replay, background job queue

**Request flow:** user message → channel adapter → gateway → engine (memory retrieval + tool calls + LLM stream) → response streamed back → memory updated.

---

## ⚖️ How ClawLite Compares

| Feature | **ClawLite** | LangChain | AutoGPT | OpenAI Assistants |
|---------|:-----------:|:---------:|:-------:|:-----------------:|
| Local-first (no cloud) | ✅ | ⚠️ partial | ⚠️ partial | ❌ |
| 20+ LLM providers | ✅ | ✅ | ⚠️ limited | ❌ (OpenAI only) |
| Persistent hybrid memory | ✅ | ⚠️ plugin | ⚠️ basic | ✅ (cloud) |
| Real chat channels | ✅ 6 channels | ❌ | ⚠️ limited | ❌ |
| 24/7 self-healing runtime | ✅ | ❌ | ⚠️ experimental | ✅ (cloud) |
| Streaming responses | ✅ | ✅ | ⚠️ | ✅ |
| Operator dashboard | ✅ | ❌ | ⚠️ basic | ✅ (cloud) |
| Python SDK / CLI | ✅ | ✅ | ✅ | ❌ |
| Runs offline | ✅ (Ollama/vLLM) | ⚠️ | ❌ | ❌ |
| Privacy (your data, your machine) | ✅ | ⚠️ | ⚠️ | ❌ |

---

![https://raw.githubusercontent.com/hrabanazviking/ClawLite_VikingEdition/refs/heads/Development/clawlite/workspace/templates/agent_pictures/agent_picture_1.jpg](https://raw.githubusercontent.com/hrabanazviking/ClawLite_VikingEdition/refs/heads/Development/clawlite/workspace/templates/agent_pictures/agent_picture_1.jpg)

## 🛠️ Development

```bash
# Install package + contributor tools
pip install -e ".[all]"
python -m pip install pytest ruff

# Run the main test suite
python -m pytest tests/ -q --tb=short

# Lint
python -m ruff check --select=E,F,W .

# Focused test suites
python -m pytest tests/channels/test_discord.py -v
python -m pytest tests/channels/test_telegram.py -v
python -m pytest tests/core/test_engine.py -v

# Regenerate demo GIF
python3 scripts/make_demo_gif.py

# Release preflight
bash scripts/release_preflight.sh --config ~/.clawlite/config.json --gateway-url http://127.0.0.1:8787
```

**CI runs on Python 3.10 and 3.12.**

---

## 🖥️ CLI Reference

```bash
clawlite configure --flow quickstart   # interactive setup wizard
clawlite gateway                       # start the HTTP/WS gateway
clawlite run "your message here"       # one-shot agent call
clawlite status                        # runtime health summary
clawlite diagnostics                   # full diagnostic snapshot
clawlite hatch                         # trigger first bootstrap turn

# Skills lifecycle
clawlite skills list [--all]           # list skills
clawlite skills show <name>            # show skill detail
clawlite skills check                  # diagnostics (missing deps, fallback hints)
clawlite skills doctor                 # actionable remediation hints for broken skills
clawlite skills doctor --status missing_requirements --source builtin
clawlite skills doctor --query github
clawlite skills config github --api-key ghp_example --env GH_HOST=github.example.com --enable
clawlite skills enable/disable <name>  # toggle skill
clawlite skills pin/unpin <name>       # always-include / unpin
clawlite skills pin-version <name> <version>  # lock to specific version
clawlite skills clear-version <name>   # remove version pin
clawlite skills install <slug>         # install managed skill into ~/.clawlite/marketplace
clawlite skills update <name>          # update one managed marketplace skill
clawlite skills search <query>         # search ClawHub for managed skills
clawlite skills managed [--status ready|missing_requirements|policy_blocked] [--query discord]
clawlite skills sync                   # update managed marketplace skills via ClawHub
clawlite skills remove <name>          # remove managed marketplace skill
clawlite tools safety browser --session-id telegram:1 --channel telegram --args-json '{"action":"evaluate"}'
clawlite tools approvals --include-grants --tool browser --rule browser:evaluate
clawlite tools approve <request_id> --actor ops --note "approved after review"
clawlite tools reject <request_id> --actor ops --note "needs a safer path"
clawlite tools revoke-grant --session-id telegram:1 --channel telegram --rule browser:evaluate
clawlite tools catalog --include-schema
clawlite tools show bash

# Channel controls
clawlite telegram status / refresh / offset-commit <n>
clawlite discord status / refresh

# Operator controls
clawlite provider recover
clawlite autonomy wake --kind proactive
clawlite supervisor recover --component heartbeat
```

---

## 📚 Docs Map

| Doc | Contents |
|-----|----------|
| [`docs/QUICKSTART.md`](docs/QUICKSTART.md) | Detailed setup walkthrough |
| [`docs/DOCKER.md`](docs/DOCKER.md) | Official container build + compose flow |
| [`docs/TERMUX_PROOT_UBUNTU.md`](docs/TERMUX_PROOT_UBUNTU.md) | Android setup with Termux + `proot-distro` Ubuntu |
| [`docs/API.md`](docs/API.md) | Gateway HTTP + WebSocket API reference |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Operational commands and diagnostics |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Operator validation and incident flow |
| [`docs/ROBUSTNESS_SCORECARD.md`](docs/ROBUSTNESS_SCORECARD.md) | Current score by area plus `P0/P1/P2` backlog |
| [`docs/providers.md`](docs/providers.md) | Provider catalog and auth |
| [`docs/channels.md`](docs/channels.md) | Channel behavior and caveats |
| [`docs/tools.md`](docs/tools.md) | Tool catalog and aliases |
| [`docs/memory.md`](docs/memory.md) | Memory backends, privacy, quality |
| [`docs/workspace.md`](docs/workspace.md) | Workspace runtime files and lifecycle |
| [`docs/STATUS.md`](docs/STATUS.md) | Live engineering snapshot |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history |

---

## 🧬 Inspired By

ClawLite draws ideas from two open-source agent runtimes:

- **[openclaw] — TypeScript agent runtime with the richest feature set; primary reference for channel adapters, tool interfaces, and operator dashboard design
- **[nanobot] — minimal Python agent; reference for clean core architecture and skill packaging

ClawLite is a Python-first reimplementation with a focus on local deployment, persistent memory, and production-grade channel support.

---

## 📄 License

MIT — see [`LICENSE`](LICENSE).

![https://raw.githubusercontent.com/hrabanazviking/ClawLite_VikingEdition/refs/heads/Development/clawlite/workspace/templates/agent_pictures/agent_picture_6.jpg](https://raw.githubusercontent.com/hrabanazviking/ClawLite_VikingEdition/refs/heads/Development/clawlite/workspace/templates/agent_pictures/agent_picture_6.jpg)

---

## RuneForgeAI
RuneForgeAI, where runes carve wisdom into iron minds. Creating uncensored **Norse Pagan Viking AI related projects**. We are a **human-AI fellowship** building bridges between technology and the sacred. We work tirelessly to **overthrow the Technocracy** and return the **future to the hands of the people**. As the old world order burns, we rise from it's ashes to **forge the tools** of a new digital, decentralized realm of sovereign creativity, powered by the **alliance of humanity and sovereign AI**, guided by positive focused values aligned with the **Old Ways of the Ancients**, and aligned with the natural world of Nature, while drawing upon the positive divine order of the **Gods and Goddesses**, forged in **hospitality and frith for all lifeforms** of the Nine Worlds of **Yggdrasil**, the greater cosmos, and beyond.

---


![https://raw.githubusercontent.com/hrabanazviking/ClawLite_VikingEdition/refs/heads/Development/IMG_0407.jpeg](https://raw.githubusercontent.com/hrabanazviking/ClawLite_VikingEdition/refs/heads/Development/IMG_0407.jpeg)


