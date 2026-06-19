---
name: project_commands
description: TUI 命令解析器，负责把用户输入解析为 CommandType + 参数
metadata:
  type: project
---

# 命令解析器 (Command Parser)

## 位置
- 实现：`src/holle_music/app.py` 中 `CommandType` enum、`COMMAND_MAP`、`parse_command()` 函数
- 测试：`tests/test_commands.py`

## 公开接口

| 符号 | 类型 | 说明 |
|---|---|---|
| `CommandType` | `Enum` | 所有支持的命令类型枚举 |
| `Command` | `dataclass` | `type: CommandType`, `args: str = ""` |
| `parse_command(text: str) -> Command` | 函数 | 解析用户输入字符串为 Command |
| `COMMAND_MAP` | `dict[str, CommandType]` | 关键字到命令类型的映射表 |

## 变更历史

- **2026-06-20**: 新增 `CommandType.AI` 与 `/ai`、`ai` 映射，支持 `/ai <apikey>` 命令解析。

## 设计说明

- 命令解析器目前与主应用 `HolleMusicApp` 同文件，没有独立模块。
- `parse_command` 对输入做 `strip()` 后按第一个空格分割，前半部分转小写后在 `COMMAND_MAP` 中查找，未找到则返回 `UNKNOWN`。
- 同时支持 `/` 前缀和无前缀形式（如 `/play` 和 `play`）。
