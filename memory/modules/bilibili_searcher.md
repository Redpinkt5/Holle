---
name: project_bilibili_searcher
description: Bilibili 音频搜索与下载模块
metadata:
  type: project
---

# bilibili_searcher 模块

`src/holle_music/bilibili_searcher.py` —— 负责 Bilibili 视频搜索、音频流解析与下载。

## 核心接口

| 名称 | 签名 | 说明 |
|---|---|---|
| `BilibiliSearcher` | class | 搜索与下载入口。 |
| `search(query, max_results=10)` | method | 返回 `list[Song]`，每个 Song 的 `source="bilibili"`。 |
| `download_audio(song)` | method | 下载音频到缓存，返回本地 `Path`。 |
| `cancel()` | method | 取消正在进行的搜索/下载。 |
| `is_network_error(exc)` | function | 判断异常是否为网络错误。 |

## 变更历史

- **2026-06-22**: 创建模块，支持 B 站搜索与音频下载，供 TUI 和 Pet 共用。
