# Configuration

Arquivo padrão: `~/.clawlite/config.json`

Campos principais (resumo):
- `workspace_path`, `state_path`
- `provider` e `providers` (modelo ativo, credenciais/base por provedor)
- `agents.defaults` (modelo, limites, temperature)
- `gateway.host`, `gateway.port`
- `gateway.auth` (controle de auth da API)
- `gateway.diagnostics` (exposição e proteção de `/v1/diagnostics`)
- `gateway.heartbeat` (liga/desliga e intervalo do heartbeat do gateway)
- `scheduler.timezone` (timezone para cron)
- `channels` (telegram/discord/slack/whatsapp + extras)

## Variáveis de ambiente

- `CLAWLITE_MODEL`
- `CLAWLITE_WORKSPACE`
- `CLAWLITE_LITELLM_BASE_URL`
- `CLAWLITE_LITELLM_API_KEY`
- `CLAWLITE_GATEWAY_HOST`
- `CLAWLITE_GATEWAY_PORT`
- `CLAWLITE_GATEWAY_AUTH_MODE` (`off|optional|required`)
- `CLAWLITE_GATEWAY_AUTH_TOKEN`
- `CLAWLITE_GATEWAY_AUTH_ALLOW_LOOPBACK` (`true/false`)
- `CLAWLITE_GATEWAY_DIAGNOSTICS_ENABLED` (`true/false`)
- `CLAWLITE_GATEWAY_DIAGNOSTICS_REQUIRE_AUTH` (`true/false`)

Obs.: variáveis de chave por provedor (`OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY` etc.) continuam válidas para resolução de credenciais do provider.

## Gateway atual (schema)

`gateway` não usa mais `gateway.token` como campo principal. O formato atual é:

```json
{
  "gateway": {
    "host": "127.0.0.1",
    "port": 8787,
    "auth": {
      "mode": "off",
      "token": "",
      "allow_loopback_without_auth": true,
      "header_name": "Authorization",
      "query_param": "token",
      "protect_health": false
    },
    "diagnostics": {
      "enabled": true,
      "require_auth": true,
      "include_config": false
    },
    "heartbeat": {
      "enabled": true,
      "interval_s": 1800
    }
  }
}
```

Compatibilidade: se existir `gateway.token` legado, o loader migra para `gateway.auth.token` e define `gateway.auth.mode=required` quando necessário.

## Heartbeat (nota de compatibilidade)

- Preferência atual: `gateway.heartbeat.interval_s`.
- Campo legado: `scheduler.heartbeat_interval_seconds`.
- Se `gateway.heartbeat.interval_s` não vier definido explicitamente, o loader usa o valor legado do `scheduler`.

## Resolução automática do provedor

- `provider.model` define o provedor preferencial (`gemini/...`, `openrouter/...`, `openai/...`, `groq/...`).
- Se a chave não estiver em `provider.litellm_api_key`, o runtime tenta variáveis de ambiente específicas por provedor.
- `provider.litellm_base_url` é opcional para provedores comuns: o runtime aplica base URL padrão por provedor.

## Telegram (opções principais)

Em `channels.telegram`, além de `enabled` e `token`, os campos operacionais mais usados são:
- `mode` (`polling` é o caminho de runtime ativo hoje; campos de webhook são mantidos por compatibilidade/integração futura)
- `webhook_enabled`, `webhook_secret`, `webhook_path`
- `poll_interval_s`, `poll_timeout_s`
- `reconnect_initial_s`, `reconnect_max_s`
- `send_timeout_s`, `send_retry_attempts`
- `send_backoff_base_s`, `send_backoff_max_s`, `send_backoff_jitter`
- `send_circuit_failure_threshold`, `send_circuit_cooldown_s`

## Exemplo

Veja: [config.example.json](./config.example.json)
