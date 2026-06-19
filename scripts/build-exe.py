#!/usr/bin/env python3
"""Build standalone executables with PyInstaller.

Cross-platform build script. Run locally or in CI:

    python scripts/build-exe.py
    python scripts/build-exe.py --targets hollemusic
    python scripts/build-exe.py --targets hollemusic,hollepet --platform windows

Output files (in ``dist/``):
    - hollemusic[.exe]   — terminal TUI app (all platforms)
    - hollepet[.exe]     — desktop music assistant (Windows only)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SRC_DIR = PROJECT_ROOT / "src"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
ICON_PATH = PROJECT_ROOT / "assets" / "icon.ico"
PYINSTALLER_VERSION = "6.11.1"


def _platform_separator() -> str:
    """PyInstaller --add-data separator: ';' on Windows, ':' elsewhere."""
    return ";" if sys.platform == "win32" else ":"


def _exe_suffix() -> str:
    """Return '.exe' on Windows, empty otherwise."""
    return ".exe" if sys.platform == "win32" else ""


def _ensure_pyinstaller() -> None:
    try:
        import PyInstaller.__main__  # noqa: F401
    except ImportError:
        print(f"Installing PyInstaller {PYINSTALLER_VERSION}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", f"pyinstaller=={PYINSTALLER_VERSION}", "-q"]
        )


def _common_excludes() -> list[str]:
    """Exclude heavy/unused packages that bloat the executable."""
    return [
        "--exclude-module", "PyQt5",
        "--exclude-module", "PySide6",
        "--exclude-module", "torch",
        "--exclude-module", "IPython",
        "--exclude-module", "jupyter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "tkinter",
    ]


def build_terminal() -> Path:
    """Build hollemusic — the full terminal TUI app."""
    print("\n" + "=" * 60)
    print("Building hollemusic (terminal TUI app)...")
    print("=" * 60)

    sys.path.insert(0, str(SRC_DIR))
    import PyInstaller.__main__

    sep = _platform_separator()
    suffix = _exe_suffix()
    output_name = f"hollemusic{suffix}"

    args = [
        str(SRC_DIR / "holle_music" / "app.py"),
        "--name", "hollemusic",
        "--onefile",
        "--console",
        "--noconfirm",
        "--clean",
        "--icon", str(ICON_PATH),
        "--add-data", f"{SRC_DIR / 'holle_music'}{sep}holle_music",
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
        *_common_excludes(),
        "--collect-all", "textual",
        "--collect-all", "pygame",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(BUILD_DIR),
    ]

    if sys.platform == "win32":
        args.extend([
            "--hidden-import", "win32api",
            "--hidden-import", "win32con",
            "--hidden-import", "win32gui",
            "--hidden-import", "win32ui",
        ])

    PyInstaller.__main__.run(args)

    exe = DIST_DIR / output_name
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"\n[OK] hollemusic{suffix}: {exe} ({size_mb:.1f} MB)")
    else:
        print(f"\n[WARN] Build completed but hollemusic{suffix} not found.")
    return exe


def build_pet() -> Path | None:
    """Build hollepet — the desktop music assistant (Windows only)."""
    if sys.platform != "win32":
        print("\n[SKIP] hollepet is Windows-only (requires pywin32 / Win32 API)")
        return None

    print("\n" + "=" * 60)
    print("Building hollepet (desktop music assistant)...")
    print("=" * 60)

    import PyInstaller.__main__

    sep = _platform_separator()
    suffix = _exe_suffix()
    output_name = f"hollepet{suffix}"

    args = [
        str(SRC_DIR / "holle_music" / "pet" / "main.py"),
        "--name", "hollepet",
        "--onefile",
        "--console",
        "--noconfirm",
        "--clean",
        "--icon", str(ICON_PATH),
        "--add-data", f"{SRC_DIR / 'holle_music'}{sep}holle_music",
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
        "--exclude-module", "textual",
        "--exclude-module", "librosa",
        "--exclude-module", "numpy",
        "--exclude-module", "ddgs",
        *_common_excludes(),
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(BUILD_DIR),
    ]

    PyInstaller.__main__.run(args)

    exe = DIST_DIR / output_name
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"\n[OK] hollepet{suffix}: {exe} ({size_mb:.1f} MB)")
    else:
        print(f"\n[WARN] Build completed but hollepet{suffix} not found.")
    return exe


def build_installer(version: str) -> Path | None:
    """Build Windows installer using Inno Setup (Windows only)."""
    if sys.platform != "win32":
        print("\n[SKIP] Installer build is Windows-only")
        return None

    iss_path = PROJECT_ROOT / "scripts" / "HolleMusic-Setup.iss"
    if not iss_path.exists():
        print(f"\n[WARN] Installer script not found: {iss_path}")
        return None

    print("\n" + "=" * 60)
    print("Building Windows installer with Inno Setup...")
    print("=" * 60)

    env = os.environ.copy()
    env["HOLLE_VERSION"] = version
    try:
        subprocess.run(["iscc", str(iss_path)], env=env, check=True)
    except FileNotFoundError:
        print("\n[WARN] iscc.exe not found. Install Inno Setup and add it to PATH.")
        print("       https://jrsoftware.org/isdl.php")
        return None
    except subprocess.CalledProcessError as e:
        print(f"\n[WARN] Inno Setup build failed: {e}")
        return None

    installer = DIST_DIR / f"HolleMusic-Setup-{version}.exe"
    if installer.exists():
        size_mb = installer.stat().st_size / (1024 * 1024)
        print(f"\n[OK] Installer: {installer} ({size_mb:.1f} MB)")
        return installer
    print(f"\n[WARN] Installer not found after build: {installer}")
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Holle Music executables")
    parser.add_argument(
        "--targets",
        default="hollemusic,hollepet",
        help="Comma-separated targets: hollemusic,hollepet",
    )
    parser.add_argument(
        "--platform",
        default="",
        help="Platform name (windows, linux, macos) for logging",
    )
    parser.add_argument(
        "--build-installer",
        action="store_true",
        help="Build Windows installer after EXEs (Windows only)",
    )
    args = parser.parse_args()

    _ensure_pyinstaller()
    sys.path.insert(0, str(SRC_DIR))

    targets = {t.strip() for t in args.targets.split(",")}
    platform_label = f" [{args.platform}]" if args.platform else ""
    print(f"Building targets: {targets}{platform_label}")

    built: list[Path] = []
    if "hollemusic" in targets:
        built.append(build_terminal())
    if "hollepet" in targets:
        pet = build_pet()
        if pet:
            built.append(pet)

    if args.build_installer:
        version = args.platform or "0.0.0"
        # In CI, the version comes from the release tag; use a placeholder locally.
        if version == "windows":
            version = "0.0.0"
        installer = build_installer(version)
        if installer:
            built.append(installer)

    print("\n" + "=" * 60)
    print("Build complete!")
    for p in built:
        if p.exists():
            size_mb = p.stat().st_size / (1024 * 1024)
            print(f"  [OK] {p.name}  ({size_mb:.1f} MB)")
        else:
            print(f"  [WARN] {p.name}  (not found)")
    print("=" * 60)


if __name__ == "__main__":
    main()
