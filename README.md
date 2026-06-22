# Holle Music

一个终端命令行音乐播放器，界面类似 Claude Code 终端风格。支持播放本地音乐（MP3、FLAC 等）、AI 聊天解歌、实时频谱可视化、随机/顺序/循环播放模式。v0.2.0 新增桌面音乐助手。

## 功能特点

- 🎵 播放本地音乐（MP3、FLAC 等格式）
- ◆ **桌面音乐助手**（独立播放器，点击交互，双击查看正在播放）
- 🤖 AI 聊天（支持联网搜索，自动解说歌曲背景）
- 📊 实时音频频谱可视化
- 🎨 多种颜色主题（`/color` 命令切换）
- 🌗 深色/浅色主题（`/maincolor light|dark`）
- 🎚️ 音量随频谱闪烁
- 🔀 顺序 / 随机 / 单曲循环 播放模式
- 🖼️ 自动提取并显示专辑封面
- 💾 播放状态与设置持久化
- 🔍 B 站音频搜索（`/search` 本地无结果时自动搜索 Bilibili）
- 💾 B 站在线音频缓存与自动清理

## 安装方式

### 方式一：有 Python 环境（推荐）

```bash
pip install holle-music
hollemusic
```

### 方式二：没有 Python 环境（使用 uv）

`uv` 是一个单文件 Python 包管理器，不需要预先安装 Python：

**Windows:**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv tool install holle-music
hollemusic
```

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install holle-music
hollemusic
```

### 方式三：Windows 安装包（推荐 Windows 用户）

从 [Releases](https://github.com/Redpinkt5/Holle/releases) 下载 `HolleMusic-Setup-x.x.x.exe`：

1. 双击运行安装向导
2. 选择安装位置
3. 勾选是否创建桌面快捷方式
4. 安装完成后从桌面或开始菜单启动

安装包包含：
- **Holle Music** — 终端完整版
- **Holle 桌面助手** — 桌面音乐助手

### 方式四：独立可执行文件（无需任何环境）

从 [Releases](https://github.com/Redpinkt5/Holle/releases) 下载对应系统的可执行文件：

- **Windows**: 下载 `hollemusic.exe`，双击运行
- **macOS**: 下载 `hollemusic`，`chmod +x hollemusic` 后运行
- **Linux**: 下载 `hollemusic`，`chmod +x hollemusic` 后运行

### 方式五：从源码运行

```bash
git clone https://github.com/Redpinkt5/Holle.git
cd Holle
pip install -e .
hollemusic
```

## 使用说明

### 终端操作

启动后进入 TUI 界面，常用操作：

| 按键 | 功能 |
|------|------|
| `空格` | 播放 / 暂停 |
| `←` / `b` | 上一曲 |
| `→` / `n` | 下一曲 |
| `Tab` | 切换焦点 |
| 鼠标滚轮 | 调节音量 |

### 桌面音乐助手

点击终端底部 `◆` 按钮启动桌面音乐助手，或直接运行：

```bash
hollepet
```

**宠物交互：**
- 🖱️ **点击身体中部** — 播放/暂停
- 🖱️ **点击左侧** — 上一曲
- 🖱️ **点击右侧** — 下一曲
- 🖱️ **点击顶部** — 切换播放模式
- 🖱️ **点击底部** — 打开聊天输入框
- 🖱️ **双击** — 显示正在播放歌单
- 🖱️ **拖动** — 移动位置

### 命令列表

终端和桌面音乐助手均支持以下命令：

| 命令 | 说明 |
|------|------|
| `/play <歌名>` | 播放指定歌曲 |
| `/pause` | 暂停 |
| `/next` | 下一曲 |
| `/prev` | 上一曲 |
| `/volume <0-100>` | 调节音量 |
| `/color <颜色>` | 切换主题色（pink / blue / red / green / yellow / purple / orange / gray / brown / black / white / colorful） |
| `/maincolor <light\|dark>` | 切换助手明暗主题 |
| `/search <关键词>` | 搜索歌曲 |
| `/cache` | 查看 B 站缓存占用 |
| `/cache clear` | 清空 B 站缓存 |
| `/scan <路径>` | 扫描文件夹添加到播放列表 |
| `/help` | 查看帮助 |
| `/quit` | 退出 |

## 打包为可执行文件

如果你想自己打包独立可执行文件：

```bash
pip install pyinstaller
python scripts/build-exe.py
```

打包后的文件位于 `dist/hollemusic.exe`（Windows）或 `dist/hollemusic`（macOS/Linux）。

## 技术栈

- [Textual](https://textual.textualize.io/) — TUI 框架
- [pygame](https://www.pygame.org/) — 音频播放
- [mutagen](https://mutagen.readthedocs.io/) — 音频元数据读取
- [librosa](https://librosa.org/) — 音频频谱分析
- [Pillow](https://pillow.readthedocs.io/) — 专辑封面处理
- Ark API / OpenAI API — AI 对话
- Win32 API — 桌面音乐助手窗口

## License

MIT License
