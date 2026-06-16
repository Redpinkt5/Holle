# Holle Pet 增强设计文档

**日期**: 2025-06-11
**范围**: 桌面宠物模块 5 项增强 + 重构
**作者**: Claude Code

---

## 1. 背景与目标

Holle Music 桌面宠物（Holle Pet）当前存在以下问题与需求：

1. 闪烁效果与终端桌宠不一致（颜色少、切换过快）
2. AI 聊天使用 MiniMax API，需切换为 DeepSeek
3. 桌宠对话框（ChatDialog）打开后无法正常关闭
4. 拖拽桌宠时容易误触发点击功能
5. 模式切换和对话缺乏视觉反馈，需气泡对话框
6. 鼠标中键关闭桌宠
7. 终端与桌宠互斥显示（打开桌宠时终端退出，打开终端时桌宠关闭）

**目标**: 修复上述问题，统一终端与桌面宠物体验，赋予 AI 直接控制播放器的能力，实现终端与桌宠的互斥切换。

---

## 2. 整体架构

```
┌─────────────────────────────────────────────┐
│            PetWindow (window.py)            │
│     消息循环 │ 鼠标事件 │ 气泡生命周期管理      │
└──────┬────────────┬────────────┬─────────────┘
       │            │            │
       ▼            ▼            ▼
┌──────────┐  ┌──────────┐  ┌──────────────┐
│ Mascot   │  │ Bubble   │  │ DeepSeek     │
│ Renderer │  │ Manager  │  │ Service      │
│(renderer │  │(bubble.py)│  │(deepseek_api)│
│  .py)    │  │          │  │              │
└──────────┘  └────┬─────┘  └──────┬───────┘
                   │               │
              ┌────┴────┐     ┌────┴────┐
              ▼         ▼     ▼         ▼
         ┌────────┐ ┌──────┐ ┌──────┐ ┌──────┐
         │Mode    │ │Chat  │ │AI    │ │Web   │
         │Bubble  │ │Bubble│ │Tools │ │Search│
         └────────┘ └──────┘ └──────┘ └──────┘
```

### 2.1 组件职责

| 组件 | 文件 | 职责 |
|------|------|------|
| PetWindow | `window.py` | Win32 窗口管理、消息循环、鼠标事件、气泡生命周期 |
| MascotRenderer | `renderer.py` | 吉祥物渲染（Pillow → UpdateLayeredWindow） |
| BubbleManager | `bubble.py` | 气泡状态管理、位置计算、交互分发 |
| BubbleRenderer | `bubble_renderer.py` | 气泡视觉渲染（Pillow 绘制圆角气泡+箭头） |
| DeepSeekService | `deepseek_api.py` | DeepSeek API 封装、工具调用解析 |
| AITools | `ai_tools.py` | AI 工具执行（搜索、播放、切歌等） |
| ClickZone | `click_zone.py` | 点击区域检测（不变） |
| PetPlayer | `player_proxy.py` | IPC 播放器代理（不变） |

### 2.2 数据流

1. 用户点击桌宠 → `PetWindow._wnd_proc()` 处理鼠标事件（时间判定区分点击/拖拽）
2. 短按 + top 区域 → `BubbleManager.show_mode_bubble()`
3. 短按 + bottom 区域 → `BubbleManager.show_chat_bubble()`
4. 用户输入 → `DeepSeekService.chat()`（携带工具定义）
5. AI 返回工具调用 → `AITools.execute()` → 控制播放器
6. AI 返回文字 → 更新消息历史 → 重新渲染气泡
7. 播放状态变化 → `PetWindow` 同步闪烁效果
8. 鼠标中键点击桌宠 → 关闭桌宠，启动终端进程
9. 终端启动桌宠 → 终端退出，桌宠接管播放

---

## 3. 详细设计

### 3.1 闪烁效果同步（任务 1）

**问题**: 当前桌面宠物使用 7 色列表 `_SHIMMER_COLORS`，每 16ms 切换一次，与终端桌宠的 10 色调色板 + 0.24s 间隔不一致。

**方案**: 引入终端的调色板系统，统一闪烁逻辑。

#### 3.1.1 renderer.py 修改

```python
from holle_music.widgets import _SHIMMER_PALETTES, _SHIMMER_INTERVAL, _current_palette

class MascotRenderer:
    def render(
        self,
        direction: str,
        active: bool,
        palette_name: str = "pink",
        shimmer_idx: int = 0,
    ) -> Image.Image:
        if active:
            colors = _SHIMMER_PALETTES.get(palette_name, _SHIMMER_PALETTES["pink"])
            body_color = colors[shimmer_idx % len(colors)]
            glow_color = (*ImageColor.getrgb(body_color), 80)
        else:
            body_color = DEFAULT_BODY_COLOR
            glow_color = None
        ...
```

#### 3.1.2 window.py 修改

```python
def _update_animation(self) -> None:
    if not self._active:
        return
    now = time.monotonic()
    if now - self._last_shimmer_update >= _SHIMMER_INTERVAL:
        palette = _SHIMMER_PALETTES.get(_current_palette, _SHIMMER_PALETTES["pink"])
        self._shimmer_idx = (self._shimmer_idx + 1) % len(palette)
        self._last_shimmer_update = now
        self._update_display()
```

**关键参数**:
- 切换间隔: `_SHIMMER_INTERVAL` = 0.24s
- 调色板: 复用 `_SHIMMER_PALETTES`（12 种主题，每种 10 色）
- 当前主题: 复用 `_current_palette` 全局变量

---

### 3.2 DeepSeek AI 工具系统（任务 2）

**目标**: 完全替换 MiniMax，接入 DeepSeek API，支持工具调用（Function Calling）。

#### 3.2.1 API 配置

```python
DEEPSEEK_API_KEY = "sk-cd27a7afd2984405a7bb441d35b99522"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
```

#### 3.2.2 系统提示词

```
你是 Holle Music 的桌面宠物 AI 助手，可以直接控制音乐播放器。

工具列表：
- search_local: 本地歌单搜索
- search_web: 联网搜索歌曲/歌手信息
- play_song: 播放指定歌曲
- toggle_play: 播放/暂停
- next_track / prev_track: 切歌
- set_volume: 调节音量 (0-100)
- set_mode: 切换模式 (sequential/random/repeat)
- get_current_song: 获取当前播放
- get_playlist: 获取播放列表

规则：
1. 播放歌曲时先 search_local，找到后 play_song
2. 本地没有时告知用户，可 search_web 提供信息
3. 切换模式前询问确认（除非用户明确指令）
4. 用简洁友好的中文回复，不使用 Markdown
```

#### 3.2.3 工具定义

| 工具名 | 参数 | 描述 |
|--------|------|------|
| search_local | query: string | 在本地播放列表搜索 |
| search_web | query: string | 联网搜索 |
| play_song | title: string, artist?: string | 播放指定歌曲 |
| toggle_play | 无 | 播放/暂停切换 |
| next_track | 无 | 下一曲 |
| prev_track | 无 | 上一曲 |
| set_volume | volume: integer (0-100) | 设置音量 |
| set_mode | mode: enum (sequential/random/repeat) | 切换模式 |
| get_current_song | 无 | 获取当前播放 |
| get_playlist | 无 | 获取播放列表 |

#### 3.2.4 对话流程

```
用户输入
    ↓
DeepSeekService.chat(message, tools)
    ↓
┌──────────────┬──────────────┐
▼              ▼              ▼
文字回复    工具调用请求    工具调用+后续
    ↓            ↓                ↓
显示气泡   AITools.execute()   结果返回AI
                ↓                ↓
           执行播放器操作     AI生成最终回复
                ↓                ↓
           结果返回AI          显示气泡
                ↓
           AI生成回复
                ↓
           显示气泡
```

**关键**: 支持多轮工具调用链（如先搜索再播放）。

#### 3.2.5 IPC 命令扩展

为支持 AI 工具调用，扩展 `pet_cmd.json` 命令格式：

```json
{"cmd": "play:<song_title>", "time": 1234567890}
{"cmd": "volume:<0-100>", "time": 1234567890}
{"cmd": "mode:<mode_name>", "time": 1234567890}
```

`app.py` 的 `_read_pet_cmd()` 需解析带参数的 cmd。

---

### 3.3 鼠标事件时间判定（任务 4）

**问题**: 当前仅按移动距离（>3px）判定拖拽，轻微抖动即误触。

**方案**: 增加时间判定，短按（<200ms）算点击，长按算拖拽。

#### 3.3.1 实现

```python
def __init__(self, ...):
    self._drag_start_time = 0.0

def _wnd_proc(self, hwnd, msg, wparam, lparam):
    if msg == win32con.WM_LBUTTONDOWN:
        ...
        self._drag_start_time = time.monotonic()
        return 0

    if msg == win32con.WM_LBUTTONUP:
        ...
        press_duration = time.monotonic() - self._drag_start_time
        is_click = (not self._drag_has_moved) and (press_duration < 0.2)
        if is_click and self._drag_click_pos:
            zone = self._click_zone.detect(x, y, *self._size)
            if zone:
                self._handle_click(zone)
        ...
```

**判定矩阵**:

| 持续时间 | 移动距离 | 结果 |
|---------|---------|------|
| < 200ms | < 3px | ✅ 触发点击 |
| < 200ms | > 3px | ❌ 拖拽（不触发） |
| > 200ms | 任意 | ❌ 拖拽（不触发） |

---

### 3.4 Win32 气泡系统（任务 3 + 5）

**目标**: 替换独立 tkinter 对话框，改为与桌宠视觉统一的 Win32 层叠气泡。

#### 3.4.1 气泡类型

| 类型 | 触发 | 内容 | 交互 | 自动消失 |
|------|------|------|------|---------|
| ModeBubble | 点击 top | 模式切换确认 | 确认/取消按钮 | 3秒无操作 |
| ChatBubble | 点击 bottom | 对话历史 | 输入框+发送 | 不自动消失 |

#### 3.4.2 渲染策略

- **气泡背景**: Pillow 绘制圆角矩形 + 箭头，通过 `UpdateLayeredWindow` 显示
- **文字**: Pillow 绘制（限制：无复杂排版）
- **按钮**: Pillow 绘制色块 + 文字，点击检测通过坐标判断
- **输入框**: 聊天气泡底部嵌入 tkinter Entry（避免重写文本编辑器）

#### 3.4.3 气泡窗口属性

```python
ex_style = (
    WS_EX_LAYERED      # 透明
    | WS_EX_TOOLWINDOW # 不在任务栏显示
    | WS_EX_TOPMOST    # 置顶
    | WS_EX_NOACTIVATE # 不抢夺焦点
)
style = WS_POPUP  # 无边框
```

#### 3.4.4 位置计算

```python
# 默认显示在桌宠上方居中
bubble_x = pet_x + pet_width // 2 - bubble_width // 2
bubble_y = pet_y - bubble_height - 5

# 边界检查：超出屏幕顶部则显示在桌宠下方
if bubble_y < 0:
    bubble_y = pet_y + pet_height + 5
```

#### 3.4.5 交互流程

**模式切换气泡**:
```
点击 top → show_mode_bubble(current, target)
    ↓
渲染气泡（确认/取消按钮）
    ↓
点击"确认" → on_action("top") → 发送 mode IPC → 气泡消失
点击"取消" → 气泡消失
3秒无操作 → 自动消失
```

**聊天气泡**:
```
点击 bottom → show_chat_bubble(messages)
    ↓
渲染气泡 + 嵌入 tkinter Entry
    ↓
用户输入 → Enter → 添加到历史 → DeepSeekService.chat()
    ↓
AI 回复 → 更新历史 → 重新渲染气泡
    ↓
（循环继续，气泡保持打开）
    ↓
点击外部 / Escape / 关闭按钮 → 气泡消失
```

#### 3.4.6 关闭机制（解决任务 3）

气泡关闭方式：
1. 点击气泡外部区域（通过全局鼠标位置检测）
2. 按 Escape 键
3. 模式气泡的"取消"按钮
4. 模式气泡 3 秒无操作自动消失
5. 聊天气泡的关闭按钮（✕）

---

### 3.5 鼠标中键关闭桌宠（任务 6）

**目标**: 鼠标中键（滚轮按下）点击桌宠时，关闭桌宠并切换回终端。

#### 3.5.1 实现

```python
def _wnd_proc(self, hwnd, msg, wparam, lparam):
    ...
    if msg == win32con.WM_MBUTTONDOWN:
        # 中键关闭桌宠，触发切换回终端
        self._switch_back_to_terminal()
        return 0

def _switch_back_to_terminal(self) -> None:
    """关闭桌宠，启动终端进程。"""
    # 保存当前位置
    self._save_position()
    # 启动终端进程
    import subprocess
    import sys
    subprocess.Popen(
        [sys.executable, "-m", "holle_music"],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # 关闭桌宠
    self.close()
```

**注意**: 使用 `DETACHED_PROCESS` 确保终端进程独立于桌宠进程，避免父子进程关系导致桌宠等待终端退出。

---

### 3.6 终端与桌宠互斥显示（任务 7）

**目标**: 终端和桌宠只能有一个在前台运行，切换时保持播放连续性。

#### 3.6.1 互斥切换流程

**终端 → 桌宠**:
```
用户点击终端"🐾"按钮
    ↓
终端保存完整播放状态到 pet_state.json
    ↓
终端启动桌宠（非 daemon 子进程）
    ↓
终端 TUI 退出（self.exit()）
    ↓
桌宠读取 pet_state.json 恢复播放
```

**桌宠 → 终端**:
```
用户中键点击桌宠 / 右键"切换回终端"
    ↓
桌宠保存位置到 pet_pos.json
    ↓
桌宠保存播放状态到 pet_state.json
    ↓
桌宠启动终端进程（subprocess.Popen）
    ↓
桌宠关闭
    ↓
终端读取状态恢复播放
```

#### 3.6.2 状态保存扩展

`pet_state.json` 需扩展以支持完整恢复：

```json
{
  "playing": true,
  "song": {"title": "...", "artist": "...", "path": "..."},
  "mode": "random",
  "volume": 0.8,
  "position": 120.5,
  "playlist": [...],
  "time": 1234567890
}
```

#### 3.6.3 终端启动桌宠改造

`app.py` 的 `on_controls_pet_launch` 需修改：

```python
@on(Controls.PetLaunch)
def on_controls_pet_launch(self, event: Controls.PetLaunch) -> None:
    # 保存完整状态
    self._write_full_pet_state()
    
    # 启动桌宠子进程（非 daemon）
    import subprocess
    subprocess.Popen(
        [sys.executable, "-m", "holle_music.pet"],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    # 退出终端
    self._notify_chat("🐾 桌宠已启动，终端即将退出...")
    self.exit()
```

#### 3.6.4 桌宠入口改造

`pet/main.py` 需支持从状态恢复：

```python
def main() -> None:
    player = PetPlayer()
    
    # 尝试从终端保存的状态恢复
    state = player.get_state()
    if state.get("playlist"):
        player.load_playlist(state["playlist"])
        if state.get("song"):
            # 恢复播放位置
            player.seek(state.get("position", 0))
            if state.get("playing"):
                player.play()
    
    chat = ChatDialog()
    window = PetWindow(on_action=on_action, dialog=chat)
    
    # 同步播放状态用于闪烁
    window._on_player_state_check = lambda: player.is_playing
    
    print("Holle Pet started!")
    window.show()
```

#### 3.6.5 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 进程关系 | 独立进程（非 daemon） | 终端退出后桌宠继续运行 |
| 状态同步 | `pet_state.json` 文件 | 简单可靠，无需网络/管道 |
| 启动方式 | `subprocess.Popen` + `DETACHED_PROCESS` | Windows 独立进程标准做法 |
| 播放恢复 | 恢复歌单 + 当前歌曲 + 播放位置 | 用户体验无缝切换 |

---

## 4. 文件变更清单

### 4.1 新增文件

| 文件 | 描述 |
|------|------|
| `src/holle_music/pet/deepseek_api.py` | DeepSeek API 封装 + 工具定义 |
| `src/holle_music/pet/ai_tools.py` | AI 工具执行器 |
| `src/holle_music/pet/bubble.py` | 气泡管理器（状态+位置+交互） |
| `src/holle_music/pet/bubble_renderer.py` | 气泡视觉渲染（Pillow） |

### 4.2 修改文件

| 文件 | 变更 |
|------|------|
| `src/holle_music/pet/renderer.py` | 引入调色板系统，支持 palette_name/shimmer_idx |
| `src/holle_music/pet/window.py` | 时间判定、气泡集成、闪烁同步 |
| `src/holle_music/pet/main.py` | 集成 DeepSeekService 和 AITools，支持状态恢复 |
| `src/holle_music/pet/chat_dialog.py` | **删除或弃用**，功能迁移到气泡系统 |
| `src/holle_music/app.py` | 扩展 IPC 命令解析，启动桌宠后退出终端 |
| `src/holle_music/pet/window.py` | 中键关闭、互斥切换逻辑 |

---

## 5. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Win32 气泡输入框焦点问题 | 高 | tkinter Entry 使用 `-topmost` + 气泡窗口 `NOACTIVATE` |
| DeepSeek 工具调用不稳定 | 中 | 加重试机制（同 MiniMax 的 3 次重试） |
| 气泡渲染性能 | 低 | 仅在有变化时重绘，使用 Pillow 缓存 |
| IPC 命令扩展兼容性 | 低 | 保持旧命令格式，新命令带参数前缀 |

---

## 6. 测试要点

- [ ] 闪烁效果与终端一致（同调色板、同间隔）
- [ ] DeepSeek 对话正常响应
- [ ] AI 搜索本地歌曲并播放
- [ ] AI 切换播放模式
- [ ] 拖拽桌宠不触发点击（短按 <200ms 触发，长按不触发）
- [ ] 模式气泡：确认/取消/自动消失
- [ ] 聊天气泡：输入、AI 回复、关闭、Escape
- [ ] 气泡位置不超出屏幕边界
- [ ] 旧 IPC 命令（toggle/next/prev/mode）保持兼容
- [ ] 鼠标中键关闭桌宠
- [ ] 终端启动桌宠后终端退出
- [ ] 桌宠关闭后终端自动启动
- [ ] 切换前后播放状态保持一致（歌曲、位置、模式、音量）
