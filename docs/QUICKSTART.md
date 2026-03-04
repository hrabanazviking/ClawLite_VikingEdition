# Quickstart

## 1. Install

```bash
curl -fsSL https://raw.githubusercontent.com/eobarretooo/ClawLite/main/scripts/install.sh | bash
```

Or locally:

```bash
pip install -e .
```

## 2. Workspace onboarding

```bash
clawlite onboard
```

The loader generates base templates in the workspace (when missing):
- `IDENTITY.md`
- `SOUL.md`
- `USER.md`
- `AGENTS.md`
- `TOOLS.md`
- `HEARTBEAT.md`
- `BOOTSTRAP.md`
- `memory/MEMORY.md`

## 3. Configure provider

```bash
export CLAWLITE_MODEL="gemini/gemini-2.5-flash"
export CLAWLITE_LITELLM_API_KEY="<your-key>"
```

## 4. Start gateway

```bash
clawlite start --host 127.0.0.1 --port 8787
```

Equivalent alias:

```bash
clawlite gateway --host 127.0.0.1 --port 8787
```

## 5. Test `/v1/chat`

```bash
curl -sS http://127.0.0.1:8787/v1/chat \
  -H 'content-type: application/json' \
  -d '{"session_id":"cli:quickstart","text":"who are you?"}'
```

If `gateway.auth.mode=required`, send the token via `Authorization: Bearer <token>` or query `?token=<token>`.
