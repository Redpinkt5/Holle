"""Local AI lyrics recognition using OpenAI Whisper.

零配置、纯本地、离线可用 — 首次运行全自动安装和下载，之后完全离线。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

CACHE_DIR = Path("lyrics_cache")
MODEL_DIR = Path("./models")


# ── 调试日志 ──────────────────────────────────────────────────────────

def _debug(msg: str) -> None:
    """写入带时间戳的调试日志，用于定位卡住的位置."""
    import datetime
    log_dir = MODEL_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / "debug.log", "a", encoding="utf-8") as f:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        f.write(f"[{ts}] {msg}\n")


# ── 自动安装 Python 依赖 ────────────────────────────────────────────

def _ensure_package(
    pip_name: str,
    import_name: str | None = None,
    extra_args: list[str] | None = None,
) -> bool:
    """自动安装缺失的 Python 包。返回 True 表示已就绪。"""
    if import_name is None:
        import_name = pip_name.replace("-", "_")
    try:
        __import__(import_name)
        _debug(f"_ensure_package: {pip_name} 已安装 → 返回 True")
        return True
    except ImportError:
        pass

    _debug(f"_ensure_package: {pip_name} 未安装, 开始 pip install")
    log_dir = MODEL_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"pip_{pip_name}.log"
    cmd = [
        sys.executable, "-m", "pip", "install", pip_name,
        "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
        "--trusted-host", "pypi.tuna.tsinghua.edu.cn",
    ]
    if extra_args:
        cmd.extend(extra_args)
    try:
        with open(log_path, "w", encoding="utf-8") as log:
            subprocess.run(cmd, check=True, timeout=600, stdout=log, stderr=log)
        _debug(f"_ensure_package: {pip_name} pip install 成功 → 返回 True")
        return True
    except subprocess.TimeoutExpired:
        _debug(f"_ensure_package: {pip_name} pip install 超时 → 返回 False")
        return False
    except Exception as exc:
        _debug(f"_ensure_package: {pip_name} pip install 异常 {exc} → 返回 False")
        return False


def _add_ffmpeg_to_path() -> None:
    """把本地 models/ffmpeg 目录加入 PATH。"""
    ffmpeg_dir = MODEL_DIR / "ffmpeg"
    ffmpeg_exe = ffmpeg_dir / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    if ffmpeg_exe.exists():
        os.environ["PATH"] = str(ffmpeg_dir) + os.pathsep + os.environ["PATH"]
        _debug("_add_ffmpeg_to_path: 已加入 PATH")


def _ensure_ffmpeg(say: Callable[[str], None] | None = None) -> bool:
    """自动下载 FFmpeg 二进制到 ./models/ffmpeg/。返回 True 表示已就绪。"""
    _debug("_ensure_ffmpeg: 开始")
    ffmpeg_dir = MODEL_DIR / "ffmpeg"
    ffmpeg_exe = ffmpeg_dir / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")

    # 优先检查缓存目录里的 ffmpeg
    if ffmpeg_exe.exists():
        os.environ["PATH"] = str(ffmpeg_dir) + os.pathsep + os.environ["PATH"]
        _debug(f"_ensure_ffmpeg: 缓存已存在 {ffmpeg_exe.resolve()} → 返回 True")
        return True

    _debug(f"_ensure_ffmpeg: models 缓存不存在, 检查 PATH 中的 ffmpeg")
    if shutil.which("ffmpeg"):
        _debug("_ensure_ffmpeg: 系统 PATH 找到 ffmpeg → 返回 True")
        return True

    _debug(f"_ensure_ffmpeg: 未找到 ffmpeg, 准备下载")
    _debug(f"  ffmpeg_exe 路径: {ffmpeg_exe.resolve()}")
    _debug(f"  ffmpeg_dir 路径: {ffmpeg_dir.resolve()}")
    if sys.platform != "win32":
        _debug("_ensure_ffmpeg: 非 Windows → 返回 False")
        return False

    # 国内镜像
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    try:
        import urllib.request
        import zipfile
        import socket

        ffmpeg_dir.mkdir(parents=True, exist_ok=True)
        zip_path = ffmpeg_dir / "ffmpeg.zip"

        if say:
            say("下载 FFmpeg (~30MB) ...")
        _debug("_ensure_ffmpeg: 开始下载 " + url)

        socket.setdefaulttimeout(30)

        def _report(block_count: int, block_size: int, total: int) -> None:
            if say and total > 0 and block_count % 20 == 0:
                pct = min(100, block_count * block_size * 100 // total)
                say(f"下载 FFmpeg ({pct}%) ...")

        urllib.request.urlretrieve(url, zip_path, _report)
        _debug("_ensure_ffmpeg: 下载完成")

        if say:
            say("解压 FFmpeg ...")

        with zipfile.ZipFile(zip_path, "r") as zf:
            exe_name = "ffmpeg.exe"
            candidates = [n for n in zf.namelist() if n.endswith("/" + exe_name)]
            if not candidates:
                candidates = [n for n in zf.namelist() if n.endswith(exe_name)]
            if candidates:
                with zf.open(candidates[0]) as src:
                    with open(ffmpeg_exe, "wb") as dst:
                        shutil.copyfileobj(src, dst)
        _debug("_ensure_ffmpeg: 解压完成")

        try:
            zip_path.unlink()
        except Exception:
            pass

        if ffmpeg_exe.exists():
            os.environ["PATH"] = str(ffmpeg_dir) + os.pathsep + os.environ["PATH"]
            _debug("_ensure_ffmpeg: 成功 → 返回 True")
            return True
        _debug("_ensure_ffmpeg: 解压后未找到 exe → 返回 False")
        return False
    except Exception as exc:
        _debug(f"_ensure_ffmpeg: gyan.dev 下载失败: {exc}, 尝试国内镜像")
        # 备用：使用国内 FFmpeg 构建（完整包，约 80MB but 含所有依赖库）
        backup_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        try:
            _debug("_ensure_ffmpeg: 尝试 github BtbN 构建")
            if say:
                say("下载 FFmpeg (备用源 ~80MB) ...")
            urllib.request.urlretrieve(backup_url, zip_path, _report)
            _debug("_ensure_ffmpeg: 备用源下载完成")

            with zipfile.ZipFile(zip_path, "r") as zf:
                exe_name = "ffmpeg.exe"
                candidates = [n for n in zf.namelist() if n.endswith("/" + exe_name)]
                if not candidates:
                    candidates = [n for n in zf.namelist() if n.endswith(exe_name)]
                if candidates:
                    with zf.open(candidates[0]) as src:
                        with open(ffmpeg_exe, "wb") as dst:
                            shutil.copyfileobj(src, dst)
            try:
                zip_path.unlink()
            except Exception:
                pass
            if ffmpeg_exe.exists():
                os.environ["PATH"] = str(ffmpeg_dir) + os.pathsep + os.environ["PATH"]
                _debug("_ensure_ffmpeg: 备用源成功 → 返回 True")
                return True
        except Exception as exc2:
            _debug(f"_ensure_ffmpeg: 备用源也失败: {exc2}")
        return False
    except Exception as exc:
        _debug(f"_ensure_ffmpeg: 异常 → {exc}")
        return False


# ── 歌词缓存 ────────────────────────────────────────────────────────

class LyricsCache:
    """JSON 文件缓存，按歌曲文件名索引."""

    def __init__(self, cache_dir: str | Path = CACHE_DIR) -> None:
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _key(self, filepath: str) -> str:
        return Path(filepath).stem + ".json"

    def get(self, filepath: str) -> list[dict] | None:
        p = self._dir / self._key(filepath)
        if p.exists():
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def set(self, filepath: str, segments: list[dict]) -> None:
        p = self._dir / self._key(filepath)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)


# ── Whisper 模型管理 ─────────────────────────────────────────────────

class LocalAIManager:
    """Whisper 模型单例 — 首次自动安装依赖 + 下载模型."""

    _instance: LocalAIManager | None = None
    _lock = threading.Lock()

    def __new__(cls) -> LocalAIManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._model = None
                    cls._instance._model_name = "base"
        return cls._instance

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load_model(self, say: Callable[[str], None] | None = None) -> object:
        """依次安装 FFmpeg → whisper → torch (CPU) → 下载模型."""
        def step(msg: str) -> None:
            _debug(f"load_model step: {msg}")
            if say:
                say(msg)

        _debug("load_model: 开始")
        # 1. FFmpeg — 确保 PATH 中有 ffmpeg（whisper 依赖它）
        step("检查 FFmpeg ...")
        _ensure_ffmpeg(step)
        # 把 models/ffmpeg 加到 PATH（即使返回 False，ffmpeg_dir 也已存在则加入 PATH）
        _add_ffmpeg_to_path()

        # 2. whisper
        step("安装 openai-whisper ...")
        if not _ensure_package("openai-whisper", "whisper"):
            step("openai-whisper 安装失败")

        # 3. torch CPU 版 (~150MB)
        step("安装 torch (CPU 版, ~150MB) ...")
        if not _ensure_package(
            "torch",
            extra_args=["--extra-index-url", "https://download.pytorch.org/whl/cpu"],
        ):
            step("torch 安装失败, 尝试默认版本 ...")
            _ensure_package("torch")

        # 4. 国内镜像
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        _debug("load_model: HF_ENDPOINT=" + os.environ.get("HF_ENDPOINT", "not set"))

        step("加载 Whisper base 模型 (首次约 142MB) ...")
        import whisper
        MODEL_DIR.mkdir(parents=True, exist_ok=True)

        if self._model is None:
            import contextlib
            log_dir = MODEL_DIR / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            _debug("load_model: 开始下载 whisper 模型...")
            with open(log_dir / "whisper_load.log", "w", encoding="utf-8") as f:
                with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
                    self._model = whisper.load_model(
                        self._model_name,
                        download_root=str(MODEL_DIR),
                    )
            _debug("load_model: whisper 模型加载完成")
        return self._model

    def transcribe(
        self,
        audio_path: str,
        say: Callable[[str], None] | None = None,
    ) -> list[dict]:
        """转录音频 → 带时间戳的歌词段."""
        model = self.load_model(say)
        if say:
            say("AI 识别歌词中 (可能需要 1-3 分钟) ...")

        result = model.transcribe(
            audio_path,
            language="zh",
            word_timestamps=True,
            verbose=False,
        )

        segments: list[dict] = []
        for seg in result["segments"]:
            text = seg["text"].strip()
            if text:
                segments.append({
                    "start": float(seg["start"]),
                    "end": float(seg["end"]),
                    "text": text,
                })
        return segments


# ── 后台识别入口 ─────────────────────────────────────────────────────

def _run_recognition(
    audio_path: str,
    on_progress: Callable[[str], None],
    on_done: Callable[[list[dict]], None],
    on_error: Callable[[str], None],
) -> None:
    try:
        _debug(f"_run_recognition: 开始, audio={audio_path}")
        # 检查缓存
        cache = LyricsCache()
        cached = cache.get(audio_path)
        if cached:
            _debug("_run_recognition: 命中缓存 → on_done")
            on_done(cached)
            return

        _debug("_run_recognition: 未命中缓存, 开始转录")
        manager = LocalAIManager()
        segments = manager.transcribe(audio_path, on_progress)
        cache.set(audio_path, segments)
        _debug(f"_run_recognition: 转录完成, {len(segments)} 段 → on_done")
        on_done(segments)
    except Exception as exc:
        _debug(f"_run_recognition: 异常 → {exc}")
        on_error(f"识别失败: {exc}")


def start_recognition(
    audio_path: str,
    on_progress: Callable[[str], None],
    on_done: Callable[[list[dict]], None],
    on_error: Callable[[str], None],
) -> threading.Thread:
    t = threading.Thread(
        target=_run_recognition,
        args=(audio_path, on_progress, on_done, on_error),
        daemon=True,
    )
    t.start()
    return t
