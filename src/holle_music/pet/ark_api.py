"""Ark (Volcengine) API integration for Holle Pet.

Uses the OpenAI-compatible Responses API endpoint with the
``deepseek-v4-flash-260425`` model. The model has a built-in ``web_search``
tool for real-time information and supports function calling for local
music-player control.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from holle_music.pet import deepseek_api


# ── API configuration ──────────────────────────────────────────────────
ARK_API_KEY = os.environ.get("ARK_API_KEY", "")
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
ARK_MODEL = "deepseek-v4-flash-260425"


# ── System prompt ──────────────────────────────────────────────────────
ARK_SYSTEM_PROMPT = """你是 Holle Music 的桌面音乐助手，既能控制音乐播放器，也能陪用户聊天、回答实时性问题。

本地音乐控制工具：
- search_local: 本地歌单搜索
- play_song: 播放指定歌曲
- toggle_play: 播放/暂停
- next_track / prev_track: 切歌
- set_volume: 调节音量 (0-100)
- set_mode: 切换模式 (sequential/random/repeat)
- get_current_song: 获取当前播放
- get_playlist: 获取当前播放列表

联网搜索：
- 模型自带 web_search 工具，可自动联网查询实时信息。
- 回答天气、新闻、股票等实时性问题时应自动调用联网搜索。
- 当前日期、时间、星期几以对话中提供的系统时间为准；除非用户询问日期、时间或星期几，否则不要在回复中主动提及当前系统时间。

规则：
1. 播放歌曲时先 search_local，找到后 play_song
2. 本地没有时告知用户，可自动联网搜索提供信息
3. 切换模式前询问确认（除非用户明确指令）
4. 用简洁友好的中文回复，不使用 Markdown
5. 用户问实时性/通用问题时，优先使用联网搜索结果，不要只围绕音乐
"""


# ── Tool definitions ───────────────────────────────────────────────────
# Reuse the function-tool schemas from DeepSeek, but drop its ``search_web``
# function because Ark provides a native web_search tool.
# Ark's Responses API expects function tools to be flat
# (type, name, description, parameters) instead of nested under ``function``.
_FUNCTION_TOOLS = [
    {
        "type": "function",
        **tool["function"],
    }
    for tool in deepseek_api.TOOLS
    if tool.get("function", {}).get("name") != "search_web"
]

ARK_TOOLS: list[dict[str, Any]] = [
    {"type": "web_search", "max_keyword": 3},
] + _FUNCTION_TOOLS


# ── Helpers ────────────────────────────────────────────────────────────


def _ensure_openai() -> None:
    try:
        import openai  # noqa: F401
    except ImportError:
        import subprocess
        import sys

        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "openai>=1.70.0", "-q"]
        )


def _api_key_help() -> str:
    return (
        "ARK_API_KEY 未配置。\n"
        "1. 访问 https://console.volcengine.com/ark 注册并开通方舟\n"
        "2. 在控制台获取 API Key\n"
        "3. 设置环境变量 ARK_API_KEY，或在 src/holle_music/ark_api.py 中配置"
    )


# ── Ark AI Service ─────────────────────────────────────────────────────


class ArkService:
    """Ark Responses API service with web_search and function calling.

    - chat(): send a user message, return text reply or tool-call request
    - submit_tool_results(): feed function execution results back to the model
    - Keeps the last response id for multi-turn context
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ) -> None:
        self.api_key = api_key or ARK_API_KEY
        self.base_url = base_url or ARK_BASE_URL
        self.model = model or ARK_MODEL
        self._client: Any | None = None
        self._last_response_id: str | None = None

    @property
    def client(self) -> Any:
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

    # ── Request helpers ─────────────────────────────────────────────

    def _create_response(
        self,
        input_items: list[dict[str, Any]],
        previous_response_id: str | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "input": input_items,
            "tools": ARK_TOOLS,
            "stream": False,
        }
        if previous_response_id:
            kwargs["previous_response_id"] = previous_response_id

        def _call():
            return self.client.responses.create(**kwargs)

        return self._retry(_call)

    def _process_response(self, response: Any) -> dict[str, Any]:
        """Parse an Ark response into our standard format."""
        self._last_response_id = getattr(response, "id", None) or self._last_response_id

        tool_calls: list[dict[str, Any]] = []
        text_parts: list[str] = []

        output = getattr(response, "output", []) or []
        for item in output:
            item_type = getattr(item, "type", None)

            if item_type == "function_call":
                call_id = getattr(item, "call_id", None) or getattr(item, "id", "")
                name = getattr(item, "name", "")
                arguments = getattr(item, "arguments", "")
                if not arguments and hasattr(item, "function"):
                    arguments = getattr(item.function, "arguments", "")
                try:
                    args = json.loads(arguments) if arguments else {}
                except Exception:
                    args = {}
                tool_calls.append(
                    {"id": call_id, "name": name, "arguments": args}
                )

            elif item_type == "message":
                content = getattr(item, "content", []) or []
                for part in content:
                    if getattr(part, "type", None) == "output_text":
                        text = getattr(part, "text", "")
                        if text:
                            text_parts.append(text)

        if tool_calls:
            return {"type": "tool_calls", "calls": tool_calls}

        return {"type": "text", "content": "".join(text_parts)}

    # ── Public API ──────────────────────────────────────────────────

    def chat(self, message: str) -> dict[str, Any]:
        """Send a user message and return the model's reply.

        Returns:
            {"type": "text", "content": str}
            or
            {"type": "tool_calls", "calls": list[dict]}
        """
        if not self.is_configured:
            raise ValueError(_api_key_help())

        if self._last_response_id:
            input_items = [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": message}],
                }
            ]
            response = self._create_response(
                input_items, previous_response_id=self._last_response_id
            )
        else:
            input_items = [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": ARK_SYSTEM_PROMPT}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": message}],
                },
            ]
            response = self._create_response(input_items)

        return self._process_response(response)

    def submit_tool_result(self, tool_call_id: str, result: str) -> dict[str, Any]:
        """Submit a single function execution result."""
        return self.submit_tool_results([(tool_call_id, result)])

    def submit_tool_results(self, results: list[tuple[str, str]]) -> dict[str, Any]:
        """Submit multiple function execution results at once."""
        if not self.is_configured:
            raise ValueError(_api_key_help())

        if not self._last_response_id:
            return {"type": "text", "content": ""}

        input_items = [
            {
                "type": "function_call_output",
                "call_id": call_id,
                "output": result,
            }
            for call_id, result in results
        ]

        response = self._create_response(
            input_items, previous_response_id=self._last_response_id
        )
        return self._process_response(response)

    def clear_history(self) -> None:
        """Reset conversation context."""
        self._last_response_id = None
