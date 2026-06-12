"""Desktop pet entry point."""

from __future__ import annotations

from pathlib import Path

from holle_music.pet.ai_tools import AITools
from holle_music.pet.deepseek_api import DeepSeekService
from holle_music.pet.player_proxy import PetPlayer
from holle_music.pet.window import PetWindow


def main() -> None:
    """Start the desktop pet."""
    player = PetPlayer()
    ai = DeepSeekService()
    tools = AITools(player)

    # Try to restore state from terminal (do NOT auto-play)
    state = player.get_state()
    playlist_songs = []
    if state.get("playlist"):
        from holle_music.models import Song
        playlist_songs = [Song(**s) for s in state["playlist"]]

    # Fallback: scan default music directory if no playlist
    if not playlist_songs:
        default_path = Path("E:/Music")
        if default_path.exists():
            try:
                from holle_music.scanner import Scanner
                scanner = Scanner()
                playlist = scanner.scan_to_playlist(default_path, name=default_path.name)
                playlist_songs = list(playlist.songs)
                print(f"[PET] Scanned {len(playlist_songs)} songs from {default_path}")
            except Exception as e:
                print(f"[PET] Scan failed: {e}")

    if playlist_songs:
        player.load_playlist(playlist_songs)

        if state.get("song"):
            # Restore current song index without playing
            for i, s in enumerate(playlist_songs):
                if s.title == state["song"].get("title"):
                    if hasattr(player, '_standalone_player') and player._standalone_player:
                        player._standalone_player._current_index = i
                    break

        if state.get("volume") is not None:
            player.set_volume(state["volume"] / 100.0)

        # Do NOT auto-play; wait for user click
        # if state.get("playing"):
        #     player.toggle_play()

    def on_action(zone: str) -> None:
        if zone == "center":
            player.toggle_play()
        elif zone == "left":
            player.prev_track()
        elif zone == "right":
            player.next_track()
        elif zone == "top":
            player.cycle_mode()
        elif zone == "volume_up":
            player.volume_up()
        elif zone == "volume_down":
            player.volume_down()
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

    window = PetWindow(on_action=on_action)
    window._on_player_state_check = lambda: player.is_playing

    # AI chat handling
    def on_chat_send(text: str) -> None:
        if not text:
            return

        def ai_worker():
            try:
                result = ai.chat(text)
                reply = None
                if result["type"] == "tool_calls":
                    for call in result["calls"]:
                        tool_result = tools.execute(call["name"], call["arguments"])
                        final = ai.submit_tool_result(call["id"], tool_result)
                        if final.get("content"):
                            reply = final["content"]
                elif result.get("content"):
                    reply = result["content"]
                if reply and hasattr(window, 'show_response_bubble'):
                    window.show_response_bubble(reply)
            except Exception as e:
                if hasattr(window, 'show_response_bubble'):
                    window.show_response_bubble(f"出错: {e}")

        import threading
        threading.Thread(target=ai_worker, daemon=True).start()

    window.set_chat_submit_callback(on_chat_send)

    print("Holle Pet started!")
    print("Click: center=play/pause | left/right=prev/next | top=mode | bottom=chat")
    print("Drag to move. Right-click for menu. Middle-click to switch to terminal.")

    window.show()


if __name__ == "__main__":
    main()
