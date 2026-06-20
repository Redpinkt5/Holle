---
name: ai_tool_arguments_json
description: AI function calling 返回的 tool arguments 可能是 JSON 字符串，工具执行器必须兼容解析
metadata:
  type: project
---

# AI 工具参数格式不一致

## 现象

在 TUI 和 Pet 中，使用 DeepSeek 服务时 AI 调用 `search_local`、`play_song`、`search_web` 等工具会失败，AI 回复类似“本地歌单搜索出现了一些小状况”。同一套代码在 Ark 服务下却能正常工作。

## 原因

不同 AI 服务返回的 tool-call 参数格式不同：

- **DeepSeek**（OpenAI SDK 标准格式）：`tool_call.function.arguments` 是 JSON 字符串。
- **Ark**：`ArkService._process_response` 已在内部把参数 `json.loads` 成 dict。

原来的 `AITools.execute` / `TUITools.execute` 直接按 dict 使用参数，DeepSeek 传入字符串时导致 `AttributeError: 'str' object has no attribute 'get'`，被外层捕获后返回“执行失败: ...”，AI 只能给出模糊解释。

## 修复

在两个工具执行器的 `execute` 方法入口处统一做类型适配：

```python
if isinstance(args, str):
    args = json.loads(args) if args.strip() else {}
elif args is None:
    args = {}
```

这样既兼容 JSON 字符串，也兼容已解析的 dict。

## 规则

1. 所有 AI tool-calling 的桥接代码，拿到 `function.arguments` 后必须先判断类型再使用。
2. 优先在一个统一入口处理，不要在每个 tool handler 里重复写 `json.loads`。
3. 新增 AI 服务接入时，明确约定它返回的 tool-call 参数是字符串还是 dict，并在服务层或工具层补齐适配。

## 关联

- `src/holle_music/tui_tools.py`
- `src/holle_music/pet/ai_tools.py`
- `src/holle_music/pet/deepseek_api.py`
- `src/holle_music/pet/ark_api.py`
