#!/usr/bin/env python3
"""Build standalone executable with PyInstaller."""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SRC_DIR = PROJECT_ROOT / "src"


def main() -> None:
    try:
        import PyInstaller.__main__
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller", "-q"])

    # Ensure package is importable during build
    sys.path.insert(0, str(SRC_DIR))

    # PyInstaller arguments
    args = [
        str(SRC_DIR / "holle_music" / "app.py"),
        "--name", "Holle",
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
        "--collect-all", "textual",
        "--collect-all", "pygame",
        "--distpath", str(PROJECT_ROOT / "dist"),
        "--workpath", str(PROJECT_ROOT / "build"),
        "--specpath", str(PROJECT_ROOT / "build"),
    ]

    print(f"Building executable with PyInstaller...")
    print(f"Command: pyinstaller {' '.join(args)}")

    import PyInstaller.__main__
    PyInstaller.__main__.run(args)

    exe_path = PROJECT_ROOT / "dist" / "Holle.exe"
    if exe_path.exists():
        print(f"\n✅ Build successful: {exe_path}")
    else:
        alt = PROJECT_ROOT / "dist" / "Holle"
        if alt.exists():
            print(f"\n✅ Build successful: {alt}")
        else:
            print(f"\n⚠️ Build completed but executable not found in expected location.")


if __name__ == "__main__":
    main()
