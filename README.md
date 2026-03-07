<div align="center">
  <img src="assets/clawlite-logo.png" alt="ClawLite Logo" width="200"/>

  # ClawLite

  **Autonomous AI agent for Linux and Android, no cloud required.**

  [Releases](https://github.com/eobarretooo/ClawLite/releases) · [Report Bug](https://github.com/eobarretooo/ClawLite/issues)
</div>

---

![Python](https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white) ![License](https://img.shields.io/github/license/eobarretooo/ClawLite) ![Version](https://img.shields.io/github/v/release/eobarretooo/ClawLite)

![Stars](https://img.shields.io/github/stars/eobarretooo/ClawLite?style=social) ![Forks](https://img.shields.io/github/forks/eobarretooo/ClawLite?style=social) ![Last Commit](https://img.shields.io/github/last-commit/eobarretooo/ClawLite)

---

ClawLite is an autonomous AI assistant written in Python, designed to run entirely locally on Linux and Android (Termux). It supports multiple LLM providers via LiteLLM, persistent memory, autonomous tool use, scheduled tasks (cron), and multi-channel integration — processing inputs from CLI, WebSockets, Telegram, Discord, and WhatsApp natively.

## ✨ Features

- ✅ **Real agent loop** — iterative Think → Act → Observe cycle without human intervention
- ✅ **Native system tools** — built-in `bash_runner` and `file_editor` for direct OS access
- ✅ **Multi-provider routing** — switch between Gemini, OpenAI, Anthropic, Groq, OpenRouter, and local Ollama
- ✅ **Persistent memory** — JSONL-based store with BM25 semantic retrieval and deduplication
- ✅ **Multi-channel endpoints** — process messages via Telegram, Discord, WhatsApp, REST, and WebSockets
- ✅ **Background operations** — built-in cron scheduler and heartbeat monitoring
- ✅ **Extensible skills** — add capabilities instantly via Markdown (`SKILL.md`) drops

## 🚀 Quick Start

```bash
git clone https://github.com/eobarretooo/ClawLite.git
cd ClawLite
pip install -e .
clawlite onboard --wizard
clawlite gateway
```

That's it. Your agent is running at `http://127.0.0.1:8787` and via CLI.

## 📦 Installation

**Requirements:** Python 3.10+

```bash
# Clone the repository
git clone https://github.com/eobarretooo/ClawLite.git
cd ClawLite

# Install in editable mode
pip install -e .
```

**Android (Termux via Ubuntu proot):**

For the best experience and full compatibility on Android, use a prooted Ubuntu environment:

```bash
# 1. In Termux, install and run Ubuntu:
pkg update && pkg upgrade -y
pkg install proot-distro -y
proot-distro install ubuntu
proot-distro login ubuntu

# 2. Inside Ubuntu, install dependencies:
apt update && apt upgrade -y
apt install python3 python3-pip python3-venv git -y

# 3. Clone and install:
git clone https://github.com/eobarretooo/ClawLite.git
cd ClawLite
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## ⚙️ Configuration

Config lives at `~/.clawlite/config.json`:

```json
{
  "provider": {
    "model": "gemini/gemini-2.5-flash"
  },
  "providers": {
    "gemini": {
      "api_key": "your-gemini-key"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "your-bot-token"
    }
  }
}
```

## 📖 Usage

**Start the gateway:**
```bash
clawlite gateway
# or with specific host/port
clawlite gateway --host 127.0.0.1 --port 8787
```

**Chat via CLI:**
```bash
clawlite run "hello agent, what is your status?"
```

**Switch active model and provider:**
```bash
clawlite provider use ollama --model openai/llama3.2
clawlite provider set-auth openai --api-key "sk-..."
```

**System diagnostics and validation:**
```bash
clawlite validate preflight --gateway-url http://127.0.0.1:8787
clawlite diagnostics --gateway-url http://127.0.0.1:8787
```

**Available Skills:**
```bash
clawlite skills list
clawlite skills check
```

## 🗂️ Project Structure

```text
clawlite/
├── core/         # Engine, prompt generation, memory, skills, subagents
├── tools/        # Tool registry and built-in capabilities
├── channels/     # Telegram, Discord, and WhatsApp adapters
├── gateway/      # FastAPI REST and WebSocket server
├── scheduler/    # Cron and heartbeat automation
├── providers/    # LiteLLM routing and model configurations
├── session/      # JSONL session persistence layer
└── workspace/    # Identity templates (IDENTITY.md, SOUL.md, USER.md)
```

## 🤝 Contributing

Pull requests are welcome. For major changes, open an issue first.

```bash
git clone https://github.com/eobarretooo/ClawLite.git
cd ClawLite
pip install -e ".[dev]"
pytest -q tests
```



## 🙏 Acknowledgements

ClawLite was built on the shoulders of giants. Special thanks to:

- [Nanobot](https://github.com/HKUDS/nanobot) — for the ultra-lightweight agent architecture inspiration
- [OpenClaw](https://github.com/openclaw/openclaw) — for the conceptual foundation and multi-channel approach
- [memU](https://github.com/NevaMind-AI/memU) — for the advanced persistent memory and retrieval concepts

## ⭐️ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=eobarretooo/ClawLite&type=Date)](https://star-history.com/#eobarretooo/ClawLite&Date)

## 📄 License

[MIT](LICENSE) © 2026 eobarretooo