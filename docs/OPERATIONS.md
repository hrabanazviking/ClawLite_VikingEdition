# Operations

## Start / stop

```bash
clawlite start --host 127.0.0.1 --port 8787
```

## Smoke test local

```bash
bash scripts/smoke_test.sh
```

## Testes

```bash
pytest -q tests
```

## Verificar saúde

```bash
curl -sS http://127.0.0.1:8787/health | python -m json.tool
```

## Verificar aliases de compatibilidade do gateway

```bash
curl -sS http://127.0.0.1:8787/
curl -sS http://127.0.0.1:8787/api/status | python -m json.tool
curl -sS -X POST http://127.0.0.1:8787/api/message \
  -H 'content-type: application/json' \
  -d '{"session_id":"cli:ops","text":"ping"}' | python -m json.tool
curl -sS http://127.0.0.1:8787/api/token | python -m json.tool
```

Notas:
- `/api/status` e `/api/message` espelham `/v1/status` e `/v1/chat`.
- `/api/token` retorna token mascarado (nunca o token bruto).
- `WS /ws` espelha `WS /v1/ws`.

## Cron manual

```bash
clawlite cron add --session-id cli:ops --expression "every 300" --prompt "status rapido"
clawlite cron list --session-id cli:ops
```

## Incident checklist

1. Confirmar `/health`.
2. Confirmar `clawlite run "ok"`.
3. Validar provider (`CLAWLITE_MODEL`, `CLAWLITE_LITELLM_API_KEY`).
4. Rodar `pytest -q tests` antes de qualquer release/hotfix.
