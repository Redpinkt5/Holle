---
name: settings-module
description: 用户配置持久化模块，负责颜色、音量、播放模式、音乐目录等设置的读写与迁移
type: project
---

# settings 模块

**状态**：已上线（v0.3.0 迁移到用户目录）
**上线时间**：2026-06
**所属业务**：Holle Music 核心配置

负责 Holle Music 所有用户持久化配置的读写，包括：
- 闪烁颜色 `color`
- 主题色 `main_color`
- 音量 `volume`
- 播放模式 `play_mode`
- 音乐目录 `music_dir`
- 上次播放歌曲 `current_song_path` / `current_song_title`

---

## 一、核心文件

| 类/文件 | 路径 | 职责 |
|---|---|---|
| `settings.py` | `src/holle_music/settings.py` | 配置读写、默认值、旧配置迁移 |

---

## 二、核心接口概要

### `load_settings() -> dict[str, Any]`
- 读取用户配置，按优先级合并默认值
- 读取顺序：新路径 → 旧路径 → legacy `.holle_color.json` → 默认值
- 启动时会自动触发 `_migrate_settings()`

### `save_settings(updates: dict[str, Any]) -> None`
- 合并更新并持久化到 `~/.holle_music/settings.json`
- 写入失败静默忽略，保证应用不崩溃

### `set_setting(key: str, value: Any) -> None`
- 设置单个配置项并持久化

### `get_setting(key: str, default: Any = None) -> Any`
- 读取单个配置项

---

## 三、数据存储

| 文件 | 路径 | 说明 |
|---|---|---|
| 当前配置文件 | `~/.holle_music/settings.json` | v0.3.0 起统一使用 |
| 旧配置文件 | `<package_dir>/.holle_settings.json` | v0.3.0 前使用，自动迁移后保留为备份 |
| legacy 颜色文件 | `<package_dir>/.holle_color.json` | 更早期的颜色配置，仍作为 fallback |

---

## 四、相关记忆

- [设计决策](design.md)
- [接入方式](integration.md)
- [已知遗留问题](known_issues.md)

---

## 变更历史

- **2026-06-20 (v0.3.0)**：将配置存储路径从 Python 包目录迁移到 `~/.holle_music/settings.json`。新增 `_migrate_settings()` 自动迁移旧配置，保留旧文件作为备份。解决 PyInstaller 单文件 exe 和 `pip install` 后配置丢失问题。
- **2026-06-20 (v0.3.0)**：新增 `tests/test_settings.py`，覆盖迁移、读取优先级、legacy 回退、保存行为、损坏 JSON 等场景。
