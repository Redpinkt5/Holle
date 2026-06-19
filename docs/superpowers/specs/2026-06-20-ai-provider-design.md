# `/ai` 命令与 AI 供应商自动识别设计

**日期**：2026-06-20
**范围**：为 Holle Music TUI 和桌面宠物添加统一的 `/ai <apikey>` 命令，自动识别 AI 供应商并保存配置，使现有 AI 聊天功能能够使用用户自定义的 API key。

---

## 1. 背景与目标

### 1.1 背景

- TUI 已有 AI 聊天面板：用户在命令输入框输入非 `/` 开头的文字，会调用 `_chat_with_ai()` 发送给 AI。
- 当前 `_chat_with_ai()` 固定使用 `MiniMaxService()`，无法切换供应商。
- 用户可能拥有不同供应商的 API key（OpenAI、DeepSeek、Kimi、Qwen 等），希望灵活切换。
- 桌面宠物（Pet）也需要使用同一套 AI 配置。

### 1.2 目标

1. 新增 `/ai <apikey>` 命令，用户输入 API key 后自动识别供应商。
2. 将识别结果（供应商、key、base_url、model）保存到 `~/.holle_music/settings.json`。
3. TUI 启动时读取配置，初始化对应的 AI 服务。
4. Pet 启动时读取同一配置，初始化同一供应商的 AI 服务。
5. 未配置 AI 时，用户发消息聊天提示：`请先使用 /ai <你的 API Key> 配置 AI`。
6. 支持主流 OpenAI-compatible 供应商：OpenAI、DeepSeek、SiliconFlow、MiniMax、火山方舟（Ark）、Kimi（Moonshot）、Qwen（DashScope）、Zhipu（ChatGLM）。

---

## 2. 非目标

- 不替换 Pet 的 function-calling 能力（Pet 仍使用自己的 system prompt 和工具）。
- 不修改现有 AI 服务类的内部实现，只通过统一工厂创建实例。
- 不提供多供应商同时在线切换（一次只用一个供应商）。
- 不保存聊天记录到磁盘。

---

## 3. 改动文件

| 文件 | 改动 |
|---|---|
| `src/holle_music/ai_provider.py` | **新增**：供应商配置表、识别逻辑、统一服务工厂 |
| `src/holle_music/commands.py` | 添加 `AI` 命令类型 |
| `src/holle_music/app.py` | 处理 `/ai` 命令；启动时初始化 AI 服务；未配置时提示 |
| `src/holle_music/pet/main.py` | 启动时读取同一 AI 配置初始化 Pet AI 服务 |
| `tests/test_ai_provider.py` | **新增**：测试供应商识别逻辑 |
| `memory/modules/project_ai_provider.md` | **新增**：记忆文件 |
| `memory/_index.md` | 更新索引 |

---

## 4. 详细设计

### 4.1 `ai_provider.py` 供应商配置

```python
from __future__ import annotations

from typing import Any


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
```

### 4.2 供应商识别逻辑

```python
def _test_provider(config: dict[str, Any], api_key: str) -> bool:
    """Send a lightweight request to verify the key works for a provider."""
    import urllib.request
    import urllib.error

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
    priority = ["deepseek", "openai", "siliconflow", "kimi", "qwen", "zhipu", "minimax"]
    for name in priority:
        if _test_provider(PROVIDERS[name], api_key):
            return name

    # Ark keys typically don't start with sk-; probe last
    if _test_provider(PROVIDERS["ark"], api_key):
        return "ark"

    return None
```

### 4.3 统一服务工厂

```python
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

    # DeepSeek service has tool-calling support, reuse it
    if provider == "deepseek":
        from holle_music.pet.deepseek_api import DeepSeekService
        return DeepSeekService(
            api_key=api_key,
            base_url=config["base_url"],
            model=config["model"],
        )

    # GLM/SiliconFlow uses the same GLMAIService
    if provider == "siliconflow":
        from holle_music.glm_api import GLMAIService
        return GLMAIService()

    # Generic OpenAI-compatible providers (SiliconFlow, OpenAI, Kimi, Qwen, Zhipu)
    from holle_music.ai_provider import OpenAICompatibleService
    return OpenAICompatibleService(
        api_key=api_key,
        base_url=config["base_url"],
        model=config["model"],
    )
```

> **注意**：`GLMAIService` 当前在模块级读取 `SILICONFLOW_API_KEY`。为了支持任意 OpenAI-compatible 供应商，新增一个通用的 `OpenAICompatibleService` 类（复用 `GLMAIService` 的聊天逻辑，但允许构造时覆盖 key、base_url、model），避免污染 `GLMAIService` 的默认行为。

`OpenAICompatibleService` 可以直接基于 `GLMAIService` 改造或复制：构造时接收 `api_key`、`base_url`、`model`，内部使用这些值创建 `OpenAI` 客户端。

### 4.4 `commands.py` 添加 `AI` 命令

```python
class CommandType(Enum):
    ...
    AI = auto()

_COMMAND_MAP: dict[str, CommandType] = {
    ...
    "/ai": CommandType.AI,
}
```

### 4.5 `app.py` 改动

#### 启动时初始化 AI 服务

```python
def __init__(self) -> None:
    ...
    self._ai = self._init_ai_service()


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

#### 处理 `/ai` 命令

```python
elif cmd.type == CommandType.AI:
    key = (cmd.args or "").strip()
    if not key:
        self._notify_chat("用法: /ai <你的 API Key>")
    else:
        from holle_music.ai_provider import detect_provider, PROVIDERS
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

#### 未配置时提示

```python
def _chat_with_ai(self, text: str) -> None:
    if self._ai is None:
        self._notify_chat("请先使用 /ai <你的 API Key> 配置 AI")
        return
    # 原有逻辑
```

### 4.6 Pet 共用配置

在 `pet/main.py` 中，把原本直接创建 `ArkService()` 的地方改为：

```python
from holle_music.ai_provider import create_ai_service, detect_provider, PROVIDERS
from holle_music.settings import load_settings

settings = load_settings()
provider = settings.get("ai_provider")
api_key = settings.get("ai_api_key")

if provider and api_key:
    ai = create_ai_service(api_key, provider)
else:
    ai = ArkService()  # fallback to default
```

> Pet 的 `ArkService` 有 function-calling 和 web_search 工具，如果用户选择非 Ark 供应商，Pet 需要降级到只聊天（用 `DeepSeekService` 或通用服务），或保持 Ark 作为 Pet 默认。设计决策：Pet 优先使用用户配置的供应商，但 function calling 只在 DeepSeek/Ark 等支持的工具模型上生效。

---

## 5. 配置存储格式

```json
{
  "ai_provider": "deepseek",
  "ai_api_key": "sk-xxxxxxxx",
  "ai_base_url": "https://api.deepseek.com",
  "ai_model": "deepseek-chat"
}
```

---

## 6. 数据流

```
用户输入 /ai sk-xxx
    │
    ▼
parse_command → CommandType.AI
    │
    ▼
detect_provider(api_key)
    │
    ├── 前缀匹配（如 sk-ant- → anthropic）
    └── 否则按优先级发试探请求
              │
              ▼
    识别成功 → 保存配置到 settings.json
              │
              ▼
    create_ai_service() 初始化 self._ai
              │
              ▼
用户后续聊天 → _chat_with_ai() 使用 self._ai
```

---

## 7. 错误处理

- 空 key：提示用法
- 识别失败：提示检查 key
- 试探请求超时（3 秒）：继续试下一个供应商
- 网络异常：静默跳过当前供应商
- 服务初始化失败：提示具体错误
- 配置保存失败：静默忽略（保持 settings.py 现有行为）

---

## 8. 兼容性

- 旧版本没有 AI 配置 → `self._ai = None`，聊天时提示配置
- 已有 `MINIMAX_API_KEY` 等环境变量 → 不再依赖，统一以 `/ai` 设置为准
- TUI 和 Pet 读取同一 `settings.json`，配置互通

---

## 9. 测试计划

1. `test_detect_provider_by_endpoint`：模拟 DeepSeek /models 请求成功
2. `test_detect_provider_returns_none_for_invalid_key`：无效 key 返回 None
3. `test_detect_provider_priority_order`：多个供应商都通时按优先级返回
4. `test_create_ai_service_returns_correct_type`：根据供应商创建正确类
5. `test_create_ai_service_openai_compatible_uses_custom_config`：`OpenAICompatibleService` 使用传入的 base_url/model
6. `test_create_ai_service_unknown_provider_raises`：未知供应商抛 ValueError
7. `test_ai_settings_saved_correctly`：集成测试 `/ai` 命令保存配置（可 mock detect_provider）

---

## 10. 风险评估

- **低风险**：新增模块，不破坏现有命令解析和聊天流程。
- **风险点**：
  - 试探请求需要联网，识别过程可能慢（最多 7 个供应商 × 3 秒 = 21 秒上限）。实际通常前几个就能命中。
  - `GLMAIService` 需要小改造以支持任意 base_url/model。
  - Pet 使用非 Ark 供应商时，function calling 可能不生效。

---

## 11. 后续可扩展

- 支持 `/ai provider key` 显式指定供应商，绕过自动识别。
- 支持 `/ai model <模型名>` 切换同一供应商的不同模型。
- 添加 `ai_timeout` 配置项。

---

*Generated during v0.3.0+ brainstorming.*
