# 当前状态

- **版本**：v0.3.2（已推送 tag，GitHub Actions release 流程已触发）
- **主要完成项**：
  - `/ai <apikey>` 自动识别 AI 供应商，`/model <模型名>` 切换模型
  - TUI 与 Pet 共享 `~/.holle_music/settings.json` 中的 AI 配置
  - TUI 支持 AI tool calling 控制播放器
  - Pet 输入气泡支持 `Ctrl+V`/`Ctrl+C`/`Ctrl+A` 与右键粘贴
  - 修复 DeepSeek tool-call 历史格式错误
  - 修复 AI 工具参数 JSON 字符串未解析导致本地/联网搜索失败的问题
- **测试**：87/87 通过
- **待观察**：GitHub Actions release  artifact 生成结果
