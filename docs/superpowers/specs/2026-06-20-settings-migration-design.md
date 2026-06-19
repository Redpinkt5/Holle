# v0.3.0 用户配置持久化迁移设计

**日期**：2026-06-20
**范围**：将 Holle Music 的用户配置存储位置从 Python 包目录迁移到用户主目录，确保 `pip install`、PyInstaller 单文件 exe 和源码开发环境下配置都能正确持久化。

---

## 1. 背景与问题

当前配置存储在 `src/holle_music/.holle_settings.json`（即 `settings.py` 所在目录）。该位置在以下场景存在问题：

- **PyInstaller 单文件 exe**：运行时 `__file__` 指向临时解压目录，退出后临时目录被删除，配置丢失。
- **`pip install` 安装**：包位于 `site-packages`，通常需要管理员权限才能写入。
- **源码开发**：配置与源码混在一起，不便备份和清理。

目标位置：`~/.holle_music/settings.json`（跨平台，Windows 下为 `C:\Users\<user>\.holle_music\settings.json`）。

---

## 2. 目标

1. 所有运行环境的配置统一持久化到 `~/.holle_music/settings.json`。
2. 自动迁移旧配置，用户不丢失已有设置（颜色、主题色、音量、播放模式、音乐目录、上次播放歌曲等）。
3. 保持 `load_settings()` / `save_settings()` / `set_setting()` / `get_setting()` 的公开接口不变。
4. 其他调用方（`app.py`、`pet/main.py`、`pet/commands.py` 等）无需修改。

---

## 3. 非目标

- 不改配置的数据结构或键名。
- 不新增除迁移外的其他配置项。
- 不删除旧配置文件（保留作为备份，避免迁移失败导致数据丢失）。

---

## 4. 改动文件

- `src/holle_music/settings.py`：唯一需要修改的文件。

---

## 5. 详细设计

### 5.1 新配置路径

```python
def _settings_path() -> Path:
    """Return path to the unified settings file in the user's home directory."""
    settings_dir = Path.home() / ".holle_music"
    try:
        settings_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return settings_dir / "settings.json"
```

### 5.2 旧配置路径（用于迁移）

```python
def _old_settings_path() -> Path:
    """Legacy settings file next to this module (pre-0.3.0)."""
    return Path(__file__).parent / ".holle_settings.json"
```

### 5.3 迁移逻辑

在 `load_settings()` 中调用 `_migrate_settings()`：

```python
def _migrate_settings() -> None:
    """Copy settings from legacy package location to user home if needed."""
    new_path = _settings_path()
    if new_path.exists():
        return

    old_path = _old_settings_path()
    if old_path.exists():
        try:
            data = json.loads(old_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                new_path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        except Exception:
            pass
```

### 5.4 读取顺序

`load_settings()` 按以下顺序读取：

1. 触发 `_migrate_settings()`。
2. 读取 `~/.holle_music/settings.json`。
3. 若新路径不存在，读取旧路径 `src/holle_music/.holle_settings.json`。
4. 若旧路径不存在，读取 legacy `.holle_color.json` 中的 `color`。
5. 若都没有，返回 `DEFAULT_SETTINGS`。

### 5.5 保存逻辑

`save_settings()` 始终写入新路径：

```python
def save_settings(updates: dict[str, Any]) -> None:
    settings = load_settings()
    settings.update(updates)
    path = _settings_path()
    try:
        path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass
```

`set_setting()` 继续复用 `save_settings()`。

---

## 6. 数据流

```
用户运行 app / pet / exe
    │
    ▼
load_settings()
    │
    ├── 新路径存在？───→ 读 ~/.holle_music/settings.json
    │
    ├── 新路径不存在 ──→ _migrate_settings()
    │                       │
    │                       ▼
    │               旧路径有文件？───→ 复制到新路径
    │                       │
    ▼                       ▼
    合并 DEFAULT_SETTINGS 返回
    │
用户修改 /color /maincolor /volume 等
    │
    ▼
set_setting() / save_settings()
    │
    ▼
只写入 ~/.holle_music/settings.json
```

---

## 7. 错误处理

- 读取新/旧配置文件失败：静默忽略，继续下一级回退。
- 迁移复制失败：静默忽略，仍可从旧路径读取。
- 写入新路径失败：静默忽略，应用继续运行。
- 目录创建失败：放入 try/except，避免启动崩溃。

---

## 8. 兼容性

| 场景 | 行为 |
|---|---|
| 源码开发 | 旧配置自动迁移到新位置 |
| `pip install` | 配置写到用户目录，不需要包目录写权限 |
| PyInstaller onefile exe | 配置写到用户目录，退出后持久保留 |
| Windows / macOS / Linux | `Path.home()` 跨平台一致 |

---

## 9. 测试计划

1. **迁移测试**：只有旧路径有文件时，调用 `load_settings()` 后新路径应生成相同内容。
2. **读取优先级测试**：新路径和旧路径同时存在时，应优先使用新路径。
3. **保存测试**：调用 `set_setting()` 后，只有新路径被写入。
4. **legacy 回退测试**：只有 `.holle_color.json` 存在时，`color` 应被正确读取。
5. **默认值测试**：没有任何配置文件时，返回 `DEFAULT_SETTINGS`。

---

## 10. 风险评估

- **低风险**：改动集中在一个文件，接口不变，其他模块无感知。
- **风险点**：如果 `Path.home()` 不可写（极少数受限环境），配置无法持久化。处理方式是静默失败，不影响应用运行。

---

## 11. 后续可扩展

- 后续版本可考虑在 Windows 上使用 `%APPDATA%` 替代 `~/.holle_music`，更符合平台习惯。
- 可考虑加迁移标记文件，避免每次启动都检查旧路径。

---

*Generated during v0.3.0 brainstorming.*
