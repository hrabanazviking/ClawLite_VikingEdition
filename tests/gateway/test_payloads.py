from __future__ import annotations

from types import SimpleNamespace

from clawlite.gateway.payloads import (
    dashboard_bootstrap_payload,
    mask_secret,
    provider_autonomy_snapshot,
    provider_telemetry_snapshot,
    render_root_dashboard_html,
)


class _ProviderWithUnsafeDiagnostics:
    provider_name = "failover"
    model = "openai/gpt-4o-mini"

    def diagnostics(self) -> dict[str, object]:
        return {
            "provider": "failover",
            "provider_name": "failover",
            "model": "openai/gpt-4o-mini",
            "transport": "openai_compatible",
            "api_key": "top-level-secret",
            "counters": {
                "fallback_attempts": 2,
                "last_error_class": "rate_limit",
            },
            "nested": {
                "access_token": "nested-secret",
                "safe": "ok",
            },
            "candidates": [
                {
                    "role": "primary",
                    "model": "openai/gpt-4o-mini",
                    "in_cooldown": True,
                    "cooldown_remaining_s": 17.25,
                    "suppression_reason": "auth",
                },
                {
                    "role": "fallback",
                    "model": "groq/llama-3.1-8b-instant",
                    "in_cooldown": False,
                    "cooldown_remaining_s": 0.0,
                    "suppression_reason": "",
                },
            ],
        }


def test_dashboard_bootstrap_payload_and_html_render() -> None:
    control_plane = SimpleNamespace(
        dict=lambda: {
            "ready": True,
            "phase": "ready",
            "auth": {"mode": "required", "token_configured": True},
        }
    )

    payload = dashboard_bootstrap_payload(
        control_plane=control_plane,
        dashboard_asset_root="/_clawlite",
    )
    assert payload["control_plane"]["ready"] is True
    assert payload["auth"]["mode"] == "required"
    assert payload["assets"]["css"] == "/_clawlite/dashboard.css"

    html = render_root_dashboard_html(
        control_plane=control_plane,
        dashboard_asset_root="/_clawlite",
        dashboard_bootstrap_token="__CLAWLITE_DASHBOARD_BOOTSTRAP_JSON__",
    )
    assert "__CLAWLITE_DASHBOARD_BOOTSTRAP_JSON__" not in html
    assert '"ready": true' in html
    assert '"/api/dashboard/state"' in html


def test_provider_telemetry_snapshot_sanitizes_sensitive_keys() -> None:
    payload = provider_telemetry_snapshot(_ProviderWithUnsafeDiagnostics())
    assert payload["diagnostics_available"] is True
    assert payload["provider"] == "failover"
    assert "api_key" not in payload
    assert "access_token" not in payload["nested"]
    assert payload["nested"]["safe"] == "ok"
    assert isinstance(payload["summary"], dict)


def test_provider_autonomy_snapshot_uses_cooldown_and_suppression_reason() -> None:
    snapshot = provider_autonomy_snapshot(provider=_ProviderWithUnsafeDiagnostics())
    assert snapshot["provider"] == "failover"
    assert snapshot["state"] == "cooldown"
    assert snapshot["cooldown_remaining_s"] == 17.25
    assert snapshot["suppression_reason"] == "auth"
    assert "failover" in snapshot["suppression_hint"].lower()


def test_mask_secret_keeps_tail() -> None:
    assert mask_secret("abcdef123456", keep=4).endswith("3456")
    assert mask_secret("abcd", keep=4) == "****"
