"""Tests for holle_music.ai_memory."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from holle_music.ai_memory import (
    LongTermMemory,
    MemoryEntry,
    MemoryKind,
    MemoryManager,
    ShortTermMemory,
)


NOW = datetime.now().timestamp()


@pytest.fixture
def tmp_path(tmp_path_factory):
    return tmp_path_factory.mktemp("ai_memory")


def test_short_term_memory_eviction_by_count():
    stm = ShortTermMemory(max_entries=3, max_age_secs=3600)
    for i in range(5):
        stm.push(
            MemoryEntry(
                id=str(i),
                timestamp=NOW + i,
                kind=MemoryKind.OBSERVATION,
                content=f"event {i}",
            )
        )
    assert len(stm.recent(10)) == 3
    assert stm.recent(1)[0].content == "event 4"


def test_short_term_memory_eviction_by_age():
    stm = ShortTermMemory(max_entries=100, max_age_secs=100)
    stm.push(
        MemoryEntry(
            id="old",
            timestamp=NOW - 200,
            kind=MemoryKind.OBSERVATION,
            content="old event",
        )
    )
    stm.push(
        MemoryEntry(
            id="new",
            timestamp=NOW,
            kind=MemoryKind.OBSERVATION,
            content="new event",
        )
    )
    assert len(stm.recent(10)) == 1
    assert stm.recent(1)[0].content == "new event"


def test_long_term_memory_save_and_load(tmp_path):
    file_path = tmp_path / "ltm.json"
    ltm = LongTermMemory(file_path)
    entry = MemoryEntry(
        id="1",
        timestamp=1000.0,
        kind=MemoryKind.PREFERENCE,
        content="用户喜欢陈奕迅",
        importance=0.8,
    )
    ltm.insert(entry)

    ltm2 = LongTermMemory(file_path)
    assert len(ltm2.all()) == 1
    assert ltm2.all()[0].content == "用户喜欢陈奕迅"


def test_long_term_memory_retrieval_orders_by_relevance(tmp_path):
    file_path = tmp_path / "ltm.json"
    ltm = LongTermMemory(file_path)
    ltm.insert(
        MemoryEntry(
            id="1",
            timestamp=1000.0,
            kind=MemoryKind.PREFERENCE,
            content="用户喜欢陈奕迅",
            importance=0.8,
        )
    )
    ltm.insert(
        MemoryEntry(
            id="2",
            timestamp=1000.0,
            kind=MemoryKind.OBSERVATION,
            content="用户昨天听了周杰伦",
            importance=0.4,
        )
    )
    results = ltm.retrieve("陈奕迅", limit=5)
    assert len(results) == 2
    assert results[0].content == "用户喜欢陈奕迅"


def test_memory_manager_records_and_builds_context(tmp_path):
    file_path = tmp_path / "ai_memory.json"
    mgr = MemoryManager(file_path)
    mgr.record(MemoryKind.CONVERSATION, "用户: 播放陈奕迅的歌", importance=0.3)
    mgr.record(MemoryKind.PREFERENCE, "用户喜欢陈奕迅", importance=0.8)

    ctx = mgr.build_context("陈奕迅")
    assert "用户喜欢陈奕迅" in ctx
    assert "播放陈奕迅的歌" in ctx


def test_memory_manager_prune(tmp_path):
    file_path = tmp_path / "ai_memory.json"
    mgr = MemoryManager(file_path)
    entry = MemoryEntry(
        id="old",
        timestamp=NOW - 31 * 24 * 3600,
        kind=MemoryKind.OBSERVATION,
        content="old unimportant event",
        importance=0.1,
    )
    mgr.long_term.insert(entry)

    mgr.prune()
    assert len(mgr.long_term.all()) == 0
