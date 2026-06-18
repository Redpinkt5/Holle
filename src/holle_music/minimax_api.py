"""MiniMax audio/video API integration for lyrics recognition + chat.

OpenAI-compatible endpoint. No ffmpeg — uses soundfile for audio reading.
"""

from __future__ import annotations

import base64
import io
import os
import re
import time
import wave
from typing import Callable

# ── User configuration ─────────────────────────────────────────────────
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = "https://api.minimaxi.com/v1"
MINIMAX_MODEL = "minimax-text-01"  # 根据你的 API 套餐更换模型名

# ── Prompts (same as GLM) ──────────────────────────────────────────────
LYRICS_PROMPT = """你是一个专业的音乐歌词识别专家。请仔细听下面的音频片段，准确识别出其中的歌词内容。

要求：
1. 严格返回标准LRC格式的歌词，不要任何解释、说明或额外内容
2. 每行歌词前必须包含精确到两位小数的时间戳，格式为[mm:ss.xx]
3. 按照歌曲的自然段落分行
4. 不要添加任何标题、作者或其他信息
5. 如果有重复的副歌部分，也要完整写出
6. 如果识别不确定，用"[?]"标记该句
7. 如果是纯音乐，返回"[00:00.00]纯音乐，无歌词"
"""

CHAT_SYSTEM_PROMPT = """你是一个专业的音乐助手，同时也是一个友好的聊天伙伴。
你正在一个终端音乐播放器中运行，用户正在听音乐。

每次提问时，你会收到：
1. 当前系统时间（精确到秒）
2. 当前播放的歌曲信息（如果有）
3. 通过联网搜索获得的实时参考信息（如果有）

回答要求：
- 对于时间、天气、新闻等实时性问题，请优先根据当前时间和联网搜索结果回答
- 请用简洁、自然的语言，不要使用任何Markdown格式
- 如果用户问音乐相关的问题，请给出专业准确的回答
- 如果用户问其他问题，也请友好地回答
- 不要编造搜索结果中没有的信息"""

# ── Limits ─────────────────────────────────────────────────────────────
MAX_AUDIO_SIZE_MB = 20
MAX_DURATION_SECS = 90


def _audio_to_base64_wav(file_path: str) -> str:
    """Read audio via soundfile, convert to mono 16-bit WAV, base64 encode.

    Handles FLAC, WAV, MP3, M4A, etc.  No ffmpeg needed.
    For large files only the first 90s (or ~8M samples) are read.
    """
    import numpy as np
    import soundfile as sf

    info = sf.info(file_path)
    sr = info.samplerate
    channels = info.channels

    max_samples = int(MAX_DURATION_SECS * sr)
    # Cap raw WAV at ~15 MB (16-bit mono)
    limit = (15 * 1024 * 1024) // 2
    max_samples = min(max_samples, limit)

    data, _ = sf.read(file_path, frames=max_samples, dtype="float32")

    # Stereo → mono
    if data.ndim == 2 and channels > 1:
        data = data.mean(axis=1)

    # Normalise
    peak = float(np.max(np.abs(data)))
    if peak > 0:
        data = data / peak * 0.95

    # Write 16-bit WAV to memory
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((data * 32767).astype(np.int16).tobytes())

    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:audio/wav;base64,{b64}"


def _ensure_openai() -> None:
    try:
        import openai  # noqa: F401
    except ImportError:
        import subprocess
        import sys
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "openai>=1.0.0", "-q"]
        )


# ── MiniMax AI Service ──────────────────────────────────────────────────


class MiniMaxService:
    """MiniMax audio/video API service.

    - Lyrics recognition: send audio → get LRC lyrics
    - Chat: streaming conversation with context memory
    - Auto-retry (3 attempts), 30s timeout
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
    ) -> None:
        self.api_key = api_key or MINIMAX_API_KEY
        self.base_url = base_url or MINIMAX_BASE_URL
        self.model = model or MINIMAX_MODEL
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
                if any(kw in err for kw in ("401", "unauthorized", "invalid api key", "auth")):
                    raise
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        raise last_error

    # ── Lyrics recognition ──────────────────────────────────────────

    def recognize_lyrics(
        self,
        audio_path: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> str:
        """Send audio to MiniMax, get LRC lyrics back.

        Reads audio via soundfile (no ffmpeg), encodes as base64 WAV,
        sends to multimodal endpoint.
        """
        if not self.is_configured:
            raise ValueError(_api_key_help())

        if on_progress:
            on_progress("🔍 准备音频...")

        audio_url = _audio_to_base64_wav(audio_path)

        if on_progress:
            on_progress("🔍 AI 正在识别歌词...")

        def _call():
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": LYRICS_PROMPT},
                        {"type": "audio_url", "audio_url": {"url": audio_url}},
                    ],
                }],
                max_tokens=2048,
                temperature=0.3,
                timeout=30,
            )
            return resp.choices[0].message.content or ""

        return self._retry(_call)

    # ── LRC parsing ─────────────────────────────────────────────────

    @staticmethod
    def parse_lrc(lrc_text: str) -> list[dict]:
        segments: list[dict] = []
        pattern = re.compile(r'\[(\d{2}):(\d{2})\.(\d{2,3})\](.*)')

        for raw in lrc_text.strip().split('\n'):
            raw = raw.strip()
            if not raw:
                continue
            m = pattern.match(raw)
            if not m:
                continue
            mins, secs, frac = int(m[1]), int(m[2]), int(m[3])
            start = mins * 60 + secs + (frac / 1000.0 if frac >= 100 else frac / 100.0)
            text = m[4].strip()
            if text:
                segments.append({"start": start, "end": start + 5.0, "text": text})

        for i in range(len(segments) - 1):
            segments[i]["end"] = min(segments[i + 1]["start"], segments[i]["start"] + 10.0)
        if segments:
            segments[-1]["end"] = segments[-1]["start"] + 10.0

        return segments

    # ── Chat ────────────────────────────────────────────────────────

    def chat(
        self,
        message: str,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """Send chat message, optionally stream tokens back."""
        if not self.is_configured:
            raise ValueError(_api_key_help())

        if not self._chat_history:
            self._chat_history.append({
                "role": "system", "content": CHAT_SYSTEM_PROMPT,
            })

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
                    timeout=30,
                    stream=True,
                )
                full = ""
                for chunk in resp:
                    delta = getattr(chunk.choices[0].delta, "content", None)
                    if delta:
                        full += delta
                        on_token(delta)
                self._chat_history.append({"role": "assistant", "content": full})
                return full
            else:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=self._chat_history,
                    max_tokens=1024,
                    temperature=0.7,
                    timeout=30,
                )
                content = resp.choices[0].message.content or ""
                self._chat_history.append({"role": "assistant", "content": content})
                return content

        return self._retry(_call)

    def clear_history(self) -> None:
        self._chat_history.clear()

    @property
    def history(self) -> list[dict]:
        return list(self._chat_history)

    # ── One-shot query (no history) ─────────────────────────────────

    def query_once(
        self,
        prompt: str,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """One-shot query without touching chat history."""
        messages = [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        def _call():
            if on_token:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=512,
                    temperature=0.7,
                    timeout=30,
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
                    model=self.model,
                    messages=messages,
                    max_tokens=512,
                    temperature=0.7,
                    timeout=30,
                )
                return resp.choices[0].message.content or ""

        return self._retry(_call)

    # ── Web search (same as GLM) ────────────────────────────────────

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
                    href = r.get("href", "")
                    if title and body:
                        results.append(f"[{title}]\n{body}\n{href}")
            return "\n\n".join(results)
        except Exception:
            return ""


def _api_key_help() -> str:
    return (
        "MiniMax API Key 未配置。\n"
        "1. 访问 https://platform.minimaxi.com/ 注册\n"
        "2. 在控制台获取 API Key\n"
        "3. 在 src/holle_music/minimax_api.py 中设置 MINIMAX_API_KEY"
    )
