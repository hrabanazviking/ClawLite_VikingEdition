from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import patch

from clawlite.providers import reliability


def test_parse_retry_after_seconds_accepts_numeric_value() -> None:
    assert reliability.parse_retry_after_seconds("1.25") == 1.25


def test_parse_retry_after_seconds_accepts_http_date_value() -> None:
    now = datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc)
    header = format_datetime(now + timedelta(seconds=15), usegmt=True)
    with patch("clawlite.providers.reliability.datetime") as mocked_datetime:
        mocked_datetime.now.return_value = now
        delay = reliability.parse_retry_after_seconds(header)
    assert delay == 15.0


def test_parse_retry_after_seconds_clamps_past_http_date_to_zero() -> None:
    now = datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc)
    header = format_datetime(now - timedelta(seconds=10), usegmt=True)
    with patch("clawlite.providers.reliability.datetime") as mocked_datetime:
        mocked_datetime.now.return_value = now
        delay = reliability.parse_retry_after_seconds(header)
    assert delay == 0.0
