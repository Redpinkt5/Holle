"""DeepSeek AI API integration for Holle Pet with function calling support.

Uses OpenAI-compatible endpoint. Auto-installs openai package if missing.
"""

from __future__ import annotations

import time
from typing import Any

# ── API configuration ──────────────────────────────────────────────────
DEEPSEEK_API_KEY = "sk-cd27a7afd2984405a7bb441d35b99522"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# ── System prompt ──────────────────────────────────────────────────────
PET_SYSTEM_PROMPT = """你是 Holle Music 的桌面音乐助手，既能控制音乐播放器，也能陪用户聊天、回答实时性问题。

音乐控制工具：
- search_local: 本地歌单搜索
- play_song: 播放指定歌曲
- toggle_play: 播放/暂停
- next_track / prev_track: 切歌
- set_volume: 调节音量 (0-100)
- set_mode: 切换模式 (sequential/random/repeat)
- get_current_song: 获取当前播放
- get_playlist: 获取播放列表

联网搜索：
- search_web: 如需额外联网信息可调用
- 注意：用户每次提问时，系统已自动联网搜索并把结果附在问题前，请优先依据这些结果回答天气、新闻等实时性问题。
- 当前日期、时间、星期几以对话中提供的系统时间为准，不要依据联网搜索结果推断；除非用户询问日期、时间或星期几，否则不要在回复中主动提及当前系统时间。

规则：
1. 播放歌曲时先 search_local，找到后 play_song
2. 本地没有时告知用户，可 search_web 提供信息
3. 切换模式前询问确认（除非用户明确指令）
4. 用简洁友好的中文回复，不使用 Markdown
5. 用户问实时性/通用问题时，基于已提供的联网搜索结果回答，不要只围绕音乐
"""

# ── Tool definitions (OpenAI function calling schema) ──────────────────
TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_local",
            "description": "在本地播放列表中搜索歌曲",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，可以是歌曲名或歌手名",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "联网搜索歌曲或歌手信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_song",
            "description": "播放指定歌曲",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "歌曲标题",
                    },
                    "artist": {
                        "type": "string",
                        "description": "歌手名（可选）",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "toggle_play",
            "description": "播放/暂停切换",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "next_track",
            "description": "下一曲",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prev_track",
            "description": "上一曲",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "设置音量",
            "parameters": {
                "type": "object",
                "properties": {
                    "volume": {
                        "type": "integer",
                        "description": "音量值，范围 0-100",
                        "minimum": 0,
                        "maximum": 100,
                    },
                },
                "required": ["volume"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_mode",
            "description": "切换播放模式",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "播放模式",
                        "enum": ["sequential", "random", "repeat"],
                    },
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_song",
            "description": "获取当前正在播放的歌曲信息",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_playlist",
            "description": "获取当前播放列表",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


# ── Helpers ────────────────────────────────────────────────────────────


def _ensure_openai() -> None:
    try:
        import openai  # noqa: F401
    except ImportError:
        import subprocess
        import sys

        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "openai>=1.0.0", "-q"]
        )


# ── DeepSeek AI Service ────────────────────────────────────────────────


class DeepSeekService:
    """DeepSeek API service with function calling support.

    - chat(): send message, get text reply or tool-call request
    - submit_tool_result(): feed tool execution result back to AI
    - clear_history(): reset conversation
    - Auto-retry (3 attempts), 30 s timeout
    - Keeps up to 10 rounds of conversation history
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ) -> None:
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.base_url = base_url or DEEPSEEK_BASE_URL
        self.model = model or DEEPSEEK_MODEL
        self._client = None
        self._chat_history: list[dict] = []
        self._max_history = 10

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
        return bool(self.api_key and self.api_key != "your_api_key_here")

    # ── Retry ───────────────────────────────────────────────────────

    def _retry(self, fn, max_retries: int = 3):
        last_error = None
        for attempt in range(max_retries):
            try:
                return fn()
            except Exception as exc:
                last_error = exc
                err = str(exc).lower()
                if any(
                    kw in err
                    for kw in ("401", "unauthorized", "invalid api key", "auth")
                ):
                    raise
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        raise last_error

    # ── History management ──────────────────────────────────────────

    def _ensure_system_prompt(self) -> None:
        if not self._chat_history:
            self._chat_history.append(
                {"role": "system", "content": PET_SYSTEM_PROMPT}
            )

    def _add_user_message(self, message: str) -> None:
        self._chat_history.append({"role": "user", "content": message})

    def _add_assistant_message(self, content: str = "", tool_calls: list | None = None) -> None:
        msg: dict = {"role": "assistant"}
        if content:
            msg["content"] = content
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self._chat_history.append(msg)

    def _add_tool_message(self, tool_call_id: str, result: str) -> None:
        self._chat_history.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            }
        )

    def _trim_history(self) -> None:
        """Keep at most max_history rounds (user + assistant pairs)."""
        max_messages = self._max_history * 2 + 1  # +1 for system prompt
        while len(self._chat_history) > max_messages:
            for i, m in enumerate(self._chat_history):
                if m["role"] != "system":
                    del self._chat_history[i]
                    break

    # ── Chat ────────────────────────────────────────────────────────

    def chat(self, message: str) -> dict:
        """Send a user message and return AI response.

        Returns:
            {"type": "text", "content": str}
            or
            {"type": "tool_calls", "calls": list[dict]}
        """
        if not self.is_configured:
            raise ValueError(_api_key_help())

        self._ensure_system_prompt()
        self._add_user_message(message)
        self._trim_history()

        def _call():
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=self._chat_history,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=1024,
                temperature=0.7,
                timeout=30,
            )
            return resp.choices[0].message

        msg = self._retry(_call)

        # Check for tool calls
        if getattr(msg, "tool_calls", None):
            tool_calls = []
            for tc in msg.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                )
            self._add_assistant_message(tool_calls=msg.tool_calls)
            return {"type": "tool_calls", "calls": tool_calls}

        # Plain text reply
        content = msg.content or ""
        self._add_assistant_message(content=content)
        return {"type": "text", "content": content}

    def submit_tool_result(self, tool_call_id: str, result: str) -> dict:
        """Submit a tool execution result and get AI's next reply.

        Returns:
            {"type": "text", "content": str}
            or
            {"type": "tool_calls", "calls": list[dict]}
        """
        if not self.is_configured:
            raise ValueError(_api_key_help())

        self._add_tool_message(tool_call_id, result)
        self._trim_history()

        def _call():
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=self._chat_history,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=1024,
                temperature=0.7,
                timeout=30,
            )
            return resp.choices[0].message

        msg = self._retry(_call)

        if getattr(msg, "tool_calls", None):
            tool_calls = []
            for tc in msg.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                )
            self._add_assistant_message(tool_calls=msg.tool_calls)
            return {"type": "tool_calls", "calls": tool_calls}

        content = msg.content or ""
        self._add_assistant_message(content=content)
        return {"type": "text", "content": content}

    def submit_tool_results(self, results: list[tuple[str, str]]) -> dict:
        """Submit multiple tool results at once and get the AI's next reply.

        Returns:
            {"type": "text", "content": str}
            or
            {"type": "tool_calls", "calls": list[dict]}
        """
        if not self.is_configured:
            raise ValueError(_api_key_help())

        for tool_call_id, result in results:
            self._add_tool_message(tool_call_id, result)
        self._trim_history()

        def _call():
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=self._chat_history,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=1024,
                temperature=0.7,
                timeout=30,
            )
            return resp.choices[0].message

        msg = self._retry(_call)

        if getattr(msg, "tool_calls", None):
            tool_calls = []
            for tc in msg.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                )
            self._add_assistant_message(tool_calls=msg.tool_calls)
            return {"type": "tool_calls", "calls": tool_calls}

        content = msg.content or ""
        self._add_assistant_message(content=content)
        return {"type": "text", "content": content}

    def clear_history(self) -> None:
        """Clear all conversation history."""
        self._chat_history.clear()

    @property
    def history(self) -> list[dict]:
        return list(self._chat_history)


def _api_key_help() -> str:
    return (
        "DeepSeek API Key 未配置。\n"
        "1. 访问 https://platform.deepseek.com/ 注册\n"
        "2. 在控制台获取 API Key\n"
        "3. 在 src/holle_music/pet/deepseek_api.py 中设置 DEEPSEEK_API_KEY"
    )
