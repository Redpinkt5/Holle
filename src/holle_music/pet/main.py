"""Desktop pet entry point."""

from __future__ import annotations

import json
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

from holle_music.pet.ai_tools import AITools
from holle_music.pet.commands import PetCommandHandler
from holle_music.pet.ark_api import ArkService
from holle_music.pet.player_proxy import PetPlayer
from holle_music.pet.window import PetWindow
from holle_music.settings import load_settings, set_setting
from holle_music.shared import set_shimmer_palette


def _log_error(exc: BaseException) -> None:
    """Write a crash traceback to a log file next to the executable."""
    try:
        if getattr(sys, "frozen", False):
            log_dir = Path(sys.executable).parent
        else:
            log_dir = Path.home() / ".holle_music"
            log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "hollepet-error.log"
        log_path.write_text(
            f"[{datetime.now().isoformat()}]\n{traceback.format_exc()}\n",
            encoding="utf-8",
        )
    except Exception:
        pass


def main() -> None:
    """Start the desktop pet."""
    player = PetPlayer()
    ai = ArkService()
    tools = AITools(player)

    # Load persisted user settings (color and volume) before restoring state.
    settings = load_settings()
    set_shimmer_palette(settings.get("color", "pink"))
    main_color = settings.get("main_color", "light")

    # Try to restore state from terminal (do NOT auto-play)
    state = player.get_state()
    playlist_songs = []
    if state.get("playlist"):
        from holle_music.models import Song
        # Ignore songs whose files no longer exist (e.g. the folder was deleted).
        playlist_songs = [
            Song(**s)
            for s in state["playlist"]
            if Path(s.get("path", "")).exists()
        ]
        if not playlist_songs:
            print("[PET] Restored playlist paths no longer exist")

    # Fallback: scan default music directory if no playlist
    no_playlist_prompt = False
    if not playlist_songs:
        default_path = Path(settings.get("music_dir", "E:/Music"))
        if default_path.exists():
            try:
                from holle_music.scanner import Scanner
                scanner = Scanner()
                playlist = scanner.scan_to_playlist(default_path, name=default_path.name)
                playlist_songs = list(playlist.songs)
                print(f"[PET] Scanned {len(playlist_songs)} songs from {default_path}")
            except Exception as e:
                print(f"[PET] Scan failed: {e}")
        if not playlist_songs:
            no_playlist_prompt = True

    if playlist_songs:
        player.load_playlist(playlist_songs)

        if state.get("song"):
            # Restore current song index without playing
            for i, s in enumerate(playlist_songs):
                if s.title == state["song"].get("title"):
                    if hasattr(player, '_standalone_player') and player._standalone_player:
                        player._standalone_player._current_index = i
                    break

        # Restore persisted volume and play mode (settings override transient IPC state).
        player.set_volume(settings.get("volume", 1.0))
        player.set_play_mode(settings.get("play_mode", "sequential"))

        # Do NOT auto-play; wait for user click
        # if state.get("playing"):
        #     player.toggle_play()

    def on_action(zone: str) -> None:
        print(f"[PET] action: {zone}")
        if zone == "center":
            player.toggle_play()
        elif zone == "left":
            player.prev_track()
            if window._bubble.state == "response" and "正在播放" in (window._bubble.response_text or ""):
                show_now_playing()
        elif zone == "right":
            player.next_track()
            if window._bubble.state == "response" and "正在播放" in (window._bubble.response_text or ""):
                show_now_playing()
        elif zone == "top":
            new_mode = player.cycle_mode()
            labels = {"sequential": "顺序播放", "random": "随机播放", "repeat": "单曲循环"}
            mode_label = labels.get(new_mode, new_mode)
            window.show_status_message(f"{mode_label}模式开启")
        elif zone == "volume_up":
            player.volume_up()
            window.set_volume(player.volume)
            set_setting("volume", player.volume)
        elif zone == "volume_down":
            player.volume_down()
            window.set_volume(player.volume)
            set_setting("volume", player.volume)
        elif zone.startswith("set_mode:"):
            target_mode = zone[9:]
            current = player.mode
            modes = ["sequential", "random", "repeat"]
            cur_idx = modes.index(current) if current in modes else 0
            target_idx = modes.index(target_mode) if target_mode in modes else 0
            steps = (target_idx - cur_idx) % len(modes)
            for _ in range(steps):
                player.cycle_mode()
        elif zone == "bottom":
            # Chat bubble is handled by BubbleManager in window.py
            pass

    def show_now_playing() -> None:
        song, next_songs = player.get_now_playing_info()
        lines: list[str] = []
        if song:
            lines.append(f"正在播放：{song.get('title', '未知')} - {song.get('artist', '未知')}")
        else:
            lines.append("正在播放：未在播放")

        # In repeat mode only show the current song; otherwise show upcoming songs.
        if player.mode != "repeat":
            lines.append("")
            lines.append("接下来:")
            if next_songs:
                for i, s in enumerate(next_songs[:10], 1):
                    lines.append(f"{i}. {s.get('title', '未知')} - {s.get('artist', '未知')}")
            else:
                lines.append("暂无")

        cover = None
        if song:
            try:
                path = song.get("path")
                if path:
                    from holle_music.pet.bubble_renderer import BubbleRenderer
                    cover = BubbleRenderer.extract_cover_image(str(path), size=(120, 120))
            except Exception:
                pass

        window.show_response_bubble("\n".join(lines), cover=cover)

    window = PetWindow(on_action=on_action, on_double_click=show_now_playing)
    window._on_player_state_check = lambda: player.is_playing
    window.set_volume_check(lambda: player.volume)
    window.set_volume(player.volume)

    def on_song_end_check() -> None:
        player.check_auto_advance()
        # If the now-playing bubble is still visible, refresh it with the new song.
        if (
            window._bubble.state == "response"
            and "正在播放" in (window._bubble.response_text or "")
        ):
            show_now_playing()

    window.set_song_end_check(on_song_end_check)
    window.set_terminal_check(lambda: player._is_main_app_running())
    window.set_main_color(main_color)

    def sync_settings_from_terminal() -> None:
        """Read the terminal state file and apply color/main_color changes."""
        try:
            state_path = Path.home() / ".holle_music" / "pet_state.json"
            if not state_path.exists():
                return
            data = json.loads(state_path.read_text(encoding="utf-8"))
            color = data.get("color")
            if color and color != get_shimmer_palette():
                set_shimmer_palette(color)
                window._update_display()
            main_color = data.get("main_color")
            if main_color and main_color != window._main_color:
                window.set_main_color(main_color)
        except Exception:
            pass
        # When running standalone, write our state back so the terminal can resume.
        player.write_state()

    window.set_settings_sync(sync_settings_from_terminal)

    # If no playlist was found at startup, show a friendly AI bubble guiding
    # the user to load songs with /scan.
    if no_playlist_prompt:
        window.show_response_bubble(
            "点击底部使用指令 /scan <音乐文件路径> 加载歌单 :)"
        )

    # AI chat handling
    command_handler = PetCommandHandler(player, tools, window)

    def on_chat_send(text: str) -> None:
        if not text:
            return

        handled, result = command_handler.try_handle(text)
        if handled:
            if result:
                window.show_response_bubble(result)
            return

        def ai_worker():
            def _friendly_error(exc: Exception) -> str:
                msg = str(exc).lower()
                if any(kw in msg for kw in ("connection", "connect", "timeout", "timed out")):
                    return "网络连接失败，请检查网络后重试。"
                return f"请求失败: {exc}"

            try:
                now = datetime.now()
                weekdays = {
                    "Monday": "星期一",
                    "Tuesday": "星期二",
                    "Wednesday": "星期三",
                    "Thursday": "星期四",
                    "Friday": "星期五",
                    "Saturday": "星期六",
                    "Sunday": "星期日",
                }
                time_ctx = (
                    f"当前系统时间: {now.strftime('%Y年%m月%d日 %H:%M:%S')} "
                    f"{weekdays[now.strftime('%A')]}。"
                )

                message = f"{time_ctx}\n\n{text}"

                reply = None
                try:
                    current = ai.chat(message)
                    for _ in range(5):
                        if current["type"] == "tool_calls":
                            tool_results = []
                            for call in current["calls"]:
                                tool_result = tools.execute(call["name"], call["arguments"])
                                tool_results.append((call["id"], tool_result))
                            current = ai.submit_tool_results(tool_results)
                        elif current.get("content"):
                            reply = current["content"]
                            break
                        else:
                            break
                except Exception as e:
                    window.show_response_bubble(_friendly_error(e))
                    return

                if reply and hasattr(window, 'show_response_bubble'):
                    window.show_response_bubble(reply)
                else:
                    window.show_response_bubble("AI 没有返回内容，请重试。")
            except Exception as e:
                if hasattr(window, 'show_response_bubble'):
                    window.show_response_bubble(_friendly_error(e))

        threading.Thread(target=ai_worker, daemon=True).start()

    window.set_chat_submit_callback(on_chat_send)

    print("Holle Pet started!")
    print("Click: center=play/pause | left/right=prev/next | top=mode | bottom=chat")
    print("Drag to move. Right-click for menu. Middle-click to switch to terminal.")

    window.show()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _log_error(e)
        raise
