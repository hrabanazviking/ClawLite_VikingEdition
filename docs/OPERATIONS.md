# Operations

## Start

```bash
clawlite start --host 127.0.0.1 --port 8787
```

Alias equivalente:

```bash
clawlite gateway --host 127.0.0.1 --port 8787
```

## Status e diagnósticos

```bash
clawlite status
clawlite diagnostics
clawlite diagnostics --gateway-url http://127.0.0.1:8787 --token "$CLAWLITE_GATEWAY_AUTH_TOKEN"
```

## Validações operacionais

```bash
clawlite validate provider
clawlite validate channels
clawlite validate onboarding
```

Para gerar templates faltantes do onboarding:

```bash
clawlite validate onboarding --fix
```

## Cron (CLI)

```bash
clawlite cron add --session-id cli:ops --expression "every 300" --prompt "status rapido" --name "ops-check"
clawlite cron list --session-id cli:ops
clawlite cron remove --job-id <job_id>
```

Comandos adicionais úteis:

```bash
clawlite cron enable <job_id>
clawlite cron disable <job_id>
clawlite cron run <job_id>
```

## Trigger manual de heartbeat via API

```bash
curl -sS -X POST http://127.0.0.1:8787/v1/control/heartbeat/trigger \
  -H "Authorization: Bearer $CLAWLITE_GATEWAY_AUTH_TOKEN"
```

## Smoke tests

```bash
bash scripts/smoke_test.sh
```

## Testes

```bash
pytest -q tests
```

## Incident checklist

1. Confirmar gateway: `curl -sS http://127.0.0.1:8787/health` e `clawlite diagnostics --gateway-url http://127.0.0.1:8787`.
2. Confirmar configuração mínima: `clawlite validate provider` e `clawlite validate channels`.
3. Se houver falha no heartbeat, validar `gateway.heartbeat.enabled` e disparar trigger manual (`/v1/control/heartbeat/trigger`).
4. Antes de hotfix/release: `bash scripts/smoke_test.sh` e `pytest -q tests`.
