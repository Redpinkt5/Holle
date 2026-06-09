# Holle Music 桌面宠物设计文档

> 将 Holle Music 的 ASCII 吉祥物做成 Windows 桌面宠物，支持独立运行和与主程序联动。

---

## 目标

创建一个轻量级 Windows 桌面宠物，复用现有 ASCII 吉祥物形象（菱形 + 追踪眼），支持：

1. **点击中间身体** → 播放 / 暂停
2. **点击左右两侧** → 上一曲 / 下一曲
3. **点击头顶** → 切换播放模式（顺序 ⭢ / 随机 ↬ / 单曲 ⟳）
4. **点击身体底部** → 弹出 AI 对话框，与 MiniMax 对话
5. **眼睛实时追踪鼠标**
6. **独立运行** 或 **与主程序联动**

---

## 技术方案

**pywin32 + Pillow**

- `pywin32`：创建原生 Windows 无边框/置顶/透明/异形窗口
- `Pillow`：将 ASCII 吉祥物实时渲染为带透明通道的 PNG
- `tkinter`：AI 对话框（标准库，无需额外依赖）

---

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                    Desktop Pet (独立进程)                  │
│  ┌─────────────────────────────────────────────────┐    │
│  │  PetWindow (pywin32)                             │    │
│  │  - WS_EX_LAYERED + WS_EX_TRANSPARENT             │    │
│  │  - 无边框、置顶、透明背景                         │    │
│  │  - 鼠标事件：Click / Move / Drag                 │    │
│  │  - 位置记忆（注册表/配置文件）                     │    │
│  │                                                  │    │
│  │  ┌─────────────────────────────────────────┐    │    │
│  │  │  MascotRenderer (Pillow)                 │    │    │
│  │  │  - _BODY + _EYES → 彩色 PNG              │    │    │
│  │  │  - _calc_direction → 眼睛方向            │    │    │
│  │  │  - shimmer → 播放状态闪烁                │    │    │
│  │  │  - blink → 随机眨眼                      │    │    │
│  │  └─────────────────────────────────────────┘    │    │
│  │                                                  │    │
│  │  ┌─────────────────────────────────────────┐    │    │
│  │  │  ClickZone                               │    │    │
│  │  │  - 头顶 20% → mode_change                │    │    │
│  │  │  - 中间 40% → toggle_play                │    │    │
│  │  │  - 左侧 20% → prev                       │    │    │
│  │  │  - 右侧 20% → next                       │    │    │
│  │  │  - 底部边缘 → chat_dialog                │    │    │
│  │  └─────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────┘    │
│                          ↕ IPC                           │
│  ┌─────────────────────────────────────────────────┐    │
│  │  PetPlayer + IPC                                 │    │
│  │  - 独立模式：直接 import Player 播放             │    │    │
│  │  - 联动模式：读写 ~/.holle_music/pet_state.json  │    │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  ChatDialog (tkinter)                            │    │
│  │  - 浮动输入框                                     │    │    │
│  │  - MiniMaxService.chat()                         │    │    │
│  │  - 气泡回复（Pillow 绘制）                       │    │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

---

## 模块设计

### 1. MascotRenderer（`pet/renderer.py`）

复用 `widgets.py` 中的 `_BODY`、`_EYES`、`_calc_direction`，用 Pillow 渲染。

```python
class MascotRenderer:
    """Render ASCII mascot as transparent PNG with mouse-tracking eyes."""

    COLS: int = 14
    ROWS: int = 7
    CELL_SIZE: int = 12  # pixels per ASCII cell
    
    def render(self, direction: str, active: bool, shimmer_color: str) -> Image.Image:
        """Generate RGBA mascot image."""
        
    def _draw_body(self, draw: ImageDraw.Draw, color: str) -> None:
        """Draw diamond body from _BODY template."""
        
    def _draw_eyes(self, draw: ImageDraw.Draw, direction: str) -> None:
        """Draw eyes at position from _EYES[direction]."""
        
    def _draw_shimmer(self, img: Image.Image, color: str) -> None:
        """Apply shimmer overlay when playing."""
```

**眼睛追踪流程：**

```
win32api.GetCursorPos() → screen coordinates
    ↓
window_rect = GetWindowRect(hwnd)
mouse_rel_x = cursor_x - window_rect.left - window_width/2
mouse_rel_y = cursor_y - window_rect.top - window_height/2
    ↓
_calc_direction(mouse_rel_x, mouse_rel_y) → "center"/"left"/"up"...
    ↓
_EYES[direction] → eye positions
    ↓
render() → new PNG
    ↓
UpdateLayeredWindow(hwnd, 0, 0, new_png)
```

**性能：** 100×100 PNG 生成 < 1ms，60fps 轻松。

---

### 2. PetWindow（`pet/window.py`）

```python
class PetWindow:
    """Windows layered window for desktop pet."""

    def __init__(self, renderer: MascotRenderer) -> None:
        self._hwnd = self._create_window()
        self._renderer = renderer
        self._dragging = False
        self._drag_offset = (0, 0)

    def _create_window(self) -> int:
        """Create WS_EX_LAYERED window, return hwnd."""
        # Register class
        # CreateWindowEx(WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_TOPMOST)
        # SetLayeredWindowAttributes(hwnd, RGB(0,0,0), 0, LWA_COLORKEY)

    def _on_mouse_move(self, x: int, y: int) -> None:
        """Update eye direction, handle drag."""
        
    def _on_click(self, x: int, y: int) -> None:
        """Detect click zone and dispatch action."""
        
    def _on_right_click(self, x: int, y: int) -> None:
        """Show context menu: hide, settings, quit."""
        
    def show(self) -> None:
        """Show window and start message loop."""
        
    def hide(self) -> None:
        """Hide to system tray."""
        
    def move(self, x: int, y: int) -> None:
        """Move window to position, save to config."""
```

**窗口样式：**

- `WS_EX_LAYERED`：支持透明 PNG
- `WS_EX_TOOLWINDOW`：不出现在任务栏
- `WS_EX_TOPMOST`：始终置顶
- `WS_POPUP`：无边框
- `LWA_COLORKEY`：黑色透明（或直接用 `UpdateLayeredWindow` 的 BLENDFUNCTION）

**点击穿透：**

非吉祥物区域（透明部分）需要穿透点击，让鼠标能点到下面的桌面图标。用 `SetWindowRgn` 设置不规则窗口区域，或者处理 `WM_NCHITTEST` 返回 `HTTRANSPARENT`。

---

### 3. ClickZone（点击区域）

```python
class ClickZone:
    """Map click coordinates to actions."""

    ZONES = {
        "top":    (0.0, 0.0, 1.0, 0.2),   # x1, y1, x2, y2 (normalized)
        "left":   (0.0, 0.2, 0.2, 0.8),
        "center": (0.2, 0.2, 0.8, 0.8),
        "right":  (0.8, 0.2, 1.0, 0.8),
        "bottom": (0.2, 0.8, 0.8, 1.0),
    }

    def detect(self, x: int, y: int, width: int, height: int) -> str:
        """Return zone name or empty string."""
        nx, ny = x / width, y / height
        for name, (x1, y1, x2, y2) in self.ZONES.items():
            if x1 <= nx < x2 and y1 <= ny < y2:
                return name
        return ""
```

| 区域 | 相对坐标 | 动作 |
|------|---------|------|
| top | (0,0) → (1,0.2) | 切换播放模式 |
| left | (0,0.2) → (0.2,0.8) | 上一曲 |
| center | (0.2,0.2) → (0.8,0.8) | 播放/暂停 |
| right | (0.8,0.2) → (1,0.8) | 下一曲 |
| bottom | (0.2,0.8) → (0.8,1.0) | 打开 AI 对话框 |

---

### 4. PetPlayer + IPC（`pet/player_proxy.py`）

```python
class PetPlayer:
    """Play music in standalone mode, or proxy to main app."""

    STATE_FILE = Path.home() / ".holle_music" / "pet_state.json"
    CMD_FILE = Path.home() / ".holle_music" / "pet_cmd.json"

    def __init__(self) -> None:
        self._standalone = not self._is_main_app_running()
        self._player: Player | None = None
        if self._standalone:
            self._player = Player()

    def _is_main_app_running(self) -> bool:
        """Check if pet_state.json was updated in last 5 seconds."""
        
    def toggle_play(self) -> None:
        if self._standalone:
            self._player.toggle_play_pause()
        else:
            self._send_cmd("toggle")
            
    def next_track(self) -> None:
        if self._standalone:
            self._player.next()
        else:
            self._send_cmd("next")
            
    def prev_track(self) -> None:
        if self._standalone:
            self._player.previous()
        else:
            self._send_cmd("prev")
            
    def cycle_mode(self) -> None:
        if self._standalone:
            # Direct mode change
            pass
        else:
            self._send_cmd("mode")

    def _send_cmd(self, cmd: str) -> None:
        """Write command to IPC file for main app to read."""
        self.CMD_FILE.write_text(json.dumps({"cmd": cmd, "time": time.time()}))
        
    def get_state(self) -> dict:
        """Read current playback state."""
        if self._standalone:
            return {
                "playing": self._player.is_playing,
                "song": self._player.current_song,
                "mode": self._player.play_mode,
            }
        else:
            if self.STATE_FILE.exists():
                return json.loads(self.STATE_FILE.read_text())
            return {}
```

**主程序侧改动：**

在 `app.py` 的 `on_mount` 中启动一个定时器，每秒写入 `pet_state.json`：

```python
def _write_pet_state(self) -> None:
    state = {
        "playing": self.player.is_playing,
        "song": {
            "title": self.player.current_song.title if self.player.current_song else "",
            "artist": self.player.current_song.artist if self.player.current_song else "",
        },
        "mode": self.player.play_mode,
        "time": time.time(),
    }
    # write to ~/.holle_music/pet_state.json
```

同时监听 `pet_cmd.json`，收到命令后执行：

```python
def _read_pet_cmd(self) -> None:
    # check pet_cmd.json
    # execute command and delete file
```

---

### 5. ChatDialog（`pet/chat_dialog.py`）

```python
class ChatDialog:
    """Floating chat dialog for desktop pet."""

    def __init__(self, parent_hwnd: int) -> None:
        self._window = tkinter.Toplevel()
        self._window.overrideredirect(True)  # 无边框
        self._window.attributes("-topmost", True)
        self._service = MiniMaxService()

    def show(self, x: int, y: int) -> None:
        """Show dialog below the pet."""
        self._window.geometry(f"300x200+{x}+{y+100}")
        self._window.deiconify()

    def _on_send(self) -> None:
        """Send message to MiniMax, show reply."""
        text = self._input.get()
        self._add_bubble(text, "user")
        
        def _run():
            reply = self._service.chat(text)
            self._window.after(0, lambda: self._add_bubble(reply, "ai"))
        threading.Thread(target=_run, daemon=True).start()

    def _add_bubble(self, text: str, role: str) -> None:
        """Add chat bubble to dialog."""
```

**UI 样式：**

- 圆角矩形窗口（`Canvas` 绘制圆角 + 背景色）
- 底部输入框 + 发送按钮
- 用户消息右对齐（蓝色气泡）
- AI 消息左对齐（灰色气泡）
- 按 `Esc` 或点击外部关闭

---

## 文件结构

```
src/holle_music/
├── pet/
│   ├── __init__.py          # 包初始化
│   ├── renderer.py          # MascotRenderer
│   ├── window.py            # PetWindow (pywin32)
│   ├── player_proxy.py      # PetPlayer + IPC
│   ├── chat_dialog.py       # ChatDialog (tkinter)
│   └── main.py              # 桌宠入口: main()
├── app.py                   # 主程序（增加 IPC 定时器）
├── player.py                # 播放引擎（无改动）
├── minimax_api.py           # AI 服务（无改动）
└── widgets.py               # TUI 组件（无改动）
```

## 入口点

```toml
[project.scripts]
Holle = "holle_music.app:main"
HollePet = "holle_music.pet.main:main"
```

## 新增依赖

```toml
dependencies = [
    # ... existing deps
    "pywin32>=306; platform_system=='Windows'",
]
```

---

## 测试计划

1. **渲染测试**：`python -m holle_music.pet.renderer` → 生成 mascot.png 验证视觉效果
2. **窗口测试**：`python -m holle_music.pet.window` → 验证无边框/置顶/透明
3. **点击测试**：`HollePet` → 点击各区域，验证动作正确
4. **IPC 测试**：同时运行 `Holle` 和 `HollePet` → 验证联动
5. **对话测试**：点击底部 → 输入问题 → 验证 MiniMax 回复

---

## 风险评估

| 风险 | 可能性 | 缓解措施 |
|------|--------|---------|
| pywin32 API 复杂 | 中 | 先写最小可运行窗口原型 |
| 异形窗口点击穿透 | 中 | 用 `SetWindowRgn` 精确裁剪 |
| IPC 文件竞争 | 低 | 用文件锁或原子写入 |
| tkinter 对话框风格不统一 | 低 | 用 Canvas 自绘圆角 |
