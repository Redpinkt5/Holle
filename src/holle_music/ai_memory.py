"""Persistent memory for the Holle Music AI assistant.

Provides short-term (in-session) and long-term (JSON file) memory with
keyword-based retrieval. Relevant context is injected into LLM prompts so the
assistant can remember user preferences, recent conversations and important
events across sessions.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class MemoryKind(str, Enum):
    """Category of a memory entry."""

    CONVERSATION = "conversation"
    OBSERVATION = "observation"
    DECISION = "decision"
    PREFERENCE = "preference"


@dataclass
class MemoryEntry:
    """A single memory entry."""

    id: str
    timestamp: float
    kind: MemoryKind
    content: str
    importance: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            timestamp=data.get("timestamp", datetime.now().timestamp()),
            kind=MemoryKind(data.get("kind", "observation")),
            content=data.get("content", ""),
            importance=data.get("importance", 0.5),
            metadata=data.get("metadata", {}) or {},
        )


class LongTermMemory:
    """Persistent long-term memory backed by a JSON file."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.entries: list[MemoryEntry] = []
        self._load()

    def _load(self) -> None:
        if not self.file_path.exists():
            return
        try:
            raw = self.file_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            self.entries = [MemoryEntry.from_dict(e) for e in data]
        except Exception:
            self.entries = []

    def save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(
            json.dumps(
                [e.to_dict() for e in self.entries],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def insert(self, entry: MemoryEntry) -> None:
        self.entries.append(entry)
        self.save()

    def retrieve(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Return the most relevant long-term memories for a query."""
        now = datetime.now().timestamp()
        week_secs = 7 * 24 * 3600
        query_lower = query.lower()
        scored: list[tuple[MemoryEntry, float]] = []
        for entry in self.entries:
            if entry.importance <= 0.0:
                continue
            score = entry.importance
            if query_lower and query_lower in entry.content.lower():
                score += 0.3
            age = now - entry.timestamp
            if age < week_secs:
                score += (1.0 - age / week_secs) * 0.2
            scored.append((entry, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [entry for entry, _ in scored[:limit]]

    def prune(self, max_age_days: int = 30, min_importance: float = 0.2) -> None:
        """Drop old, unimportant entries."""
        cutoff = datetime.now().timestamp() - max_age_days * 24 * 3600
        self.entries = [
            e
            for e in self.entries
            if not (e.importance < min_importance and e.timestamp < cutoff)
        ]
        self.save()

    def all(self) -> list[MemoryEntry]:
        return list(self.entries)


class ShortTermMemory:
    """In-memory short-term memory with count + age eviction."""

    def __init__(self, max_entries: int = 50, max_age_secs: float = 7200) -> None:
        self.entries: list[MemoryEntry] = []
        self.max_entries = max_entries
        self.max_age_secs = max_age_secs

    def push(self, entry: MemoryEntry) -> None:
        self.entries.append(entry)
        self._evict()

    def _evict(self) -> None:
        now = datetime.now().timestamp()
        cutoff = now - self.max_age_secs
        self.entries = [e for e in self.entries if e.timestamp >= cutoff]
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

    def recent(self, n: int = 10) -> list[MemoryEntry]:
        return self.entries[-n:]


class MemoryManager:
    """Unified memory manager: STM + LTM + prompt context builder."""

    DEFAULT_PATH = Path.home() / ".holle_music" / "ai_memory.json"

    def __init__(self, file_path: Path | None = None) -> None:
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(file_path or self.DEFAULT_PATH)

    def record(
        self,
        kind: MemoryKind,
        content: str,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Record an event. Important entries are auto-promoted to long-term."""
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().timestamp(),
            kind=kind,
            content=content,
            importance=importance,
            metadata=metadata or {},
        )
        self.short_term.push(entry)
        if importance >= 0.5 or kind == MemoryKind.PREFERENCE:
            self.long_term.insert(entry)
        return entry

    def build_context(self, query: str = "") -> str:
        """Build a memory-context block suitable for prompt injection."""
        parts: list[str] = []
        recent = self.short_term.recent(10)

        conversations = [e for e in recent if e.kind == MemoryKind.CONVERSATION]
        if conversations:
            parts.append("最近对话：")
            parts.extend(f"- {e.content}" for e in conversations)

        other = [e for e in recent if e.kind != MemoryKind.CONVERSATION]
        if other:
            parts.append("\n最近事件：")
            parts.extend(f"- [{e.kind.value}] {e.content}" for e in other)

        relevant = self.long_term.retrieve(query, limit=5)
        if relevant:
            parts.append("\n相关长期记忆：")
            parts.extend(
                f"- {e.content} (重要性: {e.importance:.1f})" for e in relevant
            )

        if not parts:
            return ""
        return "[记忆上下文]\n" + "\n".join(parts) + "\n[/记忆上下文]"

    def get_memories(
        self,
        kind: MemoryKind | None = None,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        all_entries = list(self.short_term.recent(limit)) + self.long_term.all()
        if kind:
            all_entries = [e for e in all_entries if e.kind == kind]
        all_entries.sort(key=lambda e: e.timestamp, reverse=True)
        return all_entries[:limit]

    def prune(self) -> None:
        """Clean up stale, low-importance long-term memories."""
        self.long_term.prune()
