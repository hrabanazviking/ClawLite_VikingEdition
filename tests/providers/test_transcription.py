from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from clawlite.providers.transcription import TranscriptionProvider


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = dict(headers or {})
        self.text = ""

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://api.example/v1/audio/transcriptions")
            response = httpx.Response(self.status_code, request=request, json=self._payload, headers=self.headers)
            raise httpx.HTTPStatusError("err", request=request, response=response)

    def json(self) -> dict:
        return self._payload


def test_transcription_provider_streams_file_instead_of_read_bytes(tmp_path) -> None:
    async def _scenario() -> None:
        audio_path = tmp_path / "sample.mp3"
        audio_path.write_bytes(b"fake-audio")
        provider = TranscriptionProvider(api_key="k", base_url="https://api.example/v1", retry_max_attempts=1)

        post_mock = AsyncMock(side_effect=[_FakeResponse(200, {"text": "ok"})])
        with patch.object(Path, "read_bytes", side_effect=AssertionError("read_bytes should not be used")):
            with patch("httpx.AsyncClient.post", new=post_mock):
                out = await provider.transcribe(audio_path)

        assert out == "ok"
        sent_files = post_mock.call_args.kwargs["files"]
        assert hasattr(sent_files["file"][1], "read")

    asyncio.run(_scenario())


def test_transcription_provider_retries_transient_http_error_then_succeeds(tmp_path) -> None:
    async def _scenario() -> None:
        audio_path = tmp_path / "sample.mp3"
        audio_path.write_bytes(b"fake-audio")
        provider = TranscriptionProvider(
            api_key="k",
            base_url="https://api.example/v1",
            retry_max_attempts=3,
            retry_initial_backoff_s=0,
            retry_max_backoff_s=0,
            retry_jitter_s=0,
        )

        post_mock = AsyncMock(side_effect=[_FakeResponse(503, {"error": {"message": "busy"}}), _FakeResponse(200, {"text": "ok"})])
        sleep_mock = AsyncMock()
        with patch("httpx.AsyncClient.post", new=post_mock), patch("asyncio.sleep", new=sleep_mock):
            out = await provider.transcribe(audio_path)

        assert out == "ok"
        assert post_mock.call_count == 2
        assert sleep_mock.await_count == 1

    asyncio.run(_scenario())
