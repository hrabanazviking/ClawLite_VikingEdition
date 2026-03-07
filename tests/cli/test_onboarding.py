from __future__ import annotations

from pathlib import Path

from clawlite.cli.onboarding import apply_provider_selection
from clawlite.cli.onboarding import ensure_gateway_token
from clawlite.cli.onboarding import probe_provider
from clawlite.cli.onboarding import probe_telegram
from clawlite.cli.onboarding import run_onboarding_wizard
from clawlite.config.schema import AppConfig


def test_apply_provider_selection_openai_updates_config() -> None:
    cfg = AppConfig.from_dict({})
    persisted = apply_provider_selection(
        cfg,
        provider="openai",
        api_key="sk-openai-123456",
        base_url="https://api.openai.com/v1",
    )

    assert persisted["provider"] == "openai"
    assert persisted["model"].startswith("openai/")
    assert persisted["api_key_masked"].endswith("3456")
    assert cfg.providers.openai.api_key == "sk-openai-123456"
    assert cfg.providers.openai.api_base == "https://api.openai.com/v1"
    assert cfg.provider.model == cfg.agents.defaults.model


def test_apply_provider_selection_ollama_normalizes_runtime_base_url() -> None:
    cfg = AppConfig.from_dict({})
    persisted = apply_provider_selection(
        cfg,
        provider="ollama",
        api_key="",
        base_url="http://127.0.0.1:11434",
    )

    assert persisted["provider"] == "ollama"
    assert persisted["base_url"] == "http://127.0.0.1:11434/v1"
    assert cfg.provider.litellm_base_url == "http://127.0.0.1:11434/v1"
    assert cfg.providers.ollama.api_base == "http://127.0.0.1:11434/v1"


def test_apply_provider_selection_xai_updates_dynamic_provider_block() -> None:
    cfg = AppConfig.from_dict({})
    persisted = apply_provider_selection(
        cfg,
        provider="xai",
        api_key="xai-key-123456",
        base_url="https://api.x.ai/v1",
    )

    assert persisted["provider"] == "xai"
    assert persisted["model"] == "xai/grok-4"
    assert cfg.providers.get("xai") is not None
    assert cfg.providers.get("xai").api_key == "xai-key-123456"
    assert cfg.providers.get("xai").api_base == "https://api.x.ai/v1"


def test_ensure_gateway_token_generates_when_missing() -> None:
    cfg = AppConfig.from_dict({"gateway": {"auth": {"mode": "required", "token": ""}}})
    generated = ensure_gateway_token(cfg)
    assert generated
    assert cfg.gateway.auth.token == generated


def test_probe_provider_openai_success(monkeypatch) -> None:
    class _Response:
        status_code = 200
        is_success = True
        text = "ok"

        @staticmethod
        def json() -> dict[str, list[dict[str, str]]]:
            return {"data": [{"id": "gpt-4o-mini"}]}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            assert url.endswith("/models")
            assert str(headers.get("Authorization", "")).startswith("Bearer sk-")
            return _Response()

    monkeypatch.setattr("clawlite.cli.onboarding.httpx.Client", _Client)
    payload = probe_provider("openai", api_key="sk-openai-123456", base_url="https://api.openai.com/v1")
    assert payload["ok"] is True
    assert payload["status_code"] == 200
    assert payload["api_key_masked"].endswith("3456")
    assert payload["transport"] == "openai_compatible"
    assert payload["family"] == "openai_compatible"
    assert payload["recommended_model"] == "openai/gpt-4o-mini"
    assert "openai/gpt-4o-mini" in payload["recommended_models"]
    assert "billing" in payload["onboarding_hint"].lower()
    assert payload["default_base_url"] == "https://api.openai.com/v1"
    assert payload["key_envs"] == ["OPENAI_API_KEY"]
    assert payload["model_check"]["checked"] is True
    assert payload["model_check"]["ok"] is True
    assert any("OpenAI-compatible" in row for row in payload["hints"])


def test_probe_telegram_handles_network_error(monkeypatch) -> None:
    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            raise RuntimeError("network_down")

    monkeypatch.setattr("clawlite.cli.onboarding.httpx.Client", _Client)
    payload = probe_telegram("12345:ABCDE")
    assert payload["ok"] is False
    assert payload["error"] == "network_down"
    assert payload["token_masked"].endswith("BCDE")


def test_probe_provider_ollama_accepts_runtime_base_url_with_v1(monkeypatch) -> None:
    class _Response:
        status_code = 200
        is_success = True
        text = "ok"

        @staticmethod
        def json() -> dict[str, list[dict[str, str]]]:
            return {"models": [{"name": "llama3.2:latest"}]}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            del headers
            assert url == "http://127.0.0.1:11434/api/tags"
            return _Response()

    monkeypatch.setattr("clawlite.cli.onboarding.httpx.Client", _Client)
    monkeypatch.setattr(
        "clawlite.cli.onboarding.probe_local_provider_runtime",
        lambda **kwargs: {
            "checked": True,
            "ok": True,
            "runtime": "ollama",
            "base_url": kwargs["base_url"],
            "model": "llama3.2",
            "error": "",
            "detail": "",
            "available_models": ["llama3.2:latest"],
        },
    )
    payload = probe_provider("ollama", api_key="", base_url="http://127.0.0.1:11434/v1")
    assert payload["ok"] is True
    assert payload["status_code"] == 200
    assert payload["transport"] == "local_runtime"
    assert any("Ollama respondeu" in row for row in payload["hints"])


def test_probe_provider_openai_model_not_listed_returns_soft_warning(monkeypatch) -> None:
    class _Response:
        status_code = 200
        is_success = True
        text = "ok"

        @staticmethod
        def json() -> dict[str, list[dict[str, str]]]:
            return {"data": [{"id": "gpt-4o-mini"}]}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            assert url.endswith("/models")
            assert str(headers.get("Authorization", "")).startswith("Bearer sk-")
            return _Response()

    monkeypatch.setattr("clawlite.cli.onboarding.httpx.Client", _Client)
    payload = probe_provider(
        "openai",
        api_key="sk-openai-123456",
        base_url="https://api.openai.com/v1",
        model="openai/gpt-4.1-mini",
    )
    assert payload["ok"] is True
    assert payload["model_check"]["checked"] is True
    assert payload["model_check"]["ok"] is False
    assert any("nao apareceu na lista remota" in row.lower() for row in payload["hints"])


def test_probe_provider_openai_missing_api_key_returns_actionable_hint() -> None:
    payload = probe_provider("openai", api_key="", base_url="https://api.openai.com/v1")
    assert payload["ok"] is False
    assert payload["error"] == "api_key_missing"
    assert payload["transport"] == "openai_compatible"
    assert any("Configure a chave do provider 'openai'" in row for row in payload["hints"])


def test_probe_provider_minimax_uses_anthropic_messages_transport(monkeypatch) -> None:
    class _Response:
        status_code = 200
        is_success = True
        text = "ok"

        @staticmethod
        def json() -> dict[str, str]:
            return {"id": "msg_1"}

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            assert url == "https://api.minimax.io/anthropic/messages"
            assert headers["x-api-key"] == "mini-key"
            assert json["model"] == "MiniMax-M2.5"
            assert json["messages"][0]["content"] == "ping"
            return _Response()

    monkeypatch.setattr("clawlite.cli.onboarding.httpx.Client", _Client)
    payload = probe_provider(
        "minimax",
        api_key="mini-key",
        base_url="https://api.minimax.io/anthropic",
        model="minimax/MiniMax-M2.5",
    )
    assert payload["ok"] is True
    assert payload["status_code"] == 200
    assert payload["family"] == "anthropic_compatible"
    assert payload["recommended_model"] == "minimax/MiniMax-M2.5"
    assert "minimax/MiniMax-M2.5" in payload["recommended_models"]
    assert "/anthropic" in payload["onboarding_hint"]


def test_run_onboarding_wizard_advanced_persists_custom_model_and_gateway(monkeypatch, tmp_path) -> None:
    cfg = AppConfig.from_dict(
        {
            "workspace_path": str(tmp_path / "workspace"),
            "gateway": {"host": "127.0.0.1", "port": 8787, "auth": {"mode": "off", "token": ""}},
            "provider": {"model": "openai/gpt-4o-mini", "litellm_base_url": "https://api.openai.com/v1"},
        }
    )

    prompt_answers = iter(
        [
            "advanced",
            "0.0.0.0",
            "19090",
            "required",
            "openai",
            "https://api.openai.com/v1",
            "openai/gpt-4.1-mini",
            "sk-openai-123456",
        ]
    )
    confirm_answers = iter([False])

    def _fake_prompt_ask(*args, **kwargs):
        return next(prompt_answers)

    def _fake_confirm_ask(*args, **kwargs):
        return next(confirm_answers)

    monkeypatch.setattr("clawlite.cli.onboarding.Prompt.ask", _fake_prompt_ask)
    monkeypatch.setattr("clawlite.cli.onboarding.Confirm.ask", _fake_confirm_ask)
    monkeypatch.setattr(
        "clawlite.cli.onboarding.probe_provider",
        lambda provider, *, api_key, base_url, model="", timeout_s=8.0: {
            "ok": True,
            "status_code": 200,
            "provider": provider,
            "family": "openai_compatible",
            "recommended_model": "openai/gpt-4o-mini",
            "recommended_models": ["openai/gpt-4o-mini", "openai/gpt-4.1-mini"],
            "onboarding_hint": "OpenAI responde via endpoint OpenAI-compatible padrão; valide billing e projeto ativo.",
            "base_url": base_url,
            "api_key_masked": "********3456",
            "error": "",
        },
    )
    monkeypatch.setattr(
        "clawlite.cli.onboarding.probe_telegram",
        lambda token, *, timeout_s=8.0: {
            "ok": True,
            "status_code": 200,
            "token_masked": "",
            "error": "",
        },
    )

    class _FakeWorkspaceLoader:
        def __init__(self, workspace_path):
            self.workspace_path = workspace_path

        def bootstrap(self, *, overwrite, variables):
            return [Path(self.workspace_path) / "IDENTITY.md"]

    monkeypatch.setattr("clawlite.cli.onboarding.WorkspaceLoader", _FakeWorkspaceLoader)

    payload = run_onboarding_wizard(
        cfg,
        config_path=tmp_path / "config.json",
        overwrite=True,
        variables={"assistant_name": "Fox"},
    )

    assert payload["ok"] is True
    assert payload["steps"][1]["step"] == 2
    assert payload["steps"][1]["provider"] == "openai"
    assert payload["steps"][1]["model"] == "openai/gpt-4.1-mini"
    assert payload["steps"][1]["family"] == "openai_compatible"
    assert payload["steps"][1]["recommended_model"] == "openai/gpt-4o-mini"
    assert payload["steps"][1]["recommended_models"] == ["openai/gpt-4o-mini", "openai/gpt-4.1-mini"]
    assert "billing" in payload["steps"][1]["onboarding_hint"].lower()
    assert payload["persisted"]["provider"]["model"] == "openai/gpt-4.1-mini"
    assert payload["persisted"]["gateway"]["host"] == "0.0.0.0"
    assert payload["persisted"]["gateway"]["port"] == 19090
    assert payload["persisted"]["gateway"]["auth_mode"] == "required"
    assert payload["final"]["gateway_url"] == "http://0.0.0.0:19090"
    assert payload["final"]["gateway_token"]


def test_run_onboarding_wizard_disables_existing_telegram_when_user_declines(monkeypatch, tmp_path) -> None:
    cfg = AppConfig.from_dict(
        {
            "workspace_path": str(tmp_path / "workspace"),
            "channels": {
                "telegram": {
                    "enabled": True,
                    "token": "123:ABC",
                }
            },
            "provider": {"model": "openai/gpt-4o-mini", "litellm_base_url": "https://api.openai.com/v1"},
        }
    )

    prompt_answers = iter(
        [
            "basic",
            "openai",
            "https://api.openai.com/v1",
            "sk-openai-123456",
        ]
    )
    confirm_answers = iter([False])

    def _fake_prompt_ask(*args, **kwargs):
        return next(prompt_answers)

    def _fake_confirm_ask(*args, **kwargs):
        return next(confirm_answers)

    monkeypatch.setattr("clawlite.cli.onboarding.Prompt.ask", _fake_prompt_ask)
    monkeypatch.setattr("clawlite.cli.onboarding.Confirm.ask", _fake_confirm_ask)
    monkeypatch.setattr(
        "clawlite.cli.onboarding.probe_provider",
        lambda provider, *, api_key, base_url, model="", timeout_s=8.0: {
            "ok": True,
            "status_code": 200,
            "provider": provider,
            "family": "openai_compatible",
            "recommended_model": "openai/gpt-4o-mini",
            "recommended_models": ["openai/gpt-4o-mini"],
            "onboarding_hint": "",
            "base_url": base_url,
            "api_key_masked": "********3456",
            "error": "",
        },
    )

    class _FakeWorkspaceLoader:
        def __init__(self, workspace_path):
            self.workspace_path = workspace_path

        def bootstrap(self, *, overwrite, variables):
            return [Path(self.workspace_path) / "IDENTITY.md"]

    monkeypatch.setattr("clawlite.cli.onboarding.WorkspaceLoader", _FakeWorkspaceLoader)

    payload = run_onboarding_wizard(
        cfg,
        config_path=tmp_path / "config.json",
        overwrite=True,
        variables={"assistant_name": "Fox"},
    )

    assert payload["ok"] is True
    assert payload["steps"][2]["enabled"] is False
    assert payload["persisted"]["telegram"]["enabled"] is False
    assert cfg.channels.telegram.enabled is False
    assert cfg.channels.telegram.token == "123:ABC"
