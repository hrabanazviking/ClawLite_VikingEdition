from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.prompt import Prompt

from clawlite.config.loader import save_config
from clawlite.config.schema import AppConfig
from clawlite.providers.catalog import ONBOARDING_PROVIDER_ORDER, default_provider_model, provider_profile
from clawlite.providers.discovery import normalize_local_runtime_base_url, probe_local_provider_runtime
from clawlite.providers.hints import provider_probe_hints, provider_transport_name
from clawlite.providers.model_probe import evaluate_remote_model_check, model_check_hints
from clawlite.providers.registry import SPECS
from clawlite.workspace.loader import WorkspaceLoader


def _provider_name_variants(spec_name: str, aliases: tuple[str, ...]) -> set[str]:
    values = {str(spec_name or "").strip().lower().replace("-", "_")}
    values.update(str(alias or "").strip().lower().replace("-", "_") for alias in aliases)
    return values


def _provider_spec(name: str) -> Any:
    provider_name = str(name or "").strip().lower().replace("-", "_")
    return next(
        (
            row
            for row in SPECS
            if provider_name in _provider_name_variants(row.name, row.aliases)
            and row.name not in {"custom", "openai_codex"}
        ),
        None,
    )


SUPPORTED_PROVIDERS: tuple[str, ...] = tuple(
    provider_id for provider_id in ONBOARDING_PROVIDER_ORDER if _provider_spec(provider_id) is not None
)

DEFAULT_PROVIDER_BASE_URLS: dict[str, str] = {}
for provider_id in SUPPORTED_PROVIDERS:
    spec = _provider_spec(provider_id)
    if spec is None:
        continue
    default_base = str(spec.default_base_url or "").strip()
    if spec.name in {"ollama", "vllm"} and default_base:
        default_base = normalize_local_runtime_base_url(spec.name, default_base)
    DEFAULT_PROVIDER_BASE_URLS[spec.name] = default_base


def _probe_model_name(model: str, provider_key: str, aliases: tuple[str, ...]) -> str:
    normalized = str(model or "").strip()
    if "/" not in normalized:
        return normalized
    prefix, remainder = normalized.split("/", 1)
    if prefix.strip().lower().replace("-", "_") in _provider_name_variants(provider_key, aliases):
        return remainder
    return normalized


def _mask_secret(value: str, *, keep: int = 4) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    if len(token) <= keep:
        return "*" * len(token)
    return f"{'*' * max(3, len(token) - keep)}{token[-keep:]}"


def _provider_profile_payload(provider_name: str) -> dict[str, Any]:
    profile = provider_profile(provider_name)
    return {
        "family": profile.family,
        "recommended_model": default_provider_model(provider_name),
        "recommended_models": list(profile.recommended_models),
        "onboarding_hint": profile.onboarding_hint,
    }


def _join_base(base_url: str, path: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    suffix = str(path or "").strip()
    if not suffix.startswith("/"):
        suffix = f"/{suffix}"
    return f"{base}{suffix}"


def ensure_gateway_token(config: AppConfig) -> str:
    current = str(config.gateway.auth.token or "").strip()
    if current:
        return current
    generated = uuid.uuid4().hex
    config.gateway.auth.token = generated
    return generated


def apply_provider_selection(
    config: AppConfig,
    *,
    provider: str,
    api_key: str,
    base_url: str,
    model: str = "",
) -> dict[str, Any]:
    spec = _provider_spec(provider)
    provider_key = spec.name if spec is not None else str(provider or "").strip().lower().replace("-", "_")
    if spec is None or provider_key not in {item.replace("-", "_") for item in SUPPORTED_PROVIDERS}:
        raise ValueError(f"unsupported_provider:{provider_key}")

    selected_model = str(model or "").strip() or default_provider_model(provider_key)
    raw_base_url = str(base_url or "").strip() or DEFAULT_PROVIDER_BASE_URLS.get(provider_key, "")
    selected_base_url = (
        normalize_local_runtime_base_url(provider_key, raw_base_url)
        if provider_key in {"ollama", "vllm"} and raw_base_url
        else raw_base_url
    )
    selected_api_key = str(api_key or "").strip()

    config.provider.model = selected_model
    config.agents.defaults.model = selected_model
    config.provider.litellm_base_url = selected_base_url
    config.provider.litellm_api_key = selected_api_key

    selected_override = config.providers.ensure(provider_key)
    selected_override.api_key = selected_api_key
    selected_override.api_base = selected_base_url

    return {
        "provider": provider_key,
        "model": selected_model,
        "base_url": selected_base_url,
        "api_key_masked": _mask_secret(selected_api_key),
    }


def probe_provider(
    provider: str,
    *,
    api_key: str,
    base_url: str,
    model: str = "",
    timeout_s: float = 8.0,
) -> dict[str, Any]:
    spec = _provider_spec(provider)
    provider_key = spec.name if spec is not None else str(provider or "").strip().lower().replace("-", "_")
    selected_model = str(model or "").strip() or default_provider_model(provider_key)
    profile_payload = _provider_profile_payload(provider_key)
    if spec is None:
        return {
            "ok": False,
            "provider": provider_key,
            "error": f"unsupported_provider:{provider_key}",
            "api_key_masked": _mask_secret(api_key),
            "base_url": str(base_url or "").strip(),
            "transport": "native",
            "probe_method": "",
            "error_detail": "",
            "default_base_url": "",
            "key_envs": [],
            "model_check": {"checked": False, "ok": True, "enforced": False},
            **profile_payload,
            "hints": [],
        }

    key = str(api_key or "").strip()
    resolved_base = str(base_url or "").strip() or DEFAULT_PROVIDER_BASE_URLS.get(provider_key, "")
    if provider_key == "ollama" and resolved_base.endswith("/v1"):
        resolved_base = resolved_base[: -len("/v1")]

    headers: dict[str, str] = {}
    payload: dict[str, Any] | None = None
    probe_method = "GET"
    transport = provider_transport_name(provider=provider_key, spec=spec, auth_mode="none" if provider_key in {"ollama", "vllm"} else "api_key")
    default_base_url = str(spec.default_base_url or "")
    key_envs = list(spec.key_envs)
    model_check: dict[str, Any] = {"checked": False, "ok": True, "enforced": False}

    if provider_key == "ollama":
        url = _join_base(resolved_base, "/api/tags")
    elif provider_key == "vllm":
        url = _join_base(resolved_base, "/models")
        if key:
            headers["Authorization"] = f"Bearer {key}"
    elif provider_key == "anthropic":
        url = _join_base(resolved_base, "/models")
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    elif spec.native_transport == "anthropic":
        resolved_model = _probe_model_name(
            selected_model,
            provider_key,
            spec.aliases,
        )
        url = _join_base(resolved_base, "/messages")
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        payload = {
            "model": resolved_model,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "ping"}],
        }
        probe_method = "POST"
    elif spec.openai_compatible:
        url = _join_base(resolved_base, "/models")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
    else:
        return {
            "ok": False,
            "provider": provider_key,
            "error": f"unsupported_provider:{provider_key}",
            "api_key_masked": _mask_secret(key),
            "base_url": resolved_base,
            "transport": transport,
            "probe_method": probe_method,
            "error_detail": "",
            "default_base_url": default_base_url,
            "key_envs": key_envs,
            "model_check": model_check,
            **profile_payload,
            "hints": provider_probe_hints(
                provider=provider_key,
                error=f"unsupported_provider:{provider_key}",
                error_detail="",
                status_code=0,
                auth_mode="api_key",
                transport=transport,
                endpoint="",
                default_base_url=default_base_url,
                key_envs=key_envs,
                model=selected_model,
            ),
        }

    if provider_key not in {"ollama", "vllm"} and not key:
        error = "api_key_missing"
        return {
            "ok": False,
                "provider": provider_key,
                "status_code": 0,
                "url": url,
                "base_url": resolved_base,
            "api_key_masked": "",
            "error": error,
            "body": "",
            "transport": transport,
            "probe_method": probe_method,
            "error_detail": "",
            "default_base_url": default_base_url,
            "key_envs": key_envs,
            "model_check": model_check,
            **profile_payload,
            "hints": provider_probe_hints(
                provider=provider_key,
                error=error,
                error_detail="",
                status_code=0,
                auth_mode="api_key",
                transport=transport,
                endpoint=url,
                default_base_url=default_base_url,
                key_envs=key_envs,
                model=selected_model,
            ),
        }

    try:
        with httpx.Client(timeout=max(0.5, float(timeout_s))) as client:
            if payload is None:
                response = client.get(url, headers=headers)
            else:
                response = client.post(url, headers=headers, json=payload)
        body: Any
        try:
            body = response.json()
        except Exception:
            body = response.text
        error = "" if response.is_success else f"http_status:{response.status_code}"
        error_detail = ""
        if not response.is_success:
            if isinstance(body, dict):
                error_obj = body.get("error")
                if isinstance(error_obj, dict):
                    error_detail = str(error_obj.get("message", "") or error_obj.get("detail", "") or "").strip()
                elif isinstance(error_obj, str):
                    error_detail = error_obj.strip()
                if not error_detail:
                    error_detail = str(body.get("message", "") or body.get("detail", "") or "").strip()
            elif isinstance(body, str):
                error_detail = body.strip()
        elif provider_key in {"ollama", "vllm"}:
            model_check = probe_local_provider_runtime(
                model=selected_model,
                base_url=resolved_base,
                timeout_s=max(0.5, float(timeout_s)),
            )
        elif payload is None:
            model_check = evaluate_remote_model_check(
                provider=provider_key,
                model=selected_model,
                aliases=spec.aliases,
                payload=body,
                is_gateway=bool(spec.is_gateway),
            )
        hints = provider_probe_hints(
            provider=provider_key,
            error=error,
            error_detail=error_detail,
            status_code=int(response.status_code),
            auth_mode="none" if provider_key in {"ollama", "vllm"} else "api_key",
            transport=transport,
            endpoint=url,
            default_base_url=default_base_url,
            key_envs=key_envs,
            model=selected_model,
        )
        for hint in model_check_hints(model_check, model=selected_model):
            if hint not in hints:
                hints.append(hint)
        ok = bool(response.is_success)
        if provider_key in {"ollama", "vllm"}:
            ok = ok and bool(model_check.get("ok", True))
        return {
            "ok": ok,
            "provider": provider_key,
            "status_code": int(response.status_code),
            "url": url,
            "base_url": resolved_base,
            "api_key_masked": _mask_secret(key),
            "error": error,
            "body": body if response.is_success else "",
            "transport": transport,
            "probe_method": probe_method,
            "error_detail": error_detail,
            "default_base_url": default_base_url,
            "key_envs": key_envs,
            "model_check": model_check,
            **profile_payload,
            "hints": hints,
        }
    except Exception as exc:
        error = str(exc)
        hints = provider_probe_hints(
            provider=provider_key,
            error=error,
            error_detail="",
            status_code=0,
            auth_mode="none" if provider_key in {"ollama", "vllm"} else "api_key",
            transport=transport,
            endpoint=url,
            default_base_url=default_base_url,
            key_envs=key_envs,
            model=selected_model,
        )
        return {
            "ok": False,
            "provider": provider_key,
            "status_code": 0,
            "url": url,
            "base_url": resolved_base,
            "api_key_masked": _mask_secret(key),
            "error": error,
            "body": "",
            "transport": transport,
            "probe_method": probe_method,
            "error_detail": "",
            "default_base_url": default_base_url,
            "key_envs": key_envs,
            "model_check": model_check,
            **profile_payload,
            "hints": hints,
        }


def probe_telegram(token: str, *, timeout_s: float = 8.0) -> dict[str, Any]:
    clean = str(token or "").strip()
    url = f"https://api.telegram.org/bot{clean}/getMe" if clean else ""
    if not clean:
        return {
            "ok": False,
            "status_code": 0,
            "url": "",
            "token_masked": "",
            "error": "telegram_token_missing",
            "body": "",
        }
    try:
        with httpx.Client(timeout=max(0.5, float(timeout_s))) as client:
            response = client.get(url)
        body: Any
        try:
            body = response.json()
        except Exception:
            body = response.text
        ok = bool(response.is_success) and bool(isinstance(body, dict) and body.get("ok", False))
        return {
            "ok": ok,
            "status_code": int(response.status_code),
            "url": url,
            "token_masked": _mask_secret(clean),
            "error": "" if ok else "telegram_probe_failed",
            "body": body if ok else "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": 0,
            "url": url,
            "token_masked": _mask_secret(clean),
            "error": str(exc),
            "body": "",
        }


def run_onboarding_wizard(
    config: AppConfig,
    *,
    config_path: str | Path | None,
    overwrite: bool = False,
    variables: dict[str, str] | None = None,
) -> dict[str, Any]:
    console = Console(stderr=True, soft_wrap=True)
    payload: dict[str, Any] = {
        "ok": False,
        "mode": "wizard",
        "steps": [],
    }

    try:
        console.print(Panel("ClawLite Onboarding Wizard", title="clawlite onboard --wizard"))

        step_1_mode = Prompt.ask("Step 1/5 - mode", choices=["quickstart", "advanced"], default="quickstart")
        payload["steps"].append({"step": 1, "name": "mode", "choice": step_1_mode})

        if step_1_mode == "advanced":
            host = Prompt.ask("Gateway host", default=str(config.gateway.host or "127.0.0.1").strip())
            port_raw = Prompt.ask("Gateway port", default=str(int(config.gateway.port or 8787)))
            auth_mode = Prompt.ask(
                "Gateway auth mode",
                choices=["off", "optional", "required"],
                default=str(config.gateway.auth.mode or "off").strip().lower() or "off",
            )
            try:
                port = int(port_raw)
            except Exception:
                port = 8787
            config.gateway.host = host.strip() or "127.0.0.1"
            config.gateway.port = max(1, port)
            config.gateway.auth.mode = auth_mode
        else:
            config.gateway.host = str(config.gateway.host or "127.0.0.1").strip() or "127.0.0.1"
            config.gateway.port = max(1, int(config.gateway.port or 8787))
            if str(config.gateway.auth.mode or "").strip().lower() not in {"off", "optional", "required"}:
                config.gateway.auth.mode = "off"

        provider = Prompt.ask("Step 2/5 - provider", choices=list(SUPPORTED_PROVIDERS), default="openai")
        provider_spec = _provider_spec(provider)
        provider_key = provider_spec.name if provider_spec is not None else provider
        provider_default_base = DEFAULT_PROVIDER_BASE_URLS.get(provider_key, "")
        current_base = str(config.provider.litellm_base_url or "").strip()
        base_default = current_base or provider_default_base
        base_url = base_default
        selected_model = ""
        if step_1_mode == "advanced":
            base_url = Prompt.ask(f"{provider} base URL", default=base_default)
            current_model = str(config.provider.model or "").strip()
            model_default = current_model or default_provider_model(provider_key)
            selected_model = Prompt.ask(f"{provider} model", default=model_default)
        api_key = ""
        if provider_key not in {"ollama", "vllm"}:
            api_key = Prompt.ask(f"{provider} API key", password=True)
        provider_probe = probe_provider(provider, api_key=api_key, base_url=base_url, model=selected_model)
        persisted_model = str(selected_model or "").strip() or default_provider_model(provider_key)
        payload["steps"].append(
            {
                "step": 2,
                "name": "provider",
                "provider": provider,
                "model": persisted_model,
                "family": str(provider_probe.get("family", "") or ""),
                "recommended_model": str(provider_probe.get("recommended_model", "") or ""),
                "recommended_models": list(provider_probe.get("recommended_models", []) or []),
                "onboarding_hint": str(provider_probe.get("onboarding_hint", "") or ""),
                "probe_ok": bool(provider_probe.get("ok", False)),
                "base_url": str(provider_probe.get("base_url", "") or ""),
                "api_key_masked": str(provider_probe.get("api_key_masked", "") or ""),
                "probe_error": str(provider_probe.get("error", "") or ""),
                "probe_hints": list(provider_probe.get("hints", []) or []),
                "transport": str(provider_probe.get("transport", "") or ""),
            }
        )
        if (not bool(provider_probe.get("ok", False))) and (not Confirm.ask("Provider probe failed. Continue?", default=False)):
            return {
                "ok": False,
                "mode": "wizard",
                "error": "provider_probe_failed",
                "steps": payload["steps"],
            }

        provider_persisted = apply_provider_selection(
            config,
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            model=selected_model,
        )

        telegram_enabled = Confirm.ask("Step 3/5 - enable Telegram channel?", default=False)
        telegram_probe: dict[str, Any] = {
            "ok": True,
            "status_code": 0,
            "token_masked": "",
            "error": "",
        }
        if telegram_enabled:
            telegram_token = Prompt.ask("Telegram bot token", password=True)
            telegram_probe = probe_telegram(telegram_token)
            if (not bool(telegram_probe.get("ok", False))) and (not Confirm.ask("Telegram probe failed. Continue?", default=False)):
                return {
                    "ok": False,
                    "mode": "wizard",
                    "error": "telegram_probe_failed",
                    "steps": payload["steps"],
                }
            config.channels.telegram.enabled = True
            config.channels.telegram.token = str(telegram_token or "").strip()
        else:
            config.channels.telegram.enabled = False
        payload["steps"].append(
            {
                "step": 3,
                "name": "telegram",
                "enabled": telegram_enabled,
                "probe_ok": bool(telegram_probe.get("ok", False)),
                "token_masked": str(telegram_probe.get("token_masked", "") or ""),
                "probe_error": str(telegram_probe.get("error", "") or ""),
            }
        )

        generated_token = ensure_gateway_token(config)

        loader = WorkspaceLoader(workspace_path=config.workspace_path)
        generated_files = loader.bootstrap(overwrite=bool(overwrite), variables=variables or {})
        payload["steps"].append(
            {
                "step": 4,
                "name": "workspace",
                "workspace": str(config.workspace_path),
                "created_files": [str(path) for path in generated_files],
            }
        )

        saved_path = save_config(config, path=config_path)
        gateway_url = f"http://{config.gateway.host}:{config.gateway.port}"
        payload["steps"].append({"step": 5, "name": "final", "gateway_url": gateway_url})

        console.print(
            Panel(
                f"Gateway URL: {gateway_url}\nGateway token: {generated_token}",
                title="Onboarding complete",
            )
        )

        return {
            "ok": True,
            "mode": "wizard",
            "saved_path": str(saved_path),
            "persisted": {
                "provider": provider_persisted,
                "gateway": {
                    "host": str(config.gateway.host),
                    "port": int(config.gateway.port),
                    "auth_mode": str(config.gateway.auth.mode),
                    "token_masked": _mask_secret(generated_token),
                },
                "telegram": {
                    "enabled": bool(config.channels.telegram.enabled),
                    "token_masked": _mask_secret(config.channels.telegram.token),
                },
            },
            "workspace": {
                "path": str(config.workspace_path),
                "created_files": [str(path) for path in generated_files],
            },
            "probes": {
                "provider": {
                    "ok": bool(provider_probe.get("ok", False)),
                    "status_code": int(provider_probe.get("status_code", 0) or 0),
                    "error": str(provider_probe.get("error", "") or ""),
                    "api_key_masked": str(provider_probe.get("api_key_masked", "") or ""),
                    "transport": str(provider_probe.get("transport", "") or ""),
                    "probe_method": str(provider_probe.get("probe_method", "") or ""),
                    "hints": list(provider_probe.get("hints", []) or []),
                },
                "telegram": {
                    "ok": bool(telegram_probe.get("ok", False)),
                    "status_code": int(telegram_probe.get("status_code", 0) or 0),
                    "error": str(telegram_probe.get("error", "") or ""),
                    "token_masked": str(telegram_probe.get("token_masked", "") or ""),
                },
            },
            "final": {
                "gateway_url": gateway_url,
                "gateway_token": generated_token,
            },
            "steps": payload["steps"],
        }
    except KeyboardInterrupt:
        return {
            "ok": False,
            "mode": "wizard",
            "error": "cancelled",
            "steps": payload["steps"],
        }
