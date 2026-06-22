---
name: project_online_cache
description: 在线音频缓存管理模块，含 LRU 清理
metadata:
  type: project
---

# online_cache 模块

`src/holle_music/online_cache.py` —— 管理 Bilibili 音频缓存目录、命中查询、LRU 自动清理与手动清理。

## 核心接口

| 名称 | 签名 | 说明 |
|---|---|---|
| `cache_dir()` | function | 返回并创建缓存目录。 |
| `audio_path(bvid)` | function | 返回已缓存音频路径或 `None`。 |
| `is_cached(bvid)` | function | 是否已缓存。 |
| `save_metadata(bvid, metadata)` | function | 保存/更新元数据。 |
| `touch(bvid)` | function | 更新 `last_played_at`。 |
| `cleanup(max_mb, max_files)` | function | LRU 清理。 |
| `cleanup_from_settings()` | function | 按 `settings.json` 配置清理。 |
| `clear()` | function | 清空缓存。 |
| `cache_info()` | function | 返回缓存大小和文件数。 |

## 配置项

- `bilibili_cache_max_mb`：默认 1024
- `bilibili_cache_max_files`：默认 200

## 变更历史

- **2026-06-22**: 创建模块，支持 B 站音频缓存 LRU 管理。
