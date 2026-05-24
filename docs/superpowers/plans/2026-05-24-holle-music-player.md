# Holle Music 播放器 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个终端命令行音乐/电台播放器，具有类似 Claude Code 的 Textual TUI 界面，支持本地音乐播放、歌单管理和电台流播放。

**Architecture:** 使用 Python 3.10+ 和 Textual 框架构建 TUI 界面，pygame.mixer 作为音频引擎，mutagen 读取元数据。整体采用 MVC 模式：models.py 定义数据层，player.py 处理音频逻辑，widgets.py 负责 UI 组件，app.py 作为主控制器整合所有模块。

**Tech Stack:** Python 3.10+, Textual 0.40+, pygame, mutagen, pytest

---

## 文件结构

```
E:\DDDESKKKK\holle_music\
├── pyproject.toml                 # 项目配置，依赖，入口点
├── README.md                      # (已存在) 设计文档
├── src/
│   └── holle_music/
│       ├── __init__.py            # 包初始化
│       ├── __main__.py            # 支持 python -m holle_music
│       ├── app.py                 # Textual App 主类，Grid 布局，键盘快捷键，命令路由
│       ├── models.py              # Song, Playlist 数据类
│       ├── scanner.py             # 音乐文件扫描器 (MP3/FLAC)
│       ├── player.py              # 音频播放引擎 (pygame.mixer 封装)
│       └── widgets.py             # 所有 UI 组件 (6 个面板)
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_scanner.py
    ├── test_player.py
    └── test_commands.py
```

**职责划分:**
- `models.py` — Song(路径、标题、艺术家、专辑、时长) 和 Playlist(名称、歌曲列表) 两个纯数据类，无逻辑
- `scanner.py` — 递归扫描目录，过滤 MP3/FLAC/WAV，使用 mutagen 提取元数据，返回歌曲列表
- `player.py` — 封装 pygame.mixer.music，提供 play/pause/resume/stop/next/prev/set_volume，通过回调通知 UI 状态变化
- `widgets.py` — 6 个 Textual 自定义 Widget：AlbumCover、LyricsPanel、PlaylistPanel、Controls、Visualizer、CommandInput
- `app.py` — Textual App 子类，compose() 构建 3×3 Grid 布局，on_mount() 初始化扫描器和播放器，处理键盘事件和命令

---

### Task 1: 项目脚手架搭建

**Files:**
- Create: `pyproject.toml`
- Create: `src/holle_music/__init__.py`
- Create: `src/holle_music/__main__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: 编写 pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "holle-music"
version = "0.1.0"
description = "终端命令行音乐/电台播放器"
requires-python = ">=3.10"
dependencies = [
    "textual>=0.40.0",
    "pygame>=2.5.0",
    "mutagen>=1.47.0",
]

[project.scripts]
hollemusic = "holle_music.app:main"

[project.optional-dependencies]
dev = ["pytest>=7.0.0", "pytest-asyncio>=0.23.0"]
```

- [ ] **Step 2: 创建包初始化文件**

`src/holle_music/__init__.py`:
```python
"""Holle Music — 终端音乐/电台播放器."""

__version__ = "0.1.0"
```

`src/holle_music/__main__.py`:
```python
"""支持 python -m holle_music 运行."""

from holle_music.app import main

main()
```

`tests/__init__.py`:
```python
"""Holle Music 测试套件."""
```

- [ ] **Step 3: 安装项目到虚拟环境**

```bash
cd E:/DDDESKKKK/holle_music
pip install -e ".[dev]"
```
Expected: 成功安装 textual, pygame, mutagen 及开发依赖

- [ ] **Step 4: 验证导入**

```bash
python -c "from holle_music import __version__; print(__version__)"
python -c "import textual; print(textual.__version__)"
python -c "import pygame; print(pygame.version.ver)"
python -c "import mutagen; print(mutagen.version_string)"
```
Expected: 输出版本号，无 ImportError

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/holle_music/__init__.py src/holle_music/__main__.py tests/__init__.py
git commit -m "chore: scaffold project with pyproject.toml and package structure"
```

---

### Task 2: 数据模型 (Song 和 Playlist)

**Files:**
- Create: `src/holle_music/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: 编写模型测试**

`tests/test_models.py`:
```python
"""Tests for Song and Playlist models."""

from pathlib import Path
from holle_music.models import Song, Playlist


class TestSong:
    def test_create_song_with_minimal_fields(self):
        song = Song(path=Path("/music/test.mp3"))
        assert song.path == Path("/music/test.mp3")
        assert song.title == "test"  # 从文件名推断
        assert song.artist == "未知艺术家"
        assert song.album == "未知专辑"
        assert song.duration == 0.0

    def test_create_song_with_all_fields(self):
        song = Song(
            path=Path("/music/song.flac"),
            title="测试歌曲",
            artist="测试歌手",
            album="测试专辑",
            duration=245.5,
        )
        assert song.title == "测试歌曲"
        assert song.artist == "测试歌手"
        assert song.album == "测试专辑"
        assert song.duration == 245.5

    def test_song_title_from_filename(self):
        song = Song(path=Path("/music/周杰伦 - 晴天.mp3"))
        assert song.title == "周杰伦 - 晴天"

    def test_song_equality(self):
        s1 = Song(path=Path("/a.mp3"))
        s2 = Song(path=Path("/a.mp3"))
        s3 = Song(path=Path("/b.mp3"))
        assert s1 == s2
        assert s1 != s3


class TestPlaylist:
    def test_create_empty_playlist(self):
        pl = Playlist(name="我的歌单")
        assert pl.name == "我的歌单"
        assert len(pl.songs) == 0

    def test_add_song_to_playlist(self):
        pl = Playlist(name="测试")
        song = Song(path=Path("/music/a.mp3"))
        pl.add_song(song)
        assert len(pl.songs) == 1
        assert pl.songs[0] == song

    def test_remove_song_from_playlist(self):
        pl = Playlist(name="测试")
        song = Song(path=Path("/music/a.mp3"))
        pl.add_song(song)
        pl.remove_song(song)
        assert len(pl.songs) == 0

    def test_playlist_iteration(self):
        pl = Playlist(name="测试")
        songs = [
            Song(path=Path(f"/music/{i}.mp3"))
            for i in range(3)
        ]
        for s in songs:
            pl.add_song(s)
        assert list(pl) == songs
        assert len(pl) == 3
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/test_models.py -v
```
Expected: 全部 FAIL — 模型类未定义

- [ ] **Step 3: 实现数据模型**

`src/holle_music/models.py`:
```python
"""Holle Music 数据模型."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(eq=False)
class Song:
    """一首歌曲."""

    path: Path
    title: str = ""
    artist: str = "未知艺术家"
    album: str = "未知专辑"
    duration: float = 0.0

    def __post_init__(self):
        if isinstance(self.path, str):
            self.path = Path(self.path)
        if not self.title:
            self.title = self.path.stem

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Song):
            return NotImplemented
        return self.path == other.path

    def __hash__(self) -> int:
        return hash(self.path)


class Playlist:
    """歌单，包含多首歌曲."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._songs: list[Song] = []

    @property
    def songs(self) -> list[Song]:
        return list(self._songs)

    def add_song(self, song: Song) -> None:
        if song not in self._songs:
            self._songs.append(song)

    def remove_song(self, song: Song) -> None:
        if song in self._songs:
            self._songs.remove(song)

    def __iter__(self):
        return iter(self._songs)

    def __len__(self) -> int:
        return len(self._songs)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/test_models.py -v
```
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add src/holle_music/models.py tests/test_models.py
git commit -m "feat: add Song and Playlist data models"
```

---

### Task 3: 音乐文件扫描器

**Files:**
- Create: `src/holle_music/scanner.py`
- Create: `tests/test_scanner.py`

- [ ] **Step 1: 编写扫描器测试**

`tests/test_scanner.py`:
```python
"""Tests for music file scanner."""

import tempfile
from pathlib import Path
from holle_music.scanner import Scanner
from holle_music.models import Song


class TestScanner:
    def test_scan_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            scanner = Scanner()
            songs = scanner.scan(Path(tmp))
            assert songs == []

    def test_scan_directory_with_mp3_files(self, tmp_path: Path):
        (tmp_path / "song1.mp3").touch()
        (tmp_path / "song2.mp3").touch()
        (tmp_path / "not_music.txt").touch()

        scanner = Scanner()
        songs = scanner.scan(tmp_path)

        assert len(songs) == 2
        titles = {s.title for s in songs}
        assert titles == {"song1", "song2"}

    def test_scan_supports_flac_and_wav(self, tmp_path: Path):
        (tmp_path / "a.flac").touch()
        (tmp_path / "b.wav").touch()
        (tmp_path / "c.ogg").touch()

        scanner = Scanner()
        songs = scanner.scan(tmp_path)

        assert len(songs) == 2  # ogg 不被支持
        extensions = {s.path.suffix for s in songs}
        assert extensions == {".flac", ".wav"}

    def test_scan_recursive_directories(self, tmp_path: Path):
        (tmp_path / "rock").mkdir()
        (tmp_path / "rock" / "song.mp3").touch()
        (tmp_path / "jazz").mkdir()
        (tmp_path / "jazz" / "tune.flac").touch()

        scanner = Scanner()
        songs = scanner.scan(tmp_path)

        assert len(songs) == 2

    def test_scan_to_playlist(self, tmp_path: Path):
        (tmp_path / "test.mp3").touch()

        scanner = Scanner()
        playlist = scanner.scan_to_playlist(tmp_path, name="我的音乐")

        assert playlist.name == "我的音乐"
        assert len(playlist) == 1
        assert playlist.songs[0].title == "test"

    def test_supported_extensions(self):
        scanner = Scanner()
        exts = scanner.supported_extensions
        assert ".mp3" in exts
        assert ".flac" in exts
        assert ".wav" in exts
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/test_scanner.py -v
```
Expected: 全部 FAIL

- [ ] **Step 3: 实现扫描器**

`src/holle_music/scanner.py`:
```python
"""音乐文件扫描器 — 递归扫描目录，发现 MP3/FLAC/WAV 文件."""

from pathlib import Path
from holle_music.models import Song, Playlist


class Scanner:
    """本地音乐文件扫描器."""

    SUPPORTED_EXTENSIONS: set[str] = {".mp3", ".flac", ".wav"}

    @property
    def supported_extensions(self) -> set[str]:
        return self.SUPPORTED_EXTENSIONS

    def scan(self, directory: Path) -> list[Song]:
        """递归扫描目录，返回发现的歌曲列表."""
        if isinstance(directory, str):
            directory = Path(directory)
        if not directory.is_dir():
            return []

        songs: list[Song] = []
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                song = self._create_song(path)
                songs.append(song)
        return sorted(songs, key=lambda s: s.title)

    def scan_to_playlist(self, directory: Path, name: str | None = None) -> Playlist:
        """扫描目录并以歌单形式返回."""
        songs = self.scan(directory)
        playlist_name = name or directory.name
        playlist = Playlist(name=playlist_name)
        for song in songs:
            playlist.add_song(song)
        return playlist

    def _create_song(self, path: Path) -> Song:
        """从文件路径创建 Song，尝试读取元数据."""
        song = Song(path=path)
        try:
            import mutagen
            audio = mutagen.File(str(path))
            if audio is not None:
                tags = getattr(audio, "tags", None)
                if tags is not None:
                    song.title = tags.get("title", [song.title])[0] or song.title
                    song.artist = tags.get("artist", [song.artist])[0] or song.artist
                    song.album = tags.get("album", [song.album])[0] or song.album
                info = getattr(audio, "info", None)
                if info is not None:
                    song.duration = info.length
        except ImportError:
            pass
        except Exception:
            pass
        return song
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/test_scanner.py -v
```
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add src/holle_music/scanner.py tests/test_scanner.py
git commit -m "feat: add music file scanner for MP3/FLAC/WAV"
```

---

### Task 4: 音频播放引擎

**Files:**
- Create: `src/holle_music/player.py`
- Create: `tests/test_player.py`

- [ ] **Step 1: 编写播放器测试**

`tests/test_player.py`:
```python
"""Tests for audio player engine."""

import pytest
from holle_music.player import Player, PlayerState
from holle_music.models import Song
from pathlib import Path


class TestPlayerState:
    def test_initial_state_is_stopped(self):
        player = Player()
        assert player.state == PlayerState.STOPPED

    def test_state_transitions(self):
        assert PlayerState.STOPPED != PlayerState.PLAYING
        assert PlayerState.PLAYING != PlayerState.PAUSED
        assert len(PlayerState) == 3


class TestPlayer:
    def test_player_initialization(self):
        player = Player()
        assert player.volume == 1.0
        assert player.current_song is None
        assert not player.is_playing

    def test_set_volume_clamps_range(self):
        player = Player()
        player.set_volume(0.5)
        assert player.volume == 0.5
        player.set_volume(2.0)
        assert player.volume == 1.0
        player.set_volume(-0.5)
        assert player.volume == 0.0

    def test_load_playlist(self):
        player = Player()
        songs = [
            Song(path=Path(f"/music/{i}.mp3"))
            for i in range(3)
        ]
        player.load_playlist(songs)
        assert len(player.playlist) == 3
        assert player.current_index == 0
        assert player.current_song == songs[0]

    def test_load_empty_playlist_does_nothing(self):
        player = Player()
        res = player.load_playlist([])
        assert res is True
        assert player.current_song is None

    def test_next_previous(self):
        player = Player()
        songs = [
            Song(path=Path(f"/music/{i}.mp3"))
            for i in range(3)
        ]
        player.load_playlist(songs)
        assert player.current_index == 0

        player.next()
        assert player.current_index == 1

        player.next()
        assert player.current_index == 2

        player.next()
        assert player.current_index == 0  # 循环

        player.previous()
        assert player.current_index == 2

    def test_previous_on_single_song(self):
        player = Player()
        songs = [Song(path=Path("/music/a.mp3"))]
        player.load_playlist(songs)
        player.previous()
        assert player.current_index == 0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/test_player.py -v
```
Expected: 全部 FAIL

- [ ] **Step 3: 实现播放引擎**

`src/holle_music/player.py`:
```python
"""音频播放引擎 — 基于 pygame.mixer 的播放控制."""

from enum import Enum, auto
from pathlib import Path
from holle_music.models import Song


class PlayerState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


class Player:
    """音频播放器，封装 pygame.mixer.music.

    支持 play/pause/resume/stop/next/prev 操作。
    """

    def __init__(self) -> None:
        self._state = PlayerState.STOPPED
        self._volume = 1.0
        self._playlist: list[Song] = []
        self._current_index = 0
        self._initialized = False
        self._on_song_change_callbacks: list = []

    def _ensure_init(self) -> None:
        if not self._initialized:
            import pygame  # lazy import，避免在测试时强制初始化
            pygame.mixer.init()
            self._initialized = True

    @property
    def state(self) -> PlayerState:
        return self._state

    @property
    def volume(self) -> float:
        return self._volume

    @property
    def current_song(self) -> Song | None:
        if 0 <= self._current_index < len(self._playlist):
            return self._playlist[self._current_index]
        return None

    @property
    def current_index(self) -> int:
        return self._current_index if self._playlist else 0

    @property
    def playlist(self) -> list[Song]:
        return list(self._playlist)

    @property
    def is_playing(self) -> bool:
        return self._state == PlayerState.PLAYING

    def on_song_change(self, callback):
        """注册歌曲切换回调."""
        self._on_song_change_callbacks.append(callback)

    def _notify_song_change(self) -> None:
        for cb in self._on_song_change_callbacks:
            try:
                cb(self.current_song)
            except Exception:
                pass

    def load_playlist(self, songs: list[Song]) -> None:
        self._playlist = list(songs)
        self._current_index = 0 if songs else 0

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))
        if self._initialized:
            import pygame
            pygame.mixer.music.set_volume(self._volume)

    def play(self, song: Song | None = None) -> None:
        self._ensure_init()
        import pygame

        if song is not None:
            if song not in self._playlist:
                self._playlist.insert(self._current_index + 1, song)
            self._current_index = self._playlist.index(song)

        if self.current_song is None:
            return

        if self._state == PlayerState.PAUSED:
            pygame.mixer.music.unpause()
        else:
            path = str(self.current_song.path)
            if not Path(path).exists():
                return
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()

        self._state = PlayerState.PLAYING
        self._notify_song_change()

    def pause(self) -> None:
        if self._state != PlayerState.PLAYING:
            return
        self._ensure_init()
        import pygame
        pygame.mixer.music.pause()
        self._state = PlayerState.PAUSED

    def stop(self) -> None:
        if self._initialized:
            import pygame
            pygame.mixer.music.stop()
        self._state = PlayerState.STOPPED

    def toggle_play_pause(self) -> None:
        if self._state == PlayerState.PLAYING:
            self.pause()
        else:
            self.play()

    def next(self) -> None:
        if not self._playlist:
            return
        was_playing = self._state == PlayerState.PLAYING
        self._current_index = (self._current_index + 1) % len(self._playlist)
        if was_playing:
            self.play()

    def previous(self) -> None:
        if not self._playlist:
            return
        was_playing = self._state == PlayerState.PLAYING
        self._current_index = (self._current_index - 1) % len(self._playlist)
        if was_playing:
            self.play()

    def cleanup(self) -> None:
        if self._initialized:
            import pygame
            pygame.mixer.music.stop()
            pygame.mixer.quit()
            self._initialized = False
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/test_player.py -v
```
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add src/holle_music/player.py tests/test_player.py
git commit -m "feat: add audio player engine with pygame.mixer"
```

---

### Task 5: 命令解析器

**Files:**
- Create: `src/holle_music/app.py` (在 Task 8 完整实现，此处仅实现命令解析部分，作为独立函数测试)
- Create: `tests/test_commands.py`

**注意:** 命令解析函数将实现在 `app.py` 中，作为 `parse_command()` 函数。本 Task 单独编写测试以驱动其实现。

- [ ] **Step 1: 编写命令解析测试**

`tests/test_commands.py`:
```python
"""Tests for command parser."""

import pytest
from pathlib import Path
from holle_music.app import parse_command, Command, CommandType


class TestCommandParser:
    def test_play_command(self):
        cmd = parse_command("play 晴天")
        assert cmd.type == CommandType.PLAY
        assert cmd.args == "晴天"

    def test_pause_command(self):
        cmd = parse_command("pause")
        assert cmd.type == CommandType.PAUSE

    def test_resume_command(self):
        cmd = parse_command("resume")
        assert cmd.type == CommandType.PLAY  # resume 等同于 play 无参数

    def test_stop_command(self):
        cmd = parse_command("stop")
        assert cmd.type == CommandType.STOP

    def test_next_command(self):
        cmd = parse_command("next")
        assert cmd.type == CommandType.NEXT

    def test_prev_command(self):
        cmd = parse_command("prev")
        assert cmd.type == CommandType.PREVIOUS

    def test_volume_command(self):
        cmd = parse_command("volume 80")
        assert cmd.type == CommandType.VOLUME
        assert cmd.args == "80"

    def test_scan_command(self):
        cmd = parse_command("scan /music/rock")
        assert cmd.type == CommandType.SCAN
        assert cmd.args == "/music/rock"

    def test_playlist_command(self):
        cmd = parse_command("playlist 我的歌单")
        assert cmd.type == CommandType.PLAYLIST
        assert cmd.args == "我的歌单"

    def test_help_command(self):
        cmd = parse_command("help")
        assert cmd.type == CommandType.HELP

    def test_quit_command(self):
        cmd = parse_command("quit")
        assert cmd.type == CommandType.QUIT

    def test_empty_input(self):
        cmd = parse_command("")
        assert cmd.type == CommandType.NONE

    def test_unknown_command(self):
        cmd = parse_command("foobar")
        assert cmd.type == CommandType.UNKNOWN

    def test_trim_whitespace(self):
        cmd = parse_command("  play   晴天  ")
        assert cmd.type == CommandType.PLAY
        assert cmd.args == "晴天"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/test_commands.py -v
```
Expected: 全部 FAIL

- [ ] **Step 3: 在 app.py 中实现命令解析**

`src/holle_music/app.py`:
```python
"""Holle Music — Textual TUI 主应用."""

from dataclasses import dataclass
from enum import Enum, auto


class CommandType(Enum):
    NONE = auto()
    PLAY = auto()
    PAUSE = auto()
    STOP = auto()
    NEXT = auto()
    PREVIOUS = auto()
    VOLUME = auto()
    SCAN = auto()
    PLAYLIST = auto()
    HELP = auto()
    QUIT = auto()
    UNKNOWN = auto()


@dataclass
class Command:
    type: CommandType
    args: str = ""


COMMAND_MAP: dict[str, CommandType] = {
    "play": CommandType.PLAY,
    "pause": CommandType.PAUSE,
    "stop": CommandType.STOP,
    "resume": CommandType.PLAY,  # resume 等同于 play
    "next": CommandType.NEXT,
    "prev": CommandType.PREVIOUS,
    "previous": CommandType.PREVIOUS,
    "volume": CommandType.VOLUME,
    "vol": CommandType.VOLUME,
    "scan": CommandType.SCAN,
    "playlist": CommandType.PLAYLIST,
    "help": CommandType.HELP,
    "?": CommandType.HELP,
    "quit": CommandType.QUIT,
    "exit": CommandType.QUIT,
    "q": CommandType.QUIT,
}


def parse_command(text: str) -> Command:
    """解析用户输入的命令字符串."""
    text = text.strip()
    if not text:
        return Command(CommandType.NONE)

    parts = text.split(maxsplit=1)
    keyword = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    cmd_type = COMMAND_MAP.get(keyword, CommandType.UNKNOWN)
    return Command(cmd_type, args)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/test_commands.py -v
```
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add src/holle_music/app.py tests/test_commands.py
git commit -m "feat: add command parser for text commands"
```

---

### Task 6: UI 组件 — 左侧/中上/右侧面板

**Files:**
- Create: `src/holle_music/widgets.py`

本 Task 实现 3 个静态展示面板：AlbumCover、LyricsPanel、PlaylistPanel。

- [ ] **Step 1: 实现 AlbumCover 组件**

`src/holle_music/widgets.py`:
```python
"""Holle Music UI 组件 — Textual 自定义 Widget."""

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static, ListView, ListItem, Button, Input, Label


class AlbumCover(Static):
    """专辑封面面板 — 带白色边框，居中显示占位符."""

    BORDER_TITLE = "专辑封面"

    def compose(self) -> ComposeResult:
        yield Static("暂无封面", id="album-art-placeholder")

    def on_mount(self) -> None:
        self.styles.border = ("solid", "white")
        self.styles.content_align = ("center", "middle")

    def set_cover_text(self, text: str) -> None:
        placeholder = self.query_one("#album-art-placeholder", Static)
        placeholder.update(text)
```

- [ ] **Step 2: 实现 LyricsPanel 组件**

在同一个 `widgets.py` 文件中追加:

```python
class LyricsPanel(Static):
    """歌词面板 — 带白色边框，居中显示歌词."""

    BORDER_TITLE = "歌词"

    def compose(self) -> ComposeResult:
        yield Static("暂无歌词", id="lyrics-content")

    def on_mount(self) -> None:
        self.styles.border = ("solid", "white")
        self.styles.content_align = ("center", "middle")
        self.styles.overflow_y = "auto"

    def set_lyrics(self, text: str) -> None:
        content = self.query_one("#lyrics-content", Static)
        content.update(text)
```

- [ ] **Step 3: 实现 PlaylistPanel 组件**

在同一个 `widgets.py` 文件中追加:

```python
class PlaylistPanel(Static):
    """播放列表面板 — 带白色边框，支持列表滚动."""

    BORDER_TITLE = "播放列表"

    def compose(self) -> ComposeResult:
        yield Static("暂无歌曲", id="playlist-placeholder")
        yield ListView(id="playlist-list")

    def on_mount(self) -> None:
        self.styles.border = ("solid", "white")
        self._hide_placeholder(False)

    def _hide_placeholder(self, hidden: bool) -> None:
        placeholder = self.query_one("#playlist-placeholder", Static)
        lst = self.query_one("#playlist-list", ListView)
        placeholder.display = False if hidden else True
        lst.display = True if hidden else False

    def load_songs(self, songs: list) -> None:
        """加载歌曲列表，每首歌曲作为 ListItem."""
        lst = self.query_one("#playlist-list", ListView)
        lst.clear()
        if not songs:
            self._hide_placeholder(False)
            return
        self._hide_placeholder(True)
        for song in songs:
            label = f"{song.title}  —  {song.artist}"
            lst.append(ListItem(Static(label)))

    def get_selected_index(self) -> int | None:
        """返回当前选中的歌曲索引."""
        lst = self.query_one("#playlist-list", ListView)
        return lst.index if lst.index is not None else None
```

- [ ] **Step 4: 验证 widget 导入和结构**

```bash
python -c "
from holle_music.widgets import AlbumCover, LyricsPanel, PlaylistPanel
print('All widgets imported successfully')
w = AlbumCover()
print(f'AlbumCover BORDER_TITLE={w.BORDER_TITLE}')
l = LyricsPanel()
print(f'LyricsPanel BORDER_TITLE={l.BORDER_TITLE}')
p = PlaylistPanel()
print(f'PlaylistPanel BORDER_TITLE={p.BORDER_TITLE}')
"
```
Expected: 所有 widget 导入成功，BORDER_TITLE 正确

- [ ] **Step 5: Commit**

```bash
git add src/holle_music/widgets.py
git commit -m "feat: add AlbumCover, LyricsPanel, PlaylistPanel widgets"
```

---

### Task 7: UI 组件 — 底部面板 (Controls, Visualizer, CommandInput)

**Files:**
- Modify: `src/holle_music/widgets.py`

- [ ] **Step 1: 实现 Controls 播放控制组件**

在 `widgets.py` 末尾追加:

```python
class Controls(Container):
    """播放控制面板 — 无外边框，上一曲/播放暂停/下一曲 + 歌曲信息按钮."""

    def compose(self) -> ComposeResult:
        with Container(id="controls-buttons"):
            yield Button("◀  上一曲", id="btn-prev", variant="default")
            yield Button("⏸  播放/暂停", id="btn-play-pause", variant="default")
            yield Button("▶  下一曲", id="btn-next", variant="default")
        with Container(id="controls-info"):
            yield Button("歌曲信息", id="btn-song-info", variant="default")

    def on_mount(self) -> None:
        buttons_row = self.query_one("#controls-buttons", Container)
        buttons_row.styles.layout = "horizontal"
        buttons_row.styles.align = ("center", "middle")
        buttons_row.styles.content_align = ("center", "middle")
        info_row = self.query_one("#controls-info", Container)
        info_row.styles.align = ("center", "middle")
        info_row.styles.content_align = ("center", "middle")
        self.styles.align = ("center", "middle")

    def set_play_pause_label(self, is_playing: bool) -> None:
        btn = self.query_one("#btn-play-pause", Button)
        btn.label = "⏸  暂停" if is_playing else "▶  播放"
```

- [ ] **Step 2: 实现 Visualizer 歌曲律动组件**

在 `widgets.py` 末尾追加:

```python
import time  # 文件顶部追加


class Visualizer(Static):
    """歌曲律动面板 — ASCII 条形频谱可视化."""

    BORDER_TITLE = "歌曲律动"

    _bars: int = 16
    _timer_handle: object | None = None

    def compose(self) -> ComposeResult:
        yield Static(self._render_bars([0] * self._bars), id="viz-content")

    def on_mount(self) -> None:
        self.styles.border = ("solid", "white")
        self.styles.content_align = ("center", "middle")

    def start(self) -> None:
        """启动频谱动画定时器."""
        self._timer_handle = self.set_interval(0.1, self._update_bars)

    def stop(self) -> None:
        """停止频谱动画."""
        if self._timer_handle is not None:
            self._timer_handle.stop()
            self._timer_handle = None

    def _render_bars(self, values: list[int]) -> str:
        """将数值数组渲染为 ASCII 条形图."""
        chars = "▁▂▃▄▅▆▇█"
        max_val = max(values) if max(values) > 0 else 8
        lines = []
        for v in values:
            idx = min(int(v / max_val * (len(chars) - 1)), len(chars) - 1)
            lines.append(chars[idx] * 2)
        return " ".join(lines)

    def _update_bars(self) -> None:
        """随机生成频谱数据并更新显示."""
        import random
        values = [random.randint(1, 10) for _ in range(self._bars)]
        content = self.query_one("#viz-content", Static)
        content.update(self._render_bars(values))

    def set_active(self, active: bool) -> None:
        """设置为活跃/非活跃状态."""
        if active:
            self.start()
        else:
            self.stop()
```

- [ ] **Step 3: 实现 CommandInput 命令行输入组件**

在 `widgets.py` 末尾追加:

```python
class CommandInput(Container):
    """命令行输入区域 — 提示标签 + 输入框."""

    def compose(self) -> ComposeResult:
        yield Label("命令行，可以让 AI 解说歌曲和寻找相似歌曲", id="cmd-hint")
        yield Input(
            placeholder="输入命令 (help 查看可用命令)...",
            id="cmd-input",
        )

    def on_mount(self) -> None:
        self.styles.height = "auto"
        hint = self.query_one("#cmd-hint", Label)
        hint.styles.text_style = "dim"
        hint.styles.content_align_horizontal = "left"
        cmd = self.query_one("#cmd-input", Input)
        cmd.styles.width = "100%"

    def get_value(self) -> str:
        return self.query_one("#cmd-input", Input).value

    def clear(self) -> None:
        self.query_one("#cmd-input", Input).value = ""
```

- [ ] **Step 4: 验证新组件导入和结构**

```bash
python -c "
from holle_music.widgets import Controls, Visualizer, CommandInput
c = Controls()
v = Visualizer()
ci = CommandInput()
print('Controls created')
print(f'Visualizer BORDER_TITLE={v.BORDER_TITLE}')
print('CommandInput created')
"
```
Expected: 所有组件创建成功

- [ ] **Step 5: Commit**

```bash
git add src/holle_music/widgets.py
git commit -m "feat: add Controls, Visualizer, CommandInput widgets"
```

---

### Task 8: Textual 主应用 — Grid 布局与生命周期

**Files:**
- Modify: `src/holle_music/app.py` (在已有命令解析基础上添加完整 App)
- Modify: `src/holle_music/__main__.py` (如需要)

- [ ] **Step 1: 实现完整的 Textual App**

替换 `app.py` 内容（保留 Task 5 中的 `CommandType`、`Command`、`COMMAND_MAP`、`parse_command`）:

```python
"""Holle Music — Textual TUI 主应用."""

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer
from textual.containers import Grid

from holle_music.models import Song, Playlist
from holle_music.scanner import Scanner
from holle_music.player import Player, PlayerState
from holle_music.widgets import (
    AlbumCover,
    LyricsPanel,
    PlaylistPanel,
    Controls,
    Visualizer,
    CommandInput,
)


class CommandType(Enum):
    NONE = auto()
    PLAY = auto()
    PAUSE = auto()
    STOP = auto()
    NEXT = auto()
    PREVIOUS = auto()
    VOLUME = auto()
    SCAN = auto()
    PLAYLIST = auto()
    HELP = auto()
    QUIT = auto()
    UNKNOWN = auto()


@dataclass
class Command:
    type: CommandType
    args: str = ""


COMMAND_MAP: dict[str, CommandType] = {
    "play": CommandType.PLAY,
    "pause": CommandType.PAUSE,
    "stop": CommandType.STOP,
    "resume": CommandType.PLAY,
    "next": CommandType.NEXT,
    "prev": CommandType.PREVIOUS,
    "previous": CommandType.PREVIOUS,
    "volume": CommandType.VOLUME,
    "vol": CommandType.VOLUME,
    "scan": CommandType.SCAN,
    "playlist": CommandType.PLAYLIST,
    "help": CommandType.HELP,
    "?": CommandType.HELP,
    "quit": CommandType.QUIT,
    "exit": CommandType.QUIT,
    "q": CommandType.QUIT,
}


def parse_command(text: str) -> Command:
    """解析用户输入的命令字符串."""
    text = text.strip()
    if not text:
        return Command(CommandType.NONE)
    parts = text.split(maxsplit=1)
    keyword = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    cmd_type = COMMAND_MAP.get(keyword, CommandType.UNKNOWN)
    return Command(cmd_type, args)


class HolleMusicApp(App):
    """Holle Music 主应用."""

    CSS = """
    Grid {
        grid-size: 3 3;
        grid-rows: 45fr 45fr 10fr;
        grid-columns: 1fr 1fr 1fr;
        border: solid white;
        background: black;
    }

    AlbumCover {
        border: solid white;
        height: 100%;
    }

    LyricsPanel {
        border: solid white;
        height: 100%;
    }

    PlaylistPanel {
        border: solid white;
        height: 100%;
        column-span: 1;
        row-span: 2;
    }

    Controls {
        height: 100%;
    }

    Visualizer {
        border: solid white;
        height: 100%;
    }

    CommandInput {
        column-span: 3;
        height: 100%;
    }

    Button {
        background: black;
        color: white;
        min-width: 14;
    }

    Button:focus {
        text-style: bold reverse;
    }

    ListView {
        background: black;
        color: white;
    }

    ListView > ListItem {
        background: black;
        color: white;
    }

    ListView > ListItem.--highlight {
        background: white;
        color: black;
    }

    Input {
        background: black;
        color: white;
        border: solid white;
    }

    Label {
        background: black;
        color: white;
    }

    Static {
        background: black;
        color: white;
    }

    Header {
        background: black;
        color: white;
    }

    Footer {
        background: black;
        color: white;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_play_pause", "播放/暂停"),
        Binding("left", "previous_track", "上一曲"),
        Binding("right", "next_track", "下一曲"),
        Binding("tab", "focus_next", "切换焦点"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.player = Player()
        self.scanner = Scanner()
        self._playlists: dict[str, Playlist] = {}
        self.player.on_song_change(self._on_song_changed)

    def compose(self) -> ComposeResult:
        yield Header()
        with Grid():
            yield AlbumCover(id="album-cover")
            yield LyricsPanel(id="lyrics-panel")
            yield PlaylistPanel(id="playlist-panel")
            yield Controls(id="controls")
            yield Visualizer(id="visualizer")
            yield CommandInput(id="command-input")
        yield Footer()

    def on_mount(self) -> None:
        """应用启动后加载演示数据."""
        self.title = "Holle Music"
        self.sub_title = "终端音乐播放器"
        cmd_input = self.query_one("#command-input", CommandInput)
        cmd = cmd_input.query_one("#cmd-input", Input)

    def _on_song_changed(self, song: Song | None) -> None:
        """歌曲切换时更新 UI."""
        if song is not None:
            cover = self.query_one("#album-cover", AlbumCover)
            cover.set_cover_text(f"{song.title}\n\n{song.artist}")
            lyrics = self.query_one("#lyrics-panel", LyricsPanel)
            lyrics.set_lyrics(f"正在播放: {song.title}")

    def action_toggle_play_pause(self) -> None:
        """空格键：播放/暂停."""
        self.player.toggle_play_pause()
        self._update_controls_ui()

    def action_next_track(self) -> None:
        """右箭头：下一曲."""
        self.player.next()
        self._sync_playlist_selection()

    def action_previous_track(self) -> None:
        """左箭头：上一曲."""
        self.player.previous()
        self._sync_playlist_selection()

    def _update_controls_ui(self) -> None:
        """更新播放控制按钮状态."""
        controls = self.query_one("#controls", Controls)
        controls.set_play_pause_label(self.player.is_playing)
        viz = self.query_one("#visualizer", Visualizer)
        viz.set_active(self.player.is_playing)

    def _sync_playlist_selection(self) -> None:
        """同步播放列表高亮到当前歌曲."""
        playlist = self.query_one("#playlist-panel", PlaylistPanel)
        lst = playlist.query_one("#playlist-list", ListView)
        lst.index = self.player.current_index

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """处理播放控制按钮点击."""
        btn_id = event.button.id
        if btn_id == "btn-prev":
            self.action_previous_track()
        elif btn_id == "btn-play-pause":
            self.action_toggle_play_pause()
        elif btn_id == "btn-next":
            self.action_next_track()
        elif btn_id == "btn-song-info":
            song = self.player.current_song
            if song:
                self.notify(
                    f"{song.title}\n{song.artist} — {song.album}\n时长: {song.duration:.0f}秒",
                    title="歌曲信息",
                )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理命令行输入."""
        text = event.value
        cmd = parse_command(text)
        self._handle_command(cmd)
        cmd_input = self.query_one("#command-input", CommandInput)
        cmd_input.clear()

    def _handle_command(self, cmd: Command) -> None:
        """根据解析的命令执行操作."""
        if cmd.type == CommandType.PLAY:
            self.player.play()

        elif cmd.type == CommandType.PAUSE:
            self.player.pause()
            self._update_controls_ui()

        elif cmd.type == CommandType.STOP:
            self.player.stop()
            self._update_controls_ui()

        elif cmd.type == CommandType.NEXT:
            self.action_next_track()

        elif cmd.type == CommandType.PREVIOUS:
            self.action_previous_track()

        elif cmd.type == CommandType.VOLUME:
            try:
                vol = int(cmd.args) / 100
                self.player.set_volume(vol)
                self.notify(f"音量: {int(vol * 100)}%", title="音量")
            except ValueError:
                self.notify("用法: volume <0-100>", title="错误", severity="error")

        elif cmd.type == CommandType.SCAN:
            path = Path(cmd.args) if cmd.args else Path.home() / "Music"
            if path.exists():
                playlist = self.scanner.scan_to_playlist(path, name=path.name)
                name = playlist.name
                self._playlists[name] = playlist
                self._load_playlist_ui(playlist)
                self.notify(f"扫描完成: {len(playlist)} 首歌曲", title="扫描")
            else:
                self.notify(f"路径不存在: {path}", title="错误", severity="error")

        elif cmd.type == CommandType.PLAYLIST:
            if cmd.args in self._playlists:
                self._load_playlist_ui(self._playlists[cmd.args])
            else:
                self.notify(
                    f"歌单 '{cmd.args}' 不存在，请先用 scan 扫描",
                    title="错误",
                    severity="error",
                )

        elif cmd.type == CommandType.HELP:
            self.notify(
                "play  播放 | pause  暂停 | stop  停止\n"
                "next  下一曲 | prev  上一曲\n"
                "volume <0-100>  设置音量\n"
                "scan <路径>  扫描音乐文件夹\n"
                "playlist <名称>  加载歌单\n"
                "quit  退出",
                title="帮助",
            )

        elif cmd.type == CommandType.QUIT:
            self.exit()

        elif cmd.type == CommandType.UNKNOWN:
            self.notify(f"未知命令: {cmd.args or '?'}", title="错误", severity="error")

    def _load_playlist_ui(self, playlist: Playlist) -> None:
        """将歌单加载到 UI 和播放器."""
        playlist_panel = self.query_one("#playlist-panel", PlaylistPanel)
        playlist_panel.load_songs(playlist.songs)
        self.player.load_playlist(playlist.songs)
        self.title = f"Holle Music - {playlist.name}"
        self.notify(f"已加载歌单: {playlist.name} ({len(playlist)} 首)", title="歌单")


def main() -> None:
    """程序入口."""
    app = HolleMusicApp()
    app.run()
```

- [ ] **Step 2: 验证应用可以实例化**

```bash
python -c "from holle_music.app import HolleMusicApp; app = HolleMusicApp(); print('App created successfully')"
```
Expected: App 创建成功 (注意：此步不启动 GUI，仅验证导入和实例化)

- [ ] **Step 3: 运行应用进行手动验证**

```bash
hollemusic
```
手动检查:
- 黑色背景，白色边框的 3×3 网格布局
- 专辑封面区域显示"暂无封面"
- 歌词区域显示"暂无歌词"
- 播放列表为空时显示"暂无歌曲"
- 播放控制按钮 (◀ ⏸ ▶) 可见
- 歌曲律动区域可见
- 底部命令行输入栏可见
- 按 Tab 可在组件间切换焦点

- [ ] **Step 4: Commit**

```bash
git add src/holle_music/app.py
git commit -m "feat: implement main Textual app with 3x3 grid layout"
```

---

### Task 9: 集成测试与最终验证

**Files:**
- Modify: `src/holle_music/app.py` (如有 bug 修复)

- [ ] **Step 1: 运行所有单元测试**

```bash
pytest tests/ -v
```
Expected: 所有测试 PASS

- [ ] **Step 2: 验证 CLI 入口点**

```bash
python -m holle_music --help
```
Expected: 显示 Textual 应用帮助 (或直接启动 GUI)

- [ ] **Step 3: 端到端功能清单验证**

在 `hollemusic` 运行中验证以下功能:

| 功能 | 操作 | 预期结果 |
|------|------|----------|
| 界面布局 | 启动应用 | 3×3 Grid，黑底白字白边框 |
| 播放控制 | 点击 ▶ 按钮 | 按钮标签变为 ⏸ 暂停 |
| 键盘快捷键 | 按空格键 | 切换播放/暂停 |
| 键盘快捷键 | 按左箭头 | 上一曲 |
| 键盘快捷键 | 按右箭头 | 下一曲 |
| 命令扫描 | 输入 `scan .` | 扫描当前目录音乐文件 |
| 命令帮助 | 输入 `help` | 弹出帮助信息 |
| 命令退出 | 输入 `quit` | 退出应用 |
| 歌曲律动 | 播放时 | 频谱动画运行 |

- [ ] **Step 4: 修复发现的问题并提交**

```bash
git add -A
git commit -m "fix: issues found during integration testing"
```

---

### Task 10: 可选增强功能

- [ ] **Step 1: 电台流支持**

在 `player.py` 中添加流媒体 URL 播放支持，`scanner.py` 中添加电台 URL 列表扫描。

- [ ] **Step 2: AI 解说歌曲 (OpenAI API 集成)**

添加 `src/holle_music/ai.py`，调用 OpenAI API 解说当前播放的歌曲，并在 `CommandInput` 中集成 AI 响应显示。

---

## 实施顺序

```
Task 1 (脚手架) → Task 2 (模型) → Task 3 (扫描器) → Task 4 (播放器) → Task 5 (命令解析)
                                                                    ↓
Task 9 (集成测试) ← Task 8 (主应用) ← Task 7 (下半部组件) ← Task 6 (上半部组件)
```

Tasks 6 和 7 可并行，其他依赖顺序执行。
