from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from loguru import logger

from clawlite.utils.logging import bind_event


@dataclass
class GatewayRequestHandlers:
    auth_guard: Any
    diagnostics_require_auth: bool
    runtime: Any
    dashboard_asset_root: str
    dashboard_bootstrap_token: str
    run_engine_with_timeout_fn: Callable[[str, str], Awaitable[Any]]
    provider_error_payload_fn: Callable[[RuntimeError], tuple[int, str]]
    finalize_bootstrap_for_user_turn_fn: Callable[[str], None]
    build_tools_catalog_payload_fn: Callable[..., dict[str, Any]]
    parse_include_schema_flag_fn: Callable[[Any], bool]
    control_plane_payload_fn: Callable[[], Any]
    dashboard_asset_text_fn: Callable[[str], str]
    render_root_dashboard_html_fn: Callable[..., str]

    def _check_control(self, request: Request) -> None:
        self.auth_guard.check_http(
            request=request,
            scope="control",
            diagnostics_auth=self.diagnostics_require_auth,
        )

    async def chat(self, req: Any, request: Request) -> Any:
        self._check_control(request)
        if not str(req.session_id or "").strip() or not str(req.text or "").strip():
            raise HTTPException(status_code=400, detail="session_id and text are required")
        logger.debug("chat request received session={} chars={}", req.session_id, len(str(req.text or "")))
        try:
            out = await self.run_engine_with_timeout_fn(str(req.session_id), str(req.text))
        except RuntimeError as exc:
            status_code, detail = self.provider_error_payload_fn(exc)
            bind_event("gateway.chat", session=str(req.session_id)).error(
                "chat request failed status={} detail={}",
                status_code,
                detail,
            )
            raise HTTPException(status_code=status_code, detail=detail) from exc
        self.finalize_bootstrap_for_user_turn_fn(str(req.session_id))
        bind_event("gateway.chat", session=str(req.session_id)).info("chat response generated model={}", out.model)
        return {"text": out.text, "model": out.model}

    async def tools_catalog(self, request: Request) -> dict[str, Any]:
        self._check_control(request)
        include_schema = self.parse_include_schema_flag_fn(request.query_params)
        return self.build_tools_catalog_payload_fn(self.runtime.engine.tools.schema(), include_schema=include_schema)

    async def tools_approvals(
        self,
        request: Request,
        *,
        status: str = "pending",
        session_id: str = "",
        channel: str = "",
        include_grants: bool = False,
        limit: int = 50,
    ) -> dict[str, Any]:
        self._check_control(request)
        tools = getattr(self.runtime.engine, "tools", None)
        list_requests = getattr(tools, "approval_requests_snapshot", None)
        if not callable(list_requests):
            return {
                "ok": True,
                "status": str(status or "pending").strip().lower() or "pending",
                "session_id": str(session_id or "").strip(),
                "channel": str(channel or "").strip().lower(),
                "include_grants": bool(include_grants),
                "count": 0,
                "requests": [],
                "grant_count": 0,
                "grants": [],
            }
        requests = list_requests(
            status=str(status or "pending").strip().lower() or "pending",
            session_id=str(session_id or "").strip(),
            channel=str(channel or "").strip().lower(),
            limit=max(1, int(limit or 1)),
        )
        grants: list[dict[str, Any]] = []
        if include_grants:
            list_grants = getattr(tools, "approval_grants_snapshot", None)
            if callable(list_grants):
                grants = list_grants(
                    session_id=str(session_id or "").strip(),
                    channel=str(channel or "").strip().lower(),
                    limit=max(1, int(limit or 1)),
                )
        return {
            "ok": True,
            "status": str(status or "pending").strip().lower() or "pending",
            "session_id": str(session_id or "").strip(),
            "channel": str(channel or "").strip().lower(),
            "include_grants": bool(include_grants),
            "count": len(requests),
            "requests": requests,
            "grant_count": len(grants),
            "grants": grants,
        }

    async def tools_approval_review(
        self,
        request: Request,
        *,
        request_id: str,
        decision: str,
        actor: str = "",
        note: str = "",
    ) -> dict[str, Any]:
        self._check_control(request)
        tools = getattr(self.runtime.engine, "tools", None)
        review_fn = getattr(tools, "review_approval_request", None)
        if not callable(review_fn):
            raise HTTPException(status_code=501, detail="tool_approval_flow_not_enabled")

        summary = await asyncio.to_thread(
            review_fn,
            str(request_id or "").strip(),
            decision=str(decision or "").strip().lower(),
            actor=str(actor or "").strip(),
            note=str(note or "").strip(),
        )
        if not isinstance(summary, dict):
            raise HTTPException(status_code=500, detail="tool_approval_review_failed")
        if not bool(summary.get("ok", False)):
            error = str(summary.get("error", "tool_approval_review_failed") or "tool_approval_review_failed")
            if error == "approval_request_not_found":
                raise HTTPException(status_code=404, detail=error)
            if error == "invalid_review_decision":
                raise HTTPException(status_code=400, detail=error)
            raise HTTPException(status_code=400, detail=error)
        return {"ok": True, "summary": summary}

    async def tools_grants_revoke(
        self,
        request: Request,
        *,
        session_id: str = "",
        channel: str = "",
        rule: str = "",
    ) -> dict[str, Any]:
        self._check_control(request)
        tools = getattr(self.runtime.engine, "tools", None)
        revoke_fn = getattr(tools, "revoke_approval_grants", None)
        if not callable(revoke_fn):
            raise HTTPException(status_code=501, detail="tool_approval_flow_not_enabled")

        summary = await asyncio.to_thread(
            revoke_fn,
            session_id=str(session_id or "").strip(),
            channel=str(channel or "").strip().lower(),
            rule=str(rule or "").strip().lower(),
        )
        if not isinstance(summary, dict) or not bool(summary.get("ok", False)):
            error = "tool_grant_revoke_failed"
            if isinstance(summary, dict):
                error = str(summary.get("error", error) or error)
            raise HTTPException(status_code=400, detail=error)
        return {"ok": True, "summary": summary}

    async def cron_add(self, req: Any, request: Request) -> dict[str, Any]:
        self._check_control(request)
        job_id = await self.runtime.cron.add_job(
            session_id=req.session_id,
            expression=req.expression,
            prompt=req.prompt,
            name=req.name,
        )
        return {"ok": True, "status": "created", "id": job_id}

    async def cron_list(self, *, session_id: str, request: Request) -> dict[str, Any]:
        self._check_control(request)
        return {"jobs": self.runtime.cron.list_jobs(session_id=session_id)}

    async def cron_remove(self, *, job_id: str, request: Request) -> dict[str, Any]:
        self._check_control(request)
        removed = await asyncio.to_thread(self.runtime.cron.remove_job, job_id)
        return {"ok": removed, "status": "removed" if removed else "not_found"}

    async def dashboard_css(self) -> Response:
        return Response(
            content=self.dashboard_asset_text_fn("dashboard.css"),
            media_type="text/css",
        )

    async def dashboard_js(self) -> Response:
        return Response(
            content=self.dashboard_asset_text_fn("dashboard.js"),
            media_type="application/javascript",
        )

    async def root(self) -> HTMLResponse:
        control_plane = self.control_plane_payload_fn()
        return HTMLResponse(
            content=self.render_root_dashboard_html_fn(
                control_plane=control_plane,
                dashboard_asset_root=self.dashboard_asset_root,
                dashboard_bootstrap_token=self.dashboard_bootstrap_token,
            ),
            status_code=200,
        )


__all__ = ["GatewayRequestHandlers"]
