# `/ai` Command and AI Provider Auto-Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/ai <apikey>` command to Holle Music TUI and Pet that auto-detects the AI provider, persists the configuration to `~/.holle_music/settings.json`, and makes TUI and Pet share the same AI key and provider.

**Architecture:** Introduce a single provider registry in `src/holle_music/ai_provider.py`. It exposes `detect_provider(api_key)` (endpoint probes with short timeout) and `create_ai_service(api_key, provider)` (factory returning the existing service classes plus a new generic `OpenAICompatibleService`). `app.py` adds the `/ai` command and initializes `_ai` from settings. `pet/main.py` reads the same settings and falls back to `ArkService()` when nothing is configured.

**Tech Stack:** Python 3.10+, `urllib`, `openai`, `pytest`, `monkeypatch`

---

## File Structure

| File | Responsibility |
|---|---|
| `src/holle_music/ai_provider.py` | **New.** Provider table, endpoint probe, detection logic, service factory, generic OpenAI-compatible chat service. |
| `src/holle_music/app.py` | Add `CommandType.AI`, `/ai` handler, AI service initialization from settings, guard when AI is not configured. |
| `src/holle_music/pet/main.py` | Load AI provider config on startup; use configured service, fall back to `ArkService()`. |
| `tests/test_ai_provider.py` | **New.** Unit tests for detection, factory, and `OpenAICompatibleService`. |
| `tests/test_commands.py` | Add parser test for `/ai`. |
| `memory/modules/project_ai_provider.md` | **New.** Module memory for the AI provider subsystem. |
| `memory/_index.md` | Add the new module row. |

---

## Task 1: Add the `/ai` command to the parser

**Files:**
- Modify: `src/holle_music/app.py:33-47` (CommandType enum)
- Modify: `src/holle_music/app.py:56-89` (COMMAND_MAP)
- Test: `tests/test_commands.py`

- [ ] **Step 1: Add `CommandType.AI` to the enum**

Add `AI = auto()` after `UNKNOWN = auto()`:

```python
class CommandType(Enum):
    NONE = auto()
    PLAY = auto()
    PAUSE = auto()
    STOP = auto()
    NEXT = auto()
    PREVIOUS = auto()
    VOLUME = auto()
    SCAN = auto()
    PLAYLIST = auto()
    HELP = auto()
    QUIT = auto()
    SEARCH = auto()
    COLOR = auto()
    AI = auto()
    UNKNOWN = auto()
```

- [ ] **Step 2: Add `/ai` to `COMMAND_MAP`**

Add the mapping at the end, before the closing brace:

```python
    "/ai": CommandType.AI,
    "ai": CommandType.AI,
```

- [ ] **Step 3: Add a parser test**

Append to `tests/test_commands.py` inside `TestCommandParser`:

```python
    def test_ai_command(self):
        cmd = parse_command("/ai sk-abc123")
        assert cmd.type == CommandType.AI
        assert cmd.args == "sk-abc123"

    def test_ai_command_without_args(self):
        cmd = parse_command("/ai")
        assert cmd.type == CommandType.AI
        assert cmd.args == ""
```

- [ ] **Step 4: Run the command parser tests**

Run:

```bash
PYTHONPATH=src python -m pytest tests/test_commands.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/holle_music/app.py tests/test_commands.py
git commit -m "feat(commands): add /ai command parser support"
```

---

## Task 2: Create the AI provider module

**Files:**
- Create: `src/holle_music/ai_provider.py`
- Test: `tests/test_ai_provider.py`

- [ ] **Step 1: Write `src/holle_music/ai_provider.py`**

Create the file with this content:

```python
"""AI provider registry, key detection, and unified service factory."""

from __future__ import annotations

from typing import Any, Callable


PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "test_endpoint": "https://api.openai.com/v1/models",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "test_endpoint": "https://api.deepseek.com/models",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "THUDM/GLM-Z1-9B-0414",
        "test_endpoint": "https://api.siliconflow.cn/v1/models",
    },
    "minimax": {
        "base_url": "https://api.minimaxi.com/v1",
        "model": "minimax-text-01",
        "test_endpoint": "https://api.minimaxi.com/v1/models",
    },
    "ark": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "deepseek-v4-flash-260425",
        "test_endpoint": None,
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "test_endpoint": "https://api.moonshot.cn/v1/models",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "test_endpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1/models",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "test_endpoint": "https://open.bigmodel.cn/api/paas/v4/models",
    },
}

_SYSTEM_PROMPT = """你是一个专业的音乐助手，运行在终端音乐播放器中。
你有联网搜索能力，会收到实时的搜索结果作为参考信息。
请优先根据搜索结果回答用户问题，特别是实时信息（日期、天气、新闻等）。
回答要简洁自然，不使用Markdown格式。
当前歌曲信息会附在问题前，可据此回答音乐相关问题。"""


def _ensure_openai() -> None:
    try:
        import openai  # noqa: F401
    except ImportError:
        import subprocess
        import sys

        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "openai>=1.0.0", "-q"]
        )


def _test_provider(config: dict[str, Any], api_key: str) -> bool:
    """Send a lightweight request to verify the key works for a provider."""
    import urllib.error
    import urllib.request

    endpoint = config.get("test_endpoint")
    if not endpoint:
        return False

    req = urllib.request.Request(
        endpoint,
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def detect_provider(api_key: str) -> str | None:
    """Detect provider from key prefix and endpoint probes.

    Returns one of the keys in PROVIDERS, or None if no provider matches.
    """
    if not api_key:
        return None

    # Generic sk- keys are common across OpenAI-compatible providers.
    # Probe providers in priority order.
    priority = [
        "deepseek",
        "openai",
        "siliconflow",
        "kimi",
        "qwen",
        "zhipu",
        "minimax",
    ]
    for name in priority:
        if _test_provider(PROVIDERS[name], api_key):
            return name

    # Ark keys typically don't start with sk-; probe last.
    if _test_provider(PROVIDERS["ark"], api_key):
        return "ark"

    return None


def create_ai_service(api_key: str, provider: str):
    """Create an AI service instance for the given provider."""
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown AI provider: {provider}")

    config = PROVIDERS[provider]

    if provider == "minimax":
        from holle_music.minimax_api import MiniMaxService

        return MiniMaxService(
            api_key=api_key,
            base_url=config["base_url"],
            model=config["model"],
        )

    if provider == "ark":
        from holle_music.pet.ark_api import ArkService

        return ArkService(
            api_key=api_key,
            base_url=config["base_url"],
            model=config["model"],
        )

    if provider == "deepseek":
        from holle_music.pet.deepseek_api import DeepSeekService

        return DeepSeekService(
            api_key=api_key,
            base_url=config["base_url"],
            model=config["model"],
        )

    # Generic OpenAI-compatible providers: OpenAI, SiliconFlow, Kimi, Qwen, Zhipu.
    return OpenAICompatibleService(
        api_key=api_key,
        base_url=config["base_url"],
        model=config["model"],
    )


class OpenAICompatibleService:
    """Generic OpenAI-compatible chat service.

    Supports chat with context memory, one-shot queries, and web search.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._client = None
        self._chat_history: list[dict] = []
        self._max_history = 10
        self._last_request_time: float = 0.0
        self._min_interval: float = 1.0

    @property
    def client(self):
        if self._client is None:
            _ensure_openai()
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _wait_rate_limit(self) -> None:
        import time

        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

    def _retry(self, fn, max_retries: int = 3):
        import time

        self._wait_rate_limit()
        last_error = None
        for attempt in range(max_retries):
            try:
                result = fn()
                self._last_request_time = time.time()
                return result
            except Exception as exc:
                last_error = exc
                err = str(exc).lower()
                if any(kw in err for kw in ("401", "unauthorized", "invalid", "auth")):
                    raise
                if "429" in err or "rate" in err:
                    time.sleep(5 * (2 ** attempt))
                    continue
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        self._last_request_time = time.time()
        raise last_error

    def chat(
        self,
        message: str,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        if not self._chat_history:
            self._chat_history.append({"role": "system", "content": _SYSTEM_PROMPT})

        self._chat_history.append({"role": "user", "content": message})

        while len(self._chat_history) > self._max_history * 2 + 1:
            for i, m in enumerate(self._chat_history):
                if m["role"] != "system":
                    del self._chat_history[i]
                    break

        def _call():
            if on_token:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=self._chat_history,
                    max_tokens=1024,
                    temperature=0.7,
                    timeout=60,
                    stream=True,
                )
                full = ""
                for chunk in resp:
                    if not chunk.choices:
                        continue
                    delta = getattr(chunk.choices[0].delta, "content", None)
                    if delta:
                        full += delta
                        on_token(delta)
                self._chat_history.append({"role": "assistant", "content": full})
                return full

            resp = self.client.chat.completions.create(
                model=self.model,
                messages=self._chat_history,
                max_tokens=1024,
                temperature=0.7,
                timeout=60,
            )
            content = resp.choices[0].message.content or "" if resp.choices else ""
            self._chat_history.append({"role": "assistant", "content": content})
            return content

        return self._retry(_call)

    def query_once(
        self,
        prompt: str,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """One-shot query without touching chat history."""
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        def _call():
            if on_token:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=512,
                    temperature=0.7,
                    timeout=60,
                    stream=True,
                )
                full = ""
                for chunk in resp:
                    delta = getattr(chunk.choices[0].delta, "content", None)
                    if delta:
                        full += delta
                        on_token(delta)
                return full

            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=512,
                temperature=0.7,
                timeout=60,
            )
            return resp.choices[0].message.content or ""

        return self._retry(_call)

    @staticmethod
    def search_web(query: str) -> str:
        """Search the web and return formatted results."""
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=5):
                    title = r.get("title", "")
                    body = r.get("body", "")
                    if title and body:
                        results.append(f"- {title}: {body}")
            return "\n".join(results) if results else ""
        except Exception:
            return ""

    def clear_history(self) -> None:
        self._chat_history.clear()

    @property
    def history(self) -> list[dict]:
        return list(self._chat_history)
```

- [ ] **Step 2: Create `tests/test_ai_provider.py`**

```python
"""Tests for holle_music.ai_provider."""

from __future__ import annotations

import pytest

from holle_music import ai_provider
from holle_music.ai_provider import (
    OpenAICompatibleService,
    PROVIDERS,
    create_ai_service,
    detect_provider,
)


@pytest.fixture
def no_network(monkeypatch):
    """Prevent real network calls in provider detection tests."""
    monkeypatch.setattr(ai_provider, "_test_provider", lambda config, key: False)


def test_providers_table_has_required_fields():
    for name, config in PROVIDERS.items():
        assert "base_url" in config, name
        assert "model" in config, name
        assert "test_endpoint" in config, name


def test_detect_provider_empty_returns_none(no_network):
    assert detect_provider("") is None
    assert detect_provider("   ") is None


def test_detect_provider_invalid_returns_none(no_network):
    assert detect_provider("not-a-real-key") is None


def test_detect_provider_priority_order(monkeypatch):
    """When multiple providers respond, priority order wins."""
    called = []

    def _fake_test(config, key):
        called.append(config["test_endpoint"])
        # Make every provider succeed.
        return True

    monkeypatch.setattr(ai_provider, "_test_provider", _fake_test)
    result = detect_provider("sk-abc")
    # DeepSeek is first in priority.
    assert result == "deepseek"
    assert called[0] == PROVIDERS["deepseek"]["test_endpoint"]


def test_detect_provider_ark_probed_last(monkeypatch):
    """Ark is probed only after all other providers fail."""
    called = []

    def _fake_test(config, key):
        called.append(config.get("test_endpoint"))
        return config.get("test_endpoint") == PROVIDERS["ark"]["test_endpoint"]

    monkeypatch.setattr(ai_provider, "_test_provider", _fake_test)
    result = detect_provider("ark-key")
    assert result == "ark"
    assert called[-1] == PROVIDERS["ark"]["test_endpoint"]


def test_create_ai_service_unknown_provider_raises():
    with pytest.raises(ValueError):
        create_ai_service("sk-abc", "not-a-provider")


def test_create_ai_service_minimax():
    service = create_ai_service("sk-abc", "minimax")
    from holle_music.minimax_api import MiniMaxService

    assert isinstance(service, MiniMaxService)
    assert service.api_key == "sk-abc"
    assert service.base_url == PROVIDERS["minimax"]["base_url"]
    assert service.model == PROVIDERS["minimax"]["model"]


def test_create_ai_service_ark():
    service = create_ai_service("ark-key", "ark")
    from holle_music.pet.ark_api import ArkService

    assert isinstance(service, ArkService)
    assert service.api_key == "ark-key"
    assert service.base_url == PROVIDERS["ark"]["base_url"]
    assert service.model == PROVIDERS["ark"]["model"]


def test_create_ai_service_deepseek():
    service = create_ai_service("sk-abc", "deepseek")
    from holle_music.pet.deepseek_api import DeepSeekService

    assert isinstance(service, DeepSeekService)
    assert service.api_key == "sk-abc"
    assert service.base_url == PROVIDERS["deepseek"]["base_url"]
    assert service.model == PROVIDERS["deepseek"]["model"]


@pytest.mark.parametrize("provider", ["openai", "siliconflow", "kimi", "qwen", "zhipu"])
def test_create_ai_service_openai_compatible(provider):
    service = create_ai_service("sk-abc", provider)
    assert isinstance(service, OpenAICompatibleService)
    assert service.api_key == "sk-abc"
    assert service.base_url == PROVIDERS[provider]["base_url"]
    assert service.model == PROVIDERS[provider]["model"]


def test_openai_compatible_service_uses_custom_config(monkeypatch):
    captured = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    # Patch the OpenAI class imported inside the property.
    import sys

    monkeypatch.setattr(sys.modules["openai"], "OpenAI", FakeOpenAI)

    service = OpenAICompatibleService(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="my-model",
    )
    _ = service.client
    assert captured["api_key"] == "sk-test"
    assert captured["base_url"] == "https://example.com/v1"
```

- [ ] **Step 3: Run the new tests**

Run:

```bash
PYTHONPATH=src python -m pytest tests/test_ai_provider.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/holle_music/ai_provider.py tests/test_ai_provider.py
git commit -m "feat(ai): add provider registry, detection, and OpenAI-compatible service"
```

---

## Task 3: Wire `/ai` into the TUI app

**Files:**
- Modify: `src/holle_music/app.py:341-352` (`__init__`)
- Modify: `src/holle_music/app.py:881-914` (`_chat_with_ai`)
- Modify: `src/holle_music/app.py:916-1000` (`_handle_command`)
- Modify: `src/holle_music/app.py:658-673` (`_query_song_background`)
- Modify: `src/holle_music/app.py:956-968` (`/help` text)

- [ ] **Step 1: Initialize AI service from settings**

Replace:

```python
        self._ai = MiniMaxService()
```

with:

```python
        self._ai = self._init_ai_service()
```

Then add the helper method right after `__init__`:

```python
    def _init_ai_service(self):
        """Initialize AI service from saved settings, or None if not configured."""
        from holle_music.ai_provider import create_ai_service

        settings = load_settings()
        provider = settings.get("ai_provider")
        api_key = settings.get("ai_api_key")
        if provider and api_key:
            try:
                return create_ai_service(api_key, provider)
            except Exception:
                return None
        return None
```

Remove the now-unused import:

```python
from holle_music.minimax_api import MiniMaxService
```

- [ ] **Step 2: Guard chat when AI is not configured**

At the top of `_chat_with_ai`, add:

```python
    def _chat_with_ai(self, text: str) -> None:
        """Send user message to AI with web search results."""
        chat = self.query_one("#chat-bubbles", ChatBubbles)
        chat.add_user_msg(text)
        chat.set_pending()

        if self._ai is None:
            chat.add_ai_msg("请先使用 /ai <你的 API Key> 配置 AI")
            return

        def _run():
            ...
```

- [ ] **Step 3: Handle `/ai` command**

Add a new branch in `_handle_command` before the `UNKNOWN` branch:

```python
        elif cmd.type == CommandType.AI:
            key = (cmd.args or "").strip()
            if not key:
                self._notify_chat("用法: /ai <你的 API Key>")
            else:
                from holle_music.ai_provider import PROVIDERS, detect_provider, create_ai_service
                provider = detect_provider(key)
                if not provider:
                    self._notify_chat("无法识别该 API Key 对应的供应商，请检查 key 是否正确")
                else:
                    config = PROVIDERS[provider]
                    set_setting("ai_provider", provider)
                    set_setting("ai_api_key", key)
                    set_setting("ai_base_url", config["base_url"])
                    set_setting("ai_model", config["model"])
                    try:
                        self._ai = create_ai_service(key, provider)
                        self._notify_chat(f"AI 已配置为: {provider}")
                    except Exception as e:
                        self._notify_chat(f"AI 初始化失败: {e}")
```

- [ ] **Step 4: Guard background song query when AI is not configured**

In `_query_song_background`, wrap the thread work:

```python
    def _query_song_background(self, song: Song) -> None:
        if self._ai is None:
            return

        prompt = (
            ...
```

- [ ] **Step 5: Update `/help` text**

Add `/ai <apikey>` to the help message:

```python
            chat.add_ai_msg(
                "/play  播放 | /pause  暂停\n"
                "/next  下一曲 | /prev  上一曲\n"
                "/volume <音量>  设置音量\n"
                "/scan [文件路径]  扫描音乐文件夹\n"
                "/search <关键词>  搜索歌曲\n"
                "/color <颜色>  选择闪烁颜色\n"
                "/ai <API Key>  配置 AI\n"
                "顺序⭢ 单曲⟳ 随机↬ | 空格 暂停\n"
                "/quit  退出"
            )
```

- [ ] **Step 6: Run the app import test**

Run:

```bash
PYTHONPATH=src python -c "from holle_music.app import HolleMusicApp; print('OK')"
```

Expected: prints `OK` with no errors.

- [ ] **Step 7: Commit**

```bash
git add src/holle_music/app.py
git commit -m "feat(tui): integrate /ai command and settings-based AI service"
```

---

## Task 4: Make Pet read the same AI configuration

**Files:**
- Modify: `src/holle_music/pet/main.py:12-18` (imports)
- Modify: `src/holle_music/pet/main.py:38-42` (AI initialization)
- Modify: `src/holle_music/pet/main.py:225-264` (AI chat loop)

- [ ] **Step 1: Import the AI provider helpers**

Add to the imports:

```python
from holle_music.ai_provider import create_ai_service, detect_provider, PROVIDERS
```

Keep the existing `ArkService` import because it is still used as the fallback.

- [ ] **Step 2: Initialize Pet AI from settings**

Replace:

```python
    player = PetPlayer()
    ai = ArkService()
    tools = AITools(player)
```

with:

```python
    player = PetPlayer()
    tools = AITools(player)

    settings = load_settings()
    provider = settings.get("ai_provider")
    api_key = settings.get("ai_api_key")
    ai = None
    if provider and api_key:
        try:
            ai = create_ai_service(api_key, provider)
        except Exception:
            ai = None
    if ai is None:
        ai = ArkService()
```

- [ ] **Step 3: Normalize chat responses in Pet**

Inside `on_chat_send`, replace the inner `ai_worker` chat loop:

```python
                reply = None
                try:
                    if hasattr(ai, "submit_tool_results"):
                        current = ai.chat(message)
                        for _ in range(5):
                            if current["type"] == "tool_calls":
                                tool_results = []
                                for call in current["calls"]:
                                    tool_result = tools.execute(call["name"], call["arguments"])
                                    tool_results.append((call["id"], tool_result))
                                current = ai.submit_tool_results(tool_results)
                            elif current.get("content"):
                                reply = current["content"]
                                break
                            else:
                                break
                    else:
                        reply = ai.chat(message)
                except Exception as e:
                    window.show_response_bubble(_friendly_error(e))
                    return
```

- [ ] **Step 4: Run the Pet import test**

Run:

```bash
PYTHONPATH=src python -c "from holle_music.pet.main import main; print('OK')"
```

Expected: prints `OK` with no errors.

- [ ] **Step 5: Commit**

```bash
git add src/holle_music/pet/main.py
git commit -m "feat(pet): load AI provider config from shared settings"
```

---

## Task 5: Run the full test suite

**Files:**
- Test: `tests/`

- [ ] **Step 1: Run all tests**

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

Expected: all existing tests plus new tests pass.

- [ ] **Step 2: Commit if not already committed**

No code changes if tests passed; nothing to commit.

---

## Task 6: Update project memory

**Files:**
- Create: `memory/modules/project_ai_provider.md`
- Modify: `memory/_index.md`

- [ ] **Step 1: Create `memory/modules/project_ai_provider.md`**

```markdown
---
name: project_ai_provider
description: AI 供应商自动识别与 /ai 命令配置模块
metadata:
  type: project
---

# project_ai_provider

负责 AI 供应商配置表、API key 自动识别、统一服务工厂。

## 文件

- `src/holle_music/ai_provider.py`：核心模块
- `src/holle_music/app.py`：TUI `/ai` 命令与聊天初始化
- `src/holle_music/pet/main.py`：Pet 启动时读取共享配置

## 公开接口

| 名称 | 签名 | 说明 |
|---|---|---|
| `PROVIDERS` | `dict[str, dict[str, Any]]` | 供应商配置表，含 `base_url`/`model`/`test_endpoint` |
| `detect_provider` | `(api_key: str) -> str \| None` | 按优先级发试探请求识别供应商 |
| `create_ai_service` | `(api_key: str, provider: str) -> Any` | 根据供应商创建对应服务实例 |
| `OpenAICompatibleService` | class | 通用 OpenAI-compatible 聊天服务 |

## 支持的供应商

OpenAI、DeepSeek、SiliconFlow、MiniMax、火山方舟（Ark）、Kimi（Moonshot）、通义千问（Qwen）、智谱（Zhipu）。

## 配置存储

通过 `settings.set_setting` 写入 `~/.holle_music/settings.json`：

```json
{
  "ai_provider": "deepseek",
  "ai_api_key": "sk-xxx",
  "ai_base_url": "https://api.deepseek.com",
  "ai_model": "deepseek-chat"
}
```

## 变更历史

- 2026-06-20: 新增模块，实现 `/ai` 命令与供应商自动识别。

## Why

TUI 与 Pet 需要共用用户自定义 API key，并自动识别是哪家供应商，避免硬编码。

## How to apply

新增供应商时：在 `PROVIDERS` 添加条目，按需让 `create_ai_service` 返回已有服务类或 `OpenAICompatibleService`。修改公开接口后同步更新本文件接口表。
```

- [ ] **Step 2: Add module row to `memory/_index.md`**

In the modules table (between `<!-- INDEX:MODULES:START -->` and `<!-- INDEX:MODULES:END -->`), add:

```markdown
| ai_provider | [`modules/project_ai_provider.md`](modules/project_ai_provider.md) | 开发中 | 2026-06-20 | AI 供应商自动识别与 `/ai` 命令配置 |
```

- [ ] **Step 3: Commit memory files**

```bash
git add memory/modules/project_ai_provider.md memory/_index.md
git commit -m "docs(memory): add ai_provider module notes and index"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:**
  - `/ai` command parses and saves config → Task 1 + Task 3
  - Provider auto-detection → Task 2
  - TUI reads config on startup → Task 3
  - Pet reads same config → Task 4
  - Unconfigured chat prompt → Task 3
  - 8 providers supported → Task 2
- [ ] **No placeholders:** Every step contains exact code/commands.
- [ ] **Type consistency:** `detect_provider`, `create_ai_service`, and `OpenAICompatibleService` signatures match the spec.
- [ ] **DRY:** Endpoint probe logic lives only in `_test_provider`.
- [ ] **YAGNI:** No multi-provider switching, no chat history persistence, no UI model picker.
- [ ] **Test coverage:** Provider table, detection priority, invalid key, factory for every provider type, OpenAI-compatible config, parser test.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-20-ai-provider-plan.md`.

**Execution options:**

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

Which approach would you like?
