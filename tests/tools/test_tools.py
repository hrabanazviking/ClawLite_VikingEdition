from __future__ import annotations
import sys
import pytest

def test_browser_tool_schema():
    from clawlite.tools.browser import BrowserTool
    t = BrowserTool()
    assert t.name == "browser"
    schema = t.args_schema()
    assert "navigate" in schema["properties"]["action"]["enum"]

def test_tts_tool_schema():
    from clawlite.tools.tts import TTSTool
    t = TTSTool()
    assert t.name == "tts"
    assert "text" in t.args_schema()["properties"]

def test_pdf_tool_schema():
    from clawlite.tools.pdf import PdfReadTool
    t = PdfReadTool()
    assert t.name == "pdf_read"
    assert "path" in t.args_schema()["properties"]

@pytest.mark.asyncio
async def test_pdf_missing_file():
    from clawlite.tools.pdf import PdfReadTool
    from clawlite.tools.base import ToolContext
    t = PdfReadTool()
    ctx = ToolContext(session_id="t", channel="t", user_id="t")
    result = await t.run({"path": "/nonexistent/file.pdf"}, ctx)
    assert "error" in result.lower()


@pytest.mark.asyncio
async def test_tts_missing_dependency_reports_media_extra(monkeypatch):
    from clawlite.tools.tts import TTSTool
    from clawlite.tools.base import ToolContext

    monkeypatch.setitem(sys.modules, "edge_tts", None)
    t = TTSTool()
    ctx = ToolContext(session_id="t", channel="t", user_id="t")
    result = await t.run({"text": "hello"}, ctx)
    assert 'clawlite[media]' in result


@pytest.mark.asyncio
async def test_pdf_missing_dependency_reports_media_extra(monkeypatch):
    from clawlite.tools.pdf import PdfReadTool
    from clawlite.tools.base import ToolContext

    monkeypatch.setitem(sys.modules, "pypdf", None)
    t = PdfReadTool()
    ctx = ToolContext(session_id="t", channel="t", user_id="t")
    result = await t.run({"path": "/tmp/demo.pdf"}, ctx)
    assert 'clawlite[media]' in result
