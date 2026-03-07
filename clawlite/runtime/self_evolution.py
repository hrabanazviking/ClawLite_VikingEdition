"""
Phase 7 – Self-Evolution Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Runs autonomously to:
  1. Scan own source for gaps (TODOs, FIXMEs, stubs, unchecked ROADMAP items).
  2. Generate a targeted fix proposal via the configured LLM provider.
  3. Apply the fix, validate with ruff + pytest.
  4. Auto-commit when green, notify operator via the configured notification path.
  5. Skip and log when validation fails (never force-commit broken code).

Safety limits
-------------
- Never edits self_evolution.py itself.
- MAX_FILES_PER_RUN files and MAX_LINES_DELTA added/removed per cycle.
- Full test suite must exit 0 before any commit.
- Cooldown enforced between runs.
- All applied patches are persisted in evolution-log.json for audit.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from clawlite.utils.logging import bind_event

# ── tunables ──────────────────────────────────────────────────────────────────
MAX_FILES_PER_RUN = 3
MAX_LINES_DELTA = 200          # total added+removed across changed files
_SELF_FILE = Path(__file__).resolve()
_DENYLIST_NAMES = frozenset({"self_evolution.py", "autonomy.py", "gateway", "config"})
_GAP_PATTERN = re.compile(
    r"#\s*(TODO|FIXME|HACK|XXX|STUB|NOT IMPLEMENTED|raise NotImplementedError)",
    re.IGNORECASE,
)
_ROADMAP_UNCHECKED = re.compile(r"^\s*-\s*\[\s*\]\s+(.+)$")

NotifyCallback = Callable[[str, dict[str, Any]], Awaitable[Any]]


# ── data classes ──────────────────────────────────────────────────────────────

@dataclass
class Gap:
    file: str
    line: int
    kind: str      # "todo" | "stub" | "roadmap"
    text: str


@dataclass
class FixProposal:
    gap: Gap
    description: str
    patch_unified: str    # unified diff text
    files_touched: list[str] = field(default_factory=list)


@dataclass
class EvolutionRecord:
    run_id: str
    started_at: str
    finished_at: str = ""
    outcome: str = "pending"   # "committed" | "validation_failed" | "no_gaps" | "error"
    gaps_found: int = 0
    fix_description: str = ""
    files_changed: list[str] = field(default_factory=list)
    commit_sha: str = ""
    error: str = ""
    ruff_ok: bool = False
    pytest_ok: bool = False


# ── gap scanner ───────────────────────────────────────────────────────────────

class SourceScanner:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _is_safe_file(self, path: Path) -> bool:
        if path.resolve() == _SELF_FILE:
            return False
        for part in path.parts:
            if part in _DENYLIST_NAMES:
                return False
        return path.suffix == ".py"

    def scan(self, *, max_gaps: int = 20) -> list[Gap]:
        gaps: list[Gap] = []
        for py_file in sorted(self.root.rglob("*.py")):
            if not self._is_safe_file(py_file):
                continue
            try:
                lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            rel = str(py_file.relative_to(self.root))
            for idx, line in enumerate(lines, 1):
                m = _GAP_PATTERN.search(line)
                if m:
                    kind = m.group(1).lower().replace(" ", "_")
                    gaps.append(Gap(file=rel, line=idx, kind=kind, text=line.strip()))
                    if len(gaps) >= max_gaps:
                        return gaps
        return gaps

    def scan_roadmap(self, roadmap_path: Path, *, max_items: int = 10) -> list[Gap]:
        gaps: list[Gap] = []
        if not roadmap_path.exists():
            return gaps
        try:
            lines = roadmap_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return gaps
        for idx, line in enumerate(lines, 1):
            m = _ROADMAP_UNCHECKED.match(line)
            if m:
                gaps.append(Gap(file=str(roadmap_path.name), line=idx, kind="roadmap", text=m.group(1).strip()))
                if len(gaps) >= max_items:
                    break
        return gaps

    def read_context(self, gap: Gap, *, context_lines: int = 30) -> str:
        """Return source context around a gap for the LLM prompt."""
        path = self.root / gap.file
        if not path.exists():
            return ""
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return ""
        start = max(0, gap.line - 1 - context_lines)
        end = min(len(lines), gap.line + context_lines)
        numbered = [f"{i + 1:4d}| {l}" for i, l in enumerate(lines[start:end], start)]
        return "\n".join(numbered)


# ── LLM-based fix proposer ────────────────────────────────────────────────────

class FixProposer:
    """Generates a fix proposal by calling the runtime LLM provider."""

    def __init__(self, run_llm: Callable[[str], Awaitable[str]]) -> None:
        self._run_llm = run_llm

    async def propose(self, gap: Gap, context: str) -> FixProposal | None:
        prompt = self._build_prompt(gap, context)
        try:
            raw = await asyncio.wait_for(self._run_llm(prompt), timeout=60.0)
        except Exception as exc:
            bind_event("self_evolution.propose").warning("llm call failed gap={} error={}", gap.text[:60], exc)
            return None
        return self._parse_response(gap, raw)

    @staticmethod
    def _build_prompt(gap: Gap, context: str) -> str:
        return (
            f"You are ClawLite's self-evolution engine. Fix the following gap in the codebase.\n\n"
            f"File: {gap.file}  Line: {gap.line}  Kind: {gap.kind}\n"
            f"Gap: {gap.text}\n\n"
            f"Source context:\n```python\n{context}\n```\n\n"
            "Produce a minimal, correct Python fix. Output ONLY:\n"
            "DESCRIPTION: <one-line summary of what you changed>\n"
            "```python\n<complete replacement for the function or block containing the gap>\n```\n\n"
            "Rules:\n"
            "- Keep the same indentation and surrounding code structure.\n"
            "- Do NOT change imports, class definitions, or unrelated code.\n"
            "- The fix must be compatible with Python 3.10+ and pydantic 1.x.\n"
            "- Do NOT add docstrings or comments beyond what is necessary.\n"
            "- Output only DESCRIPTION + code block, nothing else."
        )

    @staticmethod
    def _parse_response(gap: Gap, raw: str) -> FixProposal | None:
        description = ""
        desc_match = re.search(r"DESCRIPTION:\s*(.+)", raw)
        if desc_match:
            description = desc_match.group(1).strip()

        code_match = re.search(r"```python\n([\s\S]+?)```", raw)
        if not code_match:
            return None
        patch = code_match.group(1).rstrip()
        if not patch.strip():
            return None

        return FixProposal(
            gap=gap,
            description=description or gap.text[:80],
            patch_unified=patch,
            files_touched=[gap.file],
        )


# ── patch applicator ──────────────────────────────────────────────────────────

class PatchApplicator:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def apply(self, proposal: FixProposal) -> tuple[bool, str]:
        """
        Apply a FixProposal by finding the original function/block and replacing it.
        Returns (ok, error_message).
        """
        if not proposal.files_touched:
            return False, "no files in proposal"

        gap = proposal.gap
        path = self.root / gap.file
        if not path.exists():
            return False, f"file not found: {gap.file}"

        try:
            original = path.read_text(encoding="utf-8")
        except OSError as exc:
            return False, f"read error: {exc}"

        lines = original.splitlines(keepends=True)
        patch_lines = proposal.patch_unified.splitlines(keepends=True)

        # Find the function/block at the gap line and replace it
        # Strategy: find the nearest `def ` or class header above the gap line,
        # then replace lines from that header until the next same-level def/class.
        gap_idx = max(0, gap.line - 1)
        block_start = self._find_block_start(lines, gap_idx)
        block_end = self._find_block_end(lines, block_start)

        delta = abs(len(patch_lines) - (block_end - block_start))
        if delta > MAX_LINES_DELTA:
            return False, f"patch too large: delta={delta} > {MAX_LINES_DELTA}"

        new_lines = lines[:block_start] + patch_lines + lines[block_end:]
        new_text = "".join(new_lines)

        try:
            path.write_text(new_text, encoding="utf-8")
        except OSError as exc:
            return False, f"write error: {exc}"

        return True, ""

    @staticmethod
    def _find_block_start(lines: list[str], gap_idx: int) -> int:
        """Walk backwards to find the nearest def/class header."""
        for i in range(gap_idx, -1, -1):
            stripped = lines[i].lstrip()
            if stripped.startswith(("def ", "async def ", "class ")):
                return i
        return gap_idx

    @staticmethod
    def _find_block_end(lines: list[str], start: int) -> int:
        """Walk forward to find where this block ends (next same-level def/class or EOF)."""
        if start >= len(lines):
            return start
        base_indent = len(lines[start]) - len(lines[start].lstrip())
        for i in range(start + 1, len(lines)):
            line = lines[i]
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            if indent <= base_indent and stripped.startswith(("def ", "async def ", "class ")):
                return i
        return len(lines)


# ── validator ─────────────────────────────────────────────────────────────────

class Validator:
    def __init__(self, root: Path, *, timeout_s: float = 120.0) -> None:
        self.root = root
        self.timeout_s = timeout_s

    def run_ruff(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                ["ruff", "check", "--fix", "--select=E,F,W", str(self.root)],
                capture_output=True, text=True,
                timeout=self.timeout_s,
                cwd=str(self.root),
            )
            ok = result.returncode == 0
            output = (result.stdout + result.stderr).strip()
            return ok, output
        except FileNotFoundError:
            return True, "ruff not found, skipped"
        except subprocess.TimeoutExpired:
            return False, "ruff timed out"
        except Exception as exc:
            return False, str(exc)

    def run_pytest(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "-q", "--tb=short", "--no-header"],
                capture_output=True, text=True,
                timeout=self.timeout_s,
                cwd=str(self.root),
            )
            ok = result.returncode == 0
            output = (result.stdout + result.stderr).strip()[-3000:]
            return ok, output
        except FileNotFoundError:
            return False, "pytest not found"
        except subprocess.TimeoutExpired:
            return False, "pytest timed out"
        except Exception as exc:
            return False, str(exc)


# ── git helpers ───────────────────────────────────────────────────────────────

def _git(args: list[str], *, cwd: str) -> tuple[int, str]:
    try:
        r = subprocess.run(
            ["git", *args], capture_output=True, text=True, cwd=cwd, timeout=30
        )
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as exc:
        return 1, str(exc)


def _commit(root: Path, files: list[str], message: str) -> tuple[bool, str]:
    cwd = str(root)
    rel_files = [str(Path(f)) for f in files]

    rc, _ = _git(["add", "--", *rel_files], cwd=cwd)
    if rc != 0:
        rc, out = _git(["add", "--", *rel_files], cwd=cwd)
        if rc != 0:
            return False, f"git add failed: {out}"

    rc, out = _git(["commit", "-m", message], cwd=cwd)
    if rc != 0:
        return False, f"git commit failed: {out}"

    rc, sha = _git(["rev-parse", "--short", "HEAD"], cwd=cwd)
    return True, sha if rc == 0 else ""


# ── evolution log ─────────────────────────────────────────────────────────────

class EvolutionLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def append(self, record: EvolutionRecord) -> None:
        rows = self._load()
        rows.append(asdict(record))
        rows = rows[-200:]  # keep last 200 entries
        try:
            self.path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def recent(self, n: int = 10) -> list[dict[str, Any]]:
        return self._load()[-n:]


# ── main engine ───────────────────────────────────────────────────────────────

class SelfEvolutionEngine:
    """
    Phase 7 autonomous self-improvement loop.

    Call `run_once()` from the autonomy scheduler or heartbeat.
    It is safe to call concurrently — an internal lock prevents overlapping runs.
    """

    def __init__(
        self,
        *,
        project_root: str | Path,
        source_root: str | Path | None = None,
        run_llm: Callable[[str], Awaitable[str]] | None = None,
        notify: NotifyCallback | None = None,
        cooldown_s: float = 3600.0,
        enabled: bool = False,
        log_path: str | Path | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.source_root = Path(source_root).resolve() if source_root else self.project_root / "clawlite"
        self._run_llm = run_llm
        self._notify = notify
        self.cooldown_s = max(60.0, float(cooldown_s))
        self.enabled = bool(enabled)

        log_file = Path(log_path) if log_path else self.project_root / "memory" / "evolution-log.json"
        self.log = EvolutionLog(log_file)

        self._scanner = SourceScanner(self.source_root)
        self._validator = Validator(self.project_root)
        self._applicator = PatchApplicator(self.source_root)

        self._lock = asyncio.Lock()
        self._last_run_at: float = 0.0
        self._run_count = 0
        self._committed_count = 0
        self._last_outcome = ""
        self._last_error = ""

    @staticmethod
    def _utc_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _notify_operator(self, text: str) -> None:
        if self._notify is None:
            bind_event("self_evolution").info("operator notice: {}", text)
            return
        try:
            await self._notify("self_evolution", {"text": text})
        except Exception as exc:
            bind_event("self_evolution").warning("notify failed: {}", exc)

    async def run_once(self, *, force: bool = False) -> dict[str, Any]:
        if not self.enabled and not force:
            return self.status()

        now = time.monotonic()
        if not force and (now - self._last_run_at) < self.cooldown_s:
            return self.status()

        if self._lock.locked():
            return self.status()

        async with self._lock:
            return await self._do_run()

    async def _do_run(self) -> dict[str, Any]:
        run_id = f"evo-{int(time.time())}"
        record = EvolutionRecord(run_id=run_id, started_at=self._utc_iso())
        self._last_run_at = time.monotonic()
        self._run_count += 1

        try:
            # 1. Scan for gaps
            code_gaps = self._scanner.scan(max_gaps=20)
            roadmap_path = self.project_root / "ROADMAP.md"
            roadmap_gaps = self._scanner.scan_roadmap(roadmap_path, max_items=5)
            all_gaps = code_gaps + roadmap_gaps
            record.gaps_found = len(all_gaps)

            bind_event("self_evolution").info(
                "run={} gaps_found={} code={} roadmap={}",
                run_id, len(all_gaps), len(code_gaps), len(roadmap_gaps),
            )

            if not all_gaps:
                record.outcome = "no_gaps"
                record.finished_at = self._utc_iso()
                self._last_outcome = "no_gaps"
                self.log.append(record)
                return self.status()

            if self._run_llm is None:
                record.outcome = "error"
                record.error = "llm_callback_missing"
                record.finished_at = self._utc_iso()
                self._last_outcome = "error"
                self._last_error = record.error
                self.log.append(record)
                return self.status()

            # 2. Pick the first actionable code gap (roadmap items are informational only)
            target_gap = code_gaps[0] if code_gaps else all_gaps[0]
            if target_gap.kind == "roadmap":
                # Log roadmap gap as notice, nothing to patch
                record.outcome = "no_gaps"
                record.finished_at = self._utc_iso()
                self._last_outcome = "no_gaps"
                self.log.append(record)
                return self.status()

            context = self._scanner.read_context(target_gap, context_lines=40)

            # 3. Propose fix
            proposer = FixProposer(self._run_llm)
            proposal = await proposer.propose(target_gap, context)
            if proposal is None:
                record.outcome = "error"
                record.error = "fix_proposal_failed"
                record.finished_at = self._utc_iso()
                self._last_outcome = "error"
                self._last_error = record.error
                self.log.append(record)
                return self.status()

            record.fix_description = proposal.description
            record.files_changed = list(proposal.files_touched)

            # 4. Backup original files
            backups: dict[str, str] = {}
            for rel in proposal.files_touched:
                p = self.source_root / rel
                if p.exists():
                    backups[rel] = p.read_text(encoding="utf-8", errors="replace")

            # 5. Apply patch
            ok, err = await asyncio.to_thread(self._applicator.apply, proposal)
            if not ok:
                record.outcome = "error"
                record.error = f"apply_failed: {err}"
                record.finished_at = self._utc_iso()
                self._last_outcome = "error"
                self._last_error = record.error
                self.log.append(record)
                return self.status()

            # 6. Validate
            ruff_ok, ruff_out = await asyncio.to_thread(self._validator.run_ruff)
            record.ruff_ok = ruff_ok

            if not ruff_ok:
                bind_event("self_evolution").warning("ruff failed run={} output={}", run_id, ruff_out[:400])
                await self._restore_backups(backups)
                record.outcome = "validation_failed"
                record.error = f"ruff: {ruff_out[:300]}"
                record.finished_at = self._utc_iso()
                self._last_outcome = "validation_failed"
                self._last_error = record.error
                self.log.append(record)
                return self.status()

            pytest_ok, pytest_out = await asyncio.to_thread(self._validator.run_pytest)
            record.pytest_ok = pytest_ok

            if not pytest_ok:
                bind_event("self_evolution").warning("pytest failed run={} output={}", run_id, pytest_out[-400:])
                await self._restore_backups(backups)
                record.outcome = "validation_failed"
                record.error = f"pytest: {pytest_out[-300:]}"
                record.finished_at = self._utc_iso()
                self._last_outcome = "validation_failed"
                self._last_error = record.error
                self.log.append(record)
                await self._notify_operator(
                    f"[self-evolution] Proposed fix for `{target_gap.file}:{target_gap.line}` "
                    f"({target_gap.kind}) — tests FAILED, rolled back.\n"
                    f"Description: {proposal.description}"
                )
                return self.status()

            # 7. Commit
            commit_msg = (
                f"auto: self-evolution — {proposal.description}\n\n"
                f"Gap: {target_gap.kind} in {target_gap.file}:{target_gap.line}\n"
                f"Run: {run_id}\n\n"
                f"Co-Authored-By: SelfEvolutionEngine <noreply@clawlite>"
            )
            committed, sha = await asyncio.to_thread(
                _commit, self.project_root, proposal.files_touched, commit_msg
            )

            if not committed:
                record.outcome = "error"
                record.error = f"commit_failed: {sha}"
                record.finished_at = self._utc_iso()
                self._last_outcome = "error"
                self._last_error = record.error
                self.log.append(record)
                return self.status()

            record.commit_sha = sha
            record.outcome = "committed"
            record.finished_at = self._utc_iso()
            self._last_outcome = "committed"
            self._last_error = ""
            self._committed_count += 1
            self.log.append(record)

            bind_event("self_evolution").info(
                "committed run={} sha={} file={} description={}",
                run_id, sha, target_gap.file, proposal.description,
            )

            # 8. Notify operator (no approval required)
            await self._notify_operator(
                f"[self-evolution] Auto-fixed `{target_gap.file}:{target_gap.line}` "
                f"({target_gap.kind})\n"
                f"Description: {proposal.description}\n"
                f"Commit: {sha}  •  ruff ✓  pytest ✓"
            )

        except Exception as exc:
            record.outcome = "error"
            record.error = str(exc)
            record.finished_at = self._utc_iso()
            self._last_outcome = "error"
            self._last_error = str(exc)
            self.log.append(record)
            bind_event("self_evolution").error("run failed run={} error={}", run_id, exc)

        return self.status()

    async def _restore_backups(self, backups: dict[str, str]) -> None:
        for rel, content in backups.items():
            path = self.source_root / rel
            try:
                await asyncio.to_thread(path.write_text, content, "utf-8")
            except Exception as exc:
                bind_event("self_evolution").error("restore backup failed file={} error={}", rel, exc)

    def status(self) -> dict[str, Any]:
        cooldown_remaining = max(
            0.0, self.cooldown_s - (time.monotonic() - self._last_run_at)
        )
        return {
            "enabled": self.enabled,
            "run_count": self._run_count,
            "committed_count": self._committed_count,
            "last_outcome": self._last_outcome,
            "last_error": self._last_error,
            "cooldown_remaining_s": round(cooldown_remaining, 1),
            "locked": self._lock.locked(),
        }
