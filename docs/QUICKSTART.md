# Quickstart

## 1. Instalar

```bash
curl -fsSL https://raw.githubusercontent.com/eobarretooo/ClawLite/main/scripts/install.sh | bash
```

Ou localmente:

```bash
pip install -e .
```

## 2. Onboarding do workspace

```bash
clawlite onboard
```

O loader gera templates base no workspace (quando ausentes):
- `IDENTITY.md`
- `SOUL.md`
- `USER.md`
- `AGENTS.md`
- `TOOLS.md`
- `HEARTBEAT.md`
- `BOOTSTRAP.md`
- `memory/MEMORY.md`

## 3. Configurar provider

```bash
export CLAWLITE_MODEL="gemini/gemini-2.5-flash"
export CLAWLITE_LITELLM_API_KEY="<sua-chave>"
```

## 4. Subir gateway

```bash
clawlite start --host 127.0.0.1 --port 8787
```

Alias equivalente:

```bash
clawlite gateway --host 127.0.0.1 --port 8787
```

## 5. Testar `/v1/chat`

```bash
curl -sS http://127.0.0.1:8787/v1/chat \
  -H 'content-type: application/json' \
  -d '{"session_id":"cli:quickstart","text":"quem voce e?"}'
```

Se `gateway.auth.mode=required`, envie token via `Authorization: Bearer <token>` ou query `?token=<token>`.
