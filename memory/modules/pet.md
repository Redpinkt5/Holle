---
name: project_pet
description: 桌面宠物模块，提供浮动窗口、AI 聊天与播放控制
metadata:
  type: project
---

# pet 模块

## 概述

`src/holle_music/pet/` —— 桌面宠物（Desktop Pet）入口与交互逻辑。

Pet 是 Holle Music 的桌面伴侣组件，提供：
- 浮动窗口交互（点击区域控制播放、拖拽移动、右键菜单）
- AI 聊天气泡（底部点击唤起，支持自然语言指令）
- 播放状态同步与恢复

## 核心文件

| 类/文件 | 路径 | 职责 |
|---|---|---|
| `main.py` | `src/holle_music/pet/main.py` | 入口函数 `main()`，初始化播放器、AI 服务、窗口事件循环 |
| `window.py` | `src/holle_music/pet/window.py` | `PetWindow` 浮动窗口、区域点击、气泡渲染 |
| `ai_tools.py` | `src/holle_music/pet/ai_tools.py` | `AITools` 供 AI 调用的工具集（播放控制、搜索等） |
| `ark_api.py` | `src/holle_music/pet/ark_api.py` | `ArkService` 火山方舟专用 AI 服务（带 tool calling） |
| `commands.py` | `src/holle_music/pet/commands.py` | `PetCommandHandler` 处理 `/` 指令（如 /scan、/ai） |
| `player_proxy.py` | `src/holle_music/pet/player_proxy.py` | `PetPlayer` 播放状态代理（IPC/standalone 双模式） |

## 公开接口

| 名称 | 类型 | 说明 |
|---|---|---|
| `main()` | 函数 | 启动桌面宠物，阻塞直到窗口关闭 |

## AI 服务初始化逻辑（重要）

Pet 的 AI 服务按以下优先级初始化：

1. 读取 `~/.holle_music/settings.json` 中的 `ai_provider` + `ai_api_key`
2. 若两者都存在，调用 `create_ai_service(api_key, provider)` 创建对应服务
3. 若创建失败或配置缺失，回退到 `ArkService()`（火山方舟默认）

```python
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

## AI 聊天响应规范化

`on_chat_send` 中的 `ai_worker` 需要兼容两类 AI 服务：

- **带 tool calling**（`ArkService`、`DeepSeekService`）：返回 dict，有 `submit_tool_results` 方法
  - 循环最多 5 轮 tool_calls → submit_tool_results → 最终文本回复
- **纯文本**（`MiniMaxService`、`OpenAICompatibleService`）：`chat()` 直接返回字符串

用 `hasattr(ai, "submit_tool_results")` 区分，避免 `AttributeError`。

## 变更历史

- **2026-06-20** 接入共享 AI 配置：从 `settings.json` 读取 `ai_provider`/`ai_api_key`，支持多服务商切换，回退 ArkService
- **2026-06-20** 修复 `AITools.execute`/`TUITools.execute` 未将 DeepSeek 返回的 JSON 字符串参数解析为 dict 的问题，使本地搜索、播放控制等工具在 DeepSeek 服务下正常工作
- **2026-06-20** 强化 DeepSeek/Ark 系统提示与搜索工具返回文本，要求 AI 在找到歌曲后必须调用 `play_song` 工具实际播放，避免只回复文本而不执行播放
- **2026-06-20** 增加兜底逻辑：当 AI 只搜索不播放且用户话语明显带有播放意图时，自动从最近搜索结果中挑选最佳匹配并调用 `play_song`
- **2026-06-21** 接入 `ai_memory` 模块：`pet/main.py` 在 AI 聊天前注入记忆上下文，回复后记录对话与播放决策；`ark_api.py` / `deepseek_api.py` 系统提示增加记忆使用说明

## 已知问题

- `AITools.execute` 与 `TUITools.execute` 已兼容 dict 和 JSON 字符串两种参数形式，但调用方仍应优先传递 dict；Ark 服务已在内部完成解析。
