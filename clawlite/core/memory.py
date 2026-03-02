from __future__ import annotations

import json
import hashlib
import re
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    from rank_bm25 import BM25Okapi
except Exception:  # pragma: no cover
    BM25Okapi = None

WORD_RE = re.compile(r"[a-zA-Z0-9_]+")
TRIVIAL_RE = re.compile(
    r"^(ok|okay|kk|thanks|thank you|got it|noted|done|cool|yes|no|right|understood|perfeito|blz)[.!?]*$",
    re.IGNORECASE,
)
CURATION_HINT_RE = re.compile(
    r"\b(remember|memory|prefer|preference|timezone|time zone|name|project|deadline|important|always|never|avoid|do not|don't|cannot|can't|must|language|stack)\b",
    re.IGNORECASE,
)

try:
    import fcntl
except Exception:  # pragma: no cover - platform fallback
    fcntl = None


@dataclass(slots=True)
class MemoryRecord:
    id: str
    text: str
    source: str
    created_at: str


class MemoryStore:
    """Durable two-layer memory with optional history/curated split."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        history_path: str | Path | None = None,
        curated_path: str | Path | None = None,
        checkpoints_path: str | Path | None = None,
        split_layers: bool = True,
    ) -> None:
        base_history = Path(history_path) if history_path else (Path(db_path) if db_path else (Path.home() / ".clawlite" / "state" / "memory.jsonl"))
        self.path = base_history  # Backward-compatible alias.
        self.history_path = base_history

        if curated_path:
            self.curated_path = Path(curated_path)
        elif split_layers:
            self.curated_path = self.history_path.with_name("memory_curated.json")
        else:
            self.curated_path = None

        if checkpoints_path:
            self.checkpoints_path = Path(checkpoints_path)
        else:
            self.checkpoints_path = self.history_path.with_name("memory_checkpoints.json")

        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file(self.history_path, default="")
        if self.curated_path is not None:
            self.curated_path.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_file(self.curated_path, default='{"facts": []}\n')
        self.checkpoints_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file(self.checkpoints_path, default="{}\n")

    @staticmethod
    def _ensure_file(path: Path, *, default: str) -> None:
        if path.exists():
            return
        path.write_text(default, encoding="utf-8")

    @contextmanager
    def _locked_file(self, path: Path, mode: str, *, exclusive: bool):
        with path.open(mode, encoding="utf-8") as fh:
            if fcntl is not None:
                lock_mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                fcntl.flock(fh.fileno(), lock_mode)
            try:
                yield fh
            finally:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _normalize_memory_text(text: str) -> str:
        return " ".join(WORD_RE.findall(text.lower()))

    @staticmethod
    def _is_trivial_message(text: str) -> bool:
        compact = " ".join(str(text or "").split())
        if not compact:
            return True
        if len(compact) <= 4:
            return True
        return bool(TRIVIAL_RE.match(compact))

    @staticmethod
    def _is_curation_candidate(role: str, content: str) -> bool:
        clean_role = str(role or "").strip().lower()
        clean_content = " ".join(str(content or "").split())
        if not clean_content or MemoryStore._is_trivial_message(clean_content):
            return False
        if CURATION_HINT_RE.search(clean_content):
            return True
        if clean_role == "user" and len(clean_content) >= 96:
            return True
        return False

    @staticmethod
    def _chunk_signature(lines: list[str]) -> str:
        raw = "\n".join(lines).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _parse_checkpoints(raw: str) -> dict[str, str]:
        payload_raw = raw.strip()
        if not payload_raw:
            return {}
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(payload, dict):
            return {}
        return {str(k): str(v) for k, v in payload.items()}

    def _read_curated_facts(self) -> list[dict[str, str]]:
        if self.curated_path is None:
            return []
        with self._locked_file(self.curated_path, "r", exclusive=False) as fh:
            raw = fh.read().strip()
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, dict):
            return []
        facts = payload.get("facts", [])
        if not isinstance(facts, list):
            return []
        out: list[dict[str, str]] = []
        for row in facts:
            if not isinstance(row, dict):
                continue
            text = str(row.get("text", "")).strip()
            if not text:
                continue
            out.append(
                {
                    "id": str(row.get("id", "") or uuid.uuid4().hex),
                    "text": text,
                    "source": str(row.get("source", "curated") or "curated"),
                    "created_at": str(row.get("created_at", "") or datetime.now(timezone.utc).isoformat()),
                }
            )
        return out

    def _write_curated_facts(self, facts: list[dict[str, str]]) -> None:
        if self.curated_path is None:
            return
        payload = {"facts": facts[-250:]}
        encoded = json.dumps(payload, ensure_ascii=False, indent=2)
        with self._locked_file(self.curated_path, "w", exclusive=True) as fh:
            fh.write(encoded)
            fh.write("\n")
            fh.flush()

    def _curate_candidates(self, candidates: list[str], *, source: str) -> None:
        if self.curated_path is None or not candidates:
            return
        current = self._read_curated_facts()
        by_norm = {self._normalize_memory_text(item["text"]): item for item in current}
        now_iso = datetime.now(timezone.utc).isoformat()
        changed = False
        for candidate in candidates:
            norm = self._normalize_memory_text(candidate)
            if not norm:
                continue
            if norm in by_norm:
                continue
            row = {
                "id": uuid.uuid4().hex,
                "text": candidate,
                "source": f"curated:{source}",
                "created_at": now_iso,
            }
            current.append(row)
            by_norm[norm] = row
            changed = True
        if changed:
            self._write_curated_facts(current)

    def _extract_consolidation_lines(self, messages: Iterable[dict[str, str]]) -> list[str]:
        lines: list[str] = []
        for msg in messages:
            role = str(msg.get("role", "")).strip().lower()
            content = " ".join(str(msg.get("content", "")).split())
            if role not in {"user", "assistant"}:
                continue
            if not self._is_curation_candidate(role, content):
                continue
            lines.append(f"{role}: {content}")
        return lines

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [m.group(0).lower() for m in WORD_RE.finditer(text)]

    def add(self, text: str, *, source: str = "user") -> MemoryRecord:
        clean = text.strip()
        if not clean:
            raise ValueError("memory text must not be empty")
        row = MemoryRecord(
            id=uuid.uuid4().hex,
            text=clean,
            source=source,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._locked_file(self.history_path, "a", exclusive=True) as fh:
            fh.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
            fh.flush()
        return row

    def all(self) -> list[MemoryRecord]:
        out: list[MemoryRecord] = []
        with self._locked_file(self.history_path, "r", exclusive=False) as fh:
            lines = fh.read().splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            out.append(
                MemoryRecord(
                    id=str(payload.get("id", "")),
                    text=str(payload.get("text", "")).strip(),
                    source=str(payload.get("source", "unknown")),
                    created_at=str(payload.get("created_at", "")),
                )
            )
        return [item for item in out if item.text]

    def curated(self) -> list[MemoryRecord]:
        rows = self._read_curated_facts()
        return [
            MemoryRecord(
                id=str(item.get("id", "")),
                text=str(item.get("text", "")).strip(),
                source=str(item.get("source", "curated")),
                created_at=str(item.get("created_at", "")),
            )
            for item in rows
            if str(item.get("text", "")).strip()
        ]

    def search(self, query: str, *, limit: int = 5) -> list[MemoryRecord]:
        records = self.curated() + self.all()
        if not records:
            return []

        q_tokens = self._tokens(query)
        if not q_tokens:
            return records[-limit:][::-1]

        corpus_tokens = [self._tokens(item.text) for item in records]
        qset = set(q_tokens)

        bm25_scores: list[float]
        if BM25Okapi is None:
            bm25_scores = [0.0 for _ in records]
        else:
            bm25 = BM25Okapi(corpus_tokens)
            scores = bm25.get_scores(q_tokens)
            bm25_scores = [float(scores[idx]) for idx in range(len(records))]

        # Primary key: lexical overlap with query terms.
        # Secondary key: BM25 score for ordering among matching records.
        scored: list[tuple[float, float, int]] = []
        for idx, toks in enumerate(corpus_tokens):
            overlap = len(qset.intersection(toks))
            curated_boost = 0.75 if records[idx].source.startswith("curated:") else 0.0
            scored.append((float(overlap) + curated_boost, bm25_scores[idx], idx))

        scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)

        picked: list[MemoryRecord] = []
        for overlap_score, bm25_score, idx in scored:
            if len(picked) >= limit:
                break
            if overlap_score <= 0 and bm25_score <= 0.0:
                continue
            picked.append(records[idx])

        return picked if picked else records[-limit:][::-1]

    def consolidate(self, messages: Iterable[dict[str, str]], *, source: str = "session") -> MemoryRecord | None:
        lines = self._extract_consolidation_lines(messages)
        if not lines:
            return None

        summary_lines = lines[-6:]
        signature = self._chunk_signature(summary_lines)

        with self._locked_file(self.checkpoints_path, "r+", exclusive=True) as checkpoints_fh:
            checkpoints = self._parse_checkpoints(checkpoints_fh.read())
            if checkpoints.get(source) == signature:
                return None

            summary = "\n".join(summary_lines)
            row = self.add(summary, source=source)

            checkpoints[source] = signature
            checkpoints_fh.seek(0)
            checkpoints_fh.truncate()
            checkpoints_fh.write(json.dumps(checkpoints, ensure_ascii=False, sort_keys=True))
            checkpoints_fh.write("\n")
            checkpoints_fh.flush()

        curated_candidates = [line.split(":", 1)[1].strip() for line in summary_lines if ":" in line]
        self._curate_candidates(curated_candidates, source=source)
        return row


# Backward-compatible API expected by legacy CLI.
def add_note(text: str) -> None:
    MemoryStore().add(text, source="legacy")


def search_notes(query: str, limit: int = 10) -> list[str]:
    return [row.text for row in MemoryStore().search(query, limit=limit)]
