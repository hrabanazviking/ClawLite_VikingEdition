from __future__ import annotations

import asyncio

from clawlite.channels.telegram_transport import (
    activate_webhook,
    delete_webhook,
    operator_refresh_summary,
    webhook_requested,
)


def test_telegram_webhook_requested_accepts_mode_or_explicit_enable() -> None:
    assert webhook_requested(mode="webhook", webhook_enabled=False) is True
    assert webhook_requested(mode="polling", webhook_enabled=True) is True
    assert webhook_requested(mode="polling", webhook_enabled=False) is False


def test_telegram_operator_refresh_summary_exposes_transport_flags() -> None:
    payload = operator_refresh_summary(
        mode="webhook",
        webhook_requested=True,
        webhook_mode_active=False,
        connected=False,
        last_error="boom",
    )

    assert payload["mode"] == "webhook"
    assert payload["webhook_requested"] is True
    assert payload["webhook_activated"] is False
    assert payload["webhook_mode_active"] is False
    assert payload["last_error"] == "boom"


def test_telegram_delete_webhook_supports_legacy_signature() -> None:
    class _LegacyBot:
        def __init__(self) -> None:
            self.calls = 0

        async def delete_webhook(self, **kwargs):
            self.calls += 1
            if "drop_pending_updates" in kwargs:
                raise TypeError("drop_pending_updates unsupported")
            return True

    async def _scenario() -> None:
        result = await delete_webhook(bot=_LegacyBot())
        assert result.deleted is True
        assert result.legacy is True

    asyncio.run(_scenario())


def test_telegram_activate_webhook_reports_missing_and_success() -> None:
    class _Bot:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def set_webhook(self, **kwargs):
            self.calls.append(kwargs)
            return True

    async def _scenario() -> None:
        missing = await activate_webhook(
            ensure_bot=lambda: _impossible_bot(),
            webhook_url="",
            webhook_secret="",
            allowed_updates=["message"],
        )
        assert missing.activated is False
        assert missing.missing == ("webhook_url", "webhook_secret")

        bot = _Bot()

        async def _ensure_bot():
            return bot

        result = await activate_webhook(
            ensure_bot=_ensure_bot,
            webhook_url="https://example.com/hook",
            webhook_secret="secret-1",
            allowed_updates=["message"],
        )
        assert result.activated is True
        assert bot.calls[0]["url"] == "https://example.com/hook"
        assert bot.calls[0]["secret_token"] == "secret-1"
        assert bot.calls[0]["allowed_updates"] == ["message"]

    async def _impossible_bot():
        raise AssertionError("ensure_bot should not be called for missing config")

    asyncio.run(_scenario())
