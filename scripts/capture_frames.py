# scripts/capture_frames.py
"""Captura frames PNG do template HTML usando Playwright (chromium headless)."""
from __future__ import annotations
from typing import Any
from scripts.terminal_template import build_html


def capture_frames(
    frames_spec: list[dict[str, Any]],
    *,
    width: int = 720,
    height: int = 400,
) -> list[tuple[bytes, int]]:
    from playwright.sync_api import sync_playwright
    results: list[tuple[bytes, int]] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})
        for spec in frames_spec:
            html = build_html(
                lines=spec.get("lines", []),
                width=width,
                height=height,
                show_prompt=spec.get("show_prompt", True),
                partial_prompt=spec.get("partial_prompt"),
                show_cursor=spec.get("show_cursor", False),
                spinner=spec.get("spinner"),
            )
            page.set_content(html, wait_until="domcontentloaded")
            png_bytes = page.screenshot(type="png")
            results.append((png_bytes, int(spec["delay_ms"])))
        browser.close()
    return results
