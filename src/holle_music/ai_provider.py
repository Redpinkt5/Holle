"""AI provider registry, key detection, and unified service factory."""

from __future__ import annotations

from typing import Any, Callable


__all__ = [
    "PROVIDERS",
    "detect_provider",
    "create_ai_service",
    "parse_ai_args",
    "OpenAICompatibleService",
]


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
    except ImportError as exc:
        raise RuntimeError(
            "openai>=1.0.0 is required. Install it with: pip install openai>=1.0.0"
        ) from exc


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
    except urllib.error.HTTPError as exc:
        # A 401 definitively means the key is not accepted by this provider.
        if exc.code == 401:
            return False
        return False
    except Exception:
        return False


def detect_provider(api_key: str) -> str | None:
    """Detect provider from key prefix and endpoint probes.

    Returns one of the keys in PROVIDERS, or None if no provider matches.
    """
    if not api_key:
        return None
    api_key = api_key.strip()
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


def parse_ai_args(arg: str) -> tuple[str | None, str, str | None]:
    """Parse the argument string for the /ai command.

    Supports three forms:
      - <api_key>                     (auto-detect provider, use default model)
      - <provider> <api_key>          (use provider's default model)
      - <provider> <api_key> <model>  (explicit model override)

    Returns (provider_or_none, api_key, model_or_none).
    """
    parts = arg.split()
    if len(parts) == 1:
        return None, parts[0], None
    if len(parts) == 2:
        return parts[0], parts[1], None
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    return None, "", None


def create_ai_service(api_key: str, provider: str, model: str | None = None):
    """Create an AI service instance for the given provider."""
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown AI provider: {provider}")

    config = PROVIDERS[provider]
    base_url = config["base_url"]
    model = model or config["model"]

    if provider == "minimax":
        from holle_music.minimax_api import MiniMaxService

        return MiniMaxService(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )

    if provider == "ark":
        from holle_music.pet.ark_api import ArkService

        return ArkService(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )

    if provider == "deepseek":
        from holle_music.pet.deepseek_api import DeepSeekService

        return DeepSeekService(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )

    # Generic OpenAI-compatible providers: OpenAI, SiliconFlow, Kimi, Qwen, Zhipu.
    return OpenAICompatibleService(
        api_key=api_key,
        base_url=base_url,
        model=model,
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

        last_error = None
        for attempt in range(max_retries):
            self._wait_rate_limit()
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
