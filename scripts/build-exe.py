#!/usr/bin/env python3
"""Build standalone executables with PyInstaller.

Creates two separate EXEs:
    HolleMusic.exe  — Full terminal TUI app (player + assistant)
    HollePet.exe    — Desktop music assistant only (lightweight, no Textual)
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SRC_DIR = PROJECT_ROOT / "src"


def _ensure_pyinstaller() -> None:
    try:
        import PyInstaller.__main__  # noqa: F401
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller", "-q"]
        )


def build_terminal() -> None:
    """Build the full terminal TUI app (includes the desktop assistant)."""
    print("\n" + "=" * 60)
    print("Building HolleMusic.exe (full terminal TUI app)...")
    print("=" * 60)

    sys.path.insert(0, str(SRC_DIR))

    import PyInstaller.__main__

    args = [
        str(SRC_DIR / "holle_music" / "app.py"),
        "--name", "HolleMusic",
        "--onefile",
        "--console",
        "--noconfirm",
        "--clean",
        "--add-data", f"{SRC_DIR / 'holle_music'};holle_music",
        "--hidden-import", "textual",
        "--hidden-import", "textual.widgets",
        "--hidden-import", "textual.containers",
        "--hidden-import", "textual.binding",
        "--hidden-import", "textual.events",
        "--hidden-import", "pygame",
        "--hidden-import", "pygame.mixer",
        "--hidden-import", "mutagen",
        "--hidden-import", "mutagen.flac",
        "--hidden-import", "mutagen.mp3",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "openai",
        "--hidden-import", "ddgs",
        "--hidden-import", "numpy",
        "--hidden-import", "numpy.fft",
        "--hidden-import", "librosa",
        "--hidden-import", "win32api",
        "--hidden-import", "win32con",
        "--hidden-import", "win32gui",
        "--hidden-import", "win32ui",
        "--collect-all", "textual",
        "--collect-all", "pygame",
        "--distpath", str(PROJECT_ROOT / "dist"),
        "--workpath", str(PROJECT_ROOT / "build"),
        "--specpath", str(PROJECT_ROOT / "build"),
    ]

    PyInstaller.__main__.run(args)

    exe = PROJECT_ROOT / "dist" / "HolleMusic.exe"
    if exe.exists():
        print(f"\n✅ HolleMusic.exe: {exe}")
    else:
        print(f"\n⚠️ Build completed but HolleMusic.exe not found.")


def build_pet() -> None:
    """Build the desktop music assistant only (no Textual dependency)."""
    print("\n" + "=" * 60)
    print("Building HollePet.exe (desktop music assistant)...")
    print("=" * 60)

    import PyInstaller.__main__

    args = [
        str(SRC_DIR / "holle_music" / "pet" / "main.py"),
        "--name", "HollePet",
        "--onefile",
        "--console",
        "--noconfirm",
        "--clean",
        "--add-data", f"{SRC_DIR / 'holle_music'};holle_music",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageDraw",
        "--hidden-import", "pygame",
        "--hidden-import", "pygame.mixer",
        "--hidden-import", "mutagen",
        "--hidden-import", "mutagen.flac",
        "--hidden-import", "mutagen.mp3",
        "--hidden-import", "openai",
        "--hidden-import", "win32api",
        "--hidden-import", "win32con",
        "--hidden-import", "win32gui",
        "--hidden-import", "win32ui",
        # Textual is NOT included — the pet uses its own PIL-based renderer
        # librosa, numpy, ddgs are NOT included (not needed by the pet)
        "--exclude-module", "textual",
        "--exclude-module", "librosa",
        "--exclude-module", "numpy",
        "--exclude-module", "ddgs",
        "--distpath", str(PROJECT_ROOT / "dist"),
        "--workpath", str(PROJECT_ROOT / "build"),
        "--specpath", str(PROJECT_ROOT / "build"),
    ]

    PyInstaller.__main__.run(args)

    exe = PROJECT_ROOT / "dist" / "HollePet.exe"
    if exe.exists():
        print(f"\n✅ HollePet.exe: {exe}")
    else:
        print(f"\n⚠️ Build completed but HollePet.exe not found.")


def main() -> None:
    _ensure_pyinstaller()

    build_terminal()
    build_pet()

    print("\n" + "=" * 60)
    print("Build complete!")
    print("Distributable EXEs:")
    for name in ["HolleMusic.exe", "HollePet.exe"]:
        p = PROJECT_ROOT / "dist" / name
        if p.exists():
            size_mb = p.stat().st_size / (1024 * 1024)
            print(f"  ✅ {name}  ({size_mb:.1f} MB)")
        else:
            print(f"  ⚠️ {name}  (not found)")
    print("=" * 60)


if __name__ == "__main__":
    main()
