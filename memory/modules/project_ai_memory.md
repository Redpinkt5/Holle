---
name: project_ai_memory
description: AI 助手持久化记忆模块，支持短期/长期记忆与 prompt 注入
metadata:
  type: project
---

# ai_memory 模块

`src/holle_music/ai_memory.py` —— 为 Holle Music 的 AI 助手提供跨会话记忆能力。

## 设计

参考 `desktop-pet` 的五层记忆思路，但当前版本做了简化：

- **短期记忆（STM）**：进程内 `list`，按条数（默认 50）和年龄（默认 2 小时）淘汰。
- **长期记忆（LTM）**：持久化到 `~/.holle_music/ai_memory.json`，按关键词匹配 + 重要性 + 近一周时间衰减进行检索。
- **自动提升**：重要性 >= 0.5 或类型为 `preference` 的条目自动写入长期记忆。
- **Prompt 注入**：`MemoryManager.build_context(query)` 生成 `[记忆上下文]` 块，prepend 到 AI 用户消息中。

## 核心类

| 名称 | 说明 |
|---|---|
| `MemoryKind` | `conversation` / `observation` / `decision` / `preference` |
| `MemoryEntry` | 单条记忆：id、timestamp、kind、content、importance、metadata |
| `ShortTermMemory` | 进程内短期记忆，带 count/age 淘汰 |
| `LongTermMemory` | JSON 文件持久化，关键词检索 |
| `MemoryManager` | 统一入口：record / build_context / get_memories / prune |

## 公开接口

| 名称 | 签名 | 说明 |
|---|---|---|
| `MemoryManager(file_path=None)` | 类 | `file_path` 默认 `~/.holle_music/ai_memory.json` |
| `record(kind, content, importance=0.5, metadata=None)` | 方法 | 写入记忆，重要条目自动进 LTM |
| `build_context(query="")` | 方法 | 返回 prompt 可用的记忆上下文字符串，空则返回 `""` |
| `get_memories(kind=None, limit=50)` | 方法 | 获取最近记忆（STM + LTM） |
| `prune()` | 方法 | 清理 30 天前且重要性 < 0.2 的 LTM 条目 |

## 集成点

- **TUI**：`HolleMusicApp.__init__` 创建 `MemoryManager`；`_chat_with_ai` 在发消息前调用 `build_context(text)` 注入上下文，收到回复后把用户/AI 对话写入记忆，播放操作写入 `decision`。
- **Pet**：`pet/main.py` 创建 `MemoryManager`；`ai_worker` 在发送消息前注入上下文，回复后记录对话与决策。
- **系统提示**：`ai_provider.py` 的 `_SYSTEM_PROMPT`、`deepseek_api.py` 的 `PET_SYSTEM_PROMPT`、`ark_api.py` 的 `ARK_SYSTEM_PROMPT` 均已加入“请基于记忆上下文做决策”的说明。

## 变更历史

- **2026-06-21**：创建 `ai_memory.py`，实现 STM + LTM + prompt 注入，接入 TUI 与 Pet。

## Why

没有记忆的 AI 每次聊天都像第一次见用户。记住用户喜欢的歌手、常听的歌曲、最近的对话，能让回复更个性化，也能让“播放我喜欢的歌”这类指令真正可用。

## How to apply

新增记忆类型时：在 `MemoryKind` 加枚举值即可，build_context 已按 `conversation` / 其他类型分组展示。
