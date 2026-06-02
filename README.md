# Holle Music

一个终端命令行音乐播放器，界面类似 Claude Code 终端风格。支持播放本地音乐（MP3、FLAC 等）、AI 聊天解歌、实时频谱可视化、随机/顺序/循环播放模式。

## 功能特点

- 🎵 播放本地音乐（MP3、FLAC 等格式）
- 🤖 AI 聊天（支持联网搜索，自动解说歌曲背景）
- 📊 实时音频频谱可视化
- 🎨 多种颜色主题（`/color` 命令切换）
- 🎚️ 8 段均衡器
- 🔀 随机 / 顺序 / 单曲循环 播放模式
- 🖼️ 自动提取并显示专辑封面

## 安装方式

### 方式一：有 Python 环境（推荐）

```bash
pip install holle-music
Holle
```

### 方式二：没有 Python 环境（使用 uv）

`uv` 是一个单文件 Python 包管理器，不需要预先安装 Python：

**Windows:**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv tool install holle-music
Holle
```

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install holle-music
Holle
```

### 方式三：独立可执行文件（无需任何环境）

从 [Releases](https://github.com/Redpinkt5/Holle/releases) 下载对应系统的可执行文件：

- **Windows**: 下载 `hollemusic.exe`，双击运行
- **macOS**: 下载 `hollemusic`，`chmod +x hollemusic` 后运行
- **Linux**: 下载 `hollemusic`，`chmod +x hollemusic` 后运行

### 方式四：从源码运行

```bash
git clone https://github.com/Redpinkt5/Holle.git
cd Holle
pip install -e .
Holle
```

## 使用说明

启动后进入 TUI 界面，常用操作：

| 按键 | 功能 |
|------|------|
| `空格` | 播放 / 暂停 |
| `←` / `b` | 上一曲 |
| `→` / `n` | 下一曲 |
| `Tab` | 切换焦点 |

命令行输入区支持以下命令：

| 命令 | 说明 |
|------|------|
| `/play <歌名>` | 播放指定歌曲 |
| `/pause` | 暂停 |
| `/next` | 下一曲 |
| `/prev` | 上一曲 |
| `/volume <0-100>` | 调节音量 |
| `/color <颜色>` | 切换主题色（pink / blue / red / green / yellow / purple / orange / gray / brown / black / white / colorful） |
| `/search <关键词>` | 搜索歌曲 |
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
- OpenAI API / SiliconFlow — AI 对话

## License

MIT License
