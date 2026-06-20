---
name: project_ai_provider
description: AI 供应商自动识别与 /ai 命令配置模块
metadata:
  type: project
---

# ai_provider 模块

`src/holle_music/ai_provider.py` —— AI 服务商注册表、API key 自动探测与统一服务工厂。

为 `/ai <apikey>` 命令提供底层支持：根据用户提供的 API key 自动探测服务商，创建对应的服务实例，并持久化到 `~/.holle_music/settings.json`。

## 核心文件

| 类/文件 | 路径 | 职责 |
|---|---|---|
| `ai_provider.py` | `src/holle_music/ai_provider.py` | 供应商表、探测逻辑、服务工厂、通用 OpenAI 兼容服务 |

## 公开接口

| 名称 | 签名 | 说明 |
|---|---|---|
| `PROVIDERS` | `dict[str, dict[str, Any]]` | 供应商配置表，含 `base_url` / `model` / `test_endpoint` |
| `detect_provider(api_key)` | `str \| None` | 按优先级发送轻量请求探测供应商；空/纯空白 key 返回 `None` |
| `create_ai_service(api_key, provider, model=None)` | 服务实例 | 根据供应商创建服务；`model` 为空时使用供应商默认模型 |
| `OpenAICompatibleService` | class | 通用 OpenAI-compatible 聊天服务，提供 `chat` / `query_once` / `search_web` / `clear_history` |

## 支持的供应商

- `openai` — OpenAI
- `deepseek` — DeepSeek（探测优先级最高）
- `siliconflow` — SiliconFlow
- `minimax` — MiniMax（使用专用 `MiniMaxService`）
- `ark` — 火山方舟（使用专用 `ArkService`，探测在最后）
- `kimi` — Moonshot
- `qwen` — 通义千问（DashScope）
- `zhipu` — 智谱 GLM

## 配置存储格式

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

- **2026-06-20 (v0.3.0+)**：创建模块，实现 `PROVIDERS`、`detect_provider`、`create_ai_service`、`OpenAICompatibleService`。
- **2026-06-20**：`create_ai_service` 支持可选 `model` 参数，用于 `/model <模型名>` 切换模型。

## 已知问题

- `ark` 的 `test_endpoint` 为 `None`，探测时总是最后尝试；若 Ark 未来支持 `/models` endpoint 可更新。
- `detect_provider` 对 `sk-` 前缀的 key 会按优先级逐一 probe，首次成功即返回，可能误判（未来可支持 `/ai provider key` 显式指定）。

## Why

TUI 与 Pet 需要共用用户自定义 API key，并自动识别是哪家供应商，避免硬编码和依赖环境变量。

## How to apply

新增供应商时：在 `PROVIDERS` 添加条目，按需让 `create_ai_service` 返回已有服务类或 `OpenAICompatibleService`。修改公开接口后同步更新本文件接口表。
