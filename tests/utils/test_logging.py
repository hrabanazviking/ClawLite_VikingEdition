from __future__ import annotations

import asyncio
from pathlib import Path

from loguru import logger

from clawlite.channels.telegram import TelegramChannel
from clawlite.scheduler.cron import CronService
from clawlite.utils import logging as logging_utils


def _reset_logging_state() -> None:
    logger.remove()
    logging_utils._LOGGING_CONFIGURED = False


def test_plain_logger_uses_default_extra_fields(monkeypatch) -> None:
    _reset_logging_state()
    monkeypatch.setenv("CLAWLITE_LOG_STDERR", "0")
    logging_utils.setup_logging(level="INFO")

    rows: list[str] = []
    sink_id = logger.add(rows.append, format=logging_utils._text_format())
    logger.info("plain log line")
    logger.remove(sink_id)

    assert rows
    line = rows[0]
    assert "event=-" in line
    assert "session=-" in line
    assert "channel=-" in line
    assert "tool=-" in line
    assert "run=-" in line


def test_cron_and_telegram_plain_logger_calls_work(monkeypatch, tmp_path: Path) -> None:
    _reset_logging_state()
    monkeypatch.setenv("CLAWLITE_LOG_STDERR", "0")
    logging_utils.setup_logging(level="INFO")

    rows: list[str] = []
    sink_id = logger.add(rows.append, format=logging_utils._text_format())

    async def _run() -> None:
        service = CronService(tmp_path / "cron.json")

        async def _on_job(_job):
            return "ok"

        await service.start(_on_job)
        await service.stop()

        channel = TelegramChannel(config={"token": "x:token"})
        await channel.start()
        await channel.stop()

    asyncio.run(_run())
    logger.remove(sink_id)

    joined = "\n".join(rows)
    assert "event=-" in joined
    assert "cron service started" in joined
    assert "telegram channel starting" in joined
