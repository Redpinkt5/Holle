"""SiliconFlow API — GLM-Z1-9B-0414 chat integration with web search."""

from __future__ import annotations

import os
import time
from typing import Callable

API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
BASE_URL = "https://api.siliconflow.cn/v1/"
MODEL = "THUDM/GLM-Z1-9B-0414"

SYSTEM_PROMPT = """你是一个专业的音乐助手，运行在终端音乐播放器中。
你有联网搜索能力，会收到实时的搜索结果作为参考信息。
请优先根据搜索结果回答用户问题，特别是实时信息（日期、天气、新闻等）。
回答要简洁自然，不使用Markdown格式。
当前歌曲信息会附在问题前，可据此回答音乐相关问题。"""


def _ensure_openai() -> None:
    try:
        import openai  # noqa: F401
    except ImportError:
        import subprocess, sys
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "openai>=1.0.0", "-q"]
        )


class GLMAIService:
    """SiliconFlow chat service (OpenAI-compatible)."""

    def __init__(self) -> None:
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
            self._client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        return self._client

    @property
    def is_configured(self) -> bool:
        return bool(API_KEY)

    def _wait_rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

    def _retry(self, fn, max_retries: int = 3):
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
            self._chat_history.append({"role": "system", "content": SYSTEM_PROMPT})

        self._chat_history.append({"role": "user", "content": message})

        # Trim old messages (keep system + last N exchanges)
        while len(self._chat_history) > self._max_history * 2 + 1:
            for i, m in enumerate(self._chat_history):
                if m["role"] != "system":
                    del self._chat_history[i]
                    break

        def _call():
            if on_token:
                resp = self.client.chat.completions.create(
                    model=MODEL,
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
            else:
                resp = self.client.chat.completions.create(
                    model=MODEL,
                    messages=self._chat_history,
                    max_tokens=1024,
                    temperature=0.7,
                    timeout=60,
                )
                content = resp.choices[0].message.content or "" if resp.choices else ""
                self._chat_history.append({"role": "assistant", "content": content})
                return content

        return self._retry(_call)

    def search_web(self, query: str) -> str:
        """Search the web and return formatted results."""
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=5):
                    title = r.get('title', '')
                    body = r.get('body', '')
                    if title and body:
                        results.append(f"- {title}: {body}")
            return "\n".join(results) if results else ""
        except Exception:
            return ""

    def query_once(
        self,
        prompt: str,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """One-shot query without touching chat history."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        def _call():
            if on_token:
                resp = self.client.chat.completions.create(
                    model=MODEL,
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
            else:
                resp = self.client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    max_tokens=512,
                    temperature=0.7,
                    timeout=60,
                )
                return resp.choices[0].message.content or ""

        return self._retry(_call)

    def clear_history(self) -> None:
        self._chat_history.clear()

    @property
    def history(self) -> list[dict]:
        return list(self._chat_history)
