"""Desktop pet entry point."""

from __future__ import annotations

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
    if state.get("playlist"):
        from holle_music.models import Song
        songs = [Song(**s) for s in state["playlist"]]
        player.load_playlist(songs)

        if state.get("song"):
            # Restore current song index without playing
            for i, s in enumerate(songs):
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
        elif zone == "bottom":
            # Chat bubble is handled by BubbleManager in window.py
            pass

    window = PetWindow(on_action=on_action)
    window._on_player_state_check = lambda: player.is_playing

    # AI chat handling
    def on_chat_send(text: str) -> None:
        if not text:
            return
        if hasattr(window, '_bubble'):
            window._bubble.add_message("user", text)

        def ai_worker():
            try:
                result = ai.chat(text)
                if result["type"] == "tool_calls":
                    for call in result["calls"]:
                        tool_result = tools.execute(call["name"], call["arguments"])
                        final = ai.submit_tool_result(call["id"], tool_result)
                        if hasattr(window, '_bubble') and final.get("content"):
                            window._bubble.add_message("ai", final["content"])
                elif result.get("content"):
                    if hasattr(window, '_bubble'):
                        window._bubble.add_message("ai", result["content"])
            except Exception as e:
                if hasattr(window, '_bubble'):
                    window._bubble.add_message("ai", f"出错: {e}")

        import threading
        threading.Thread(target=ai_worker, daemon=True).start()

    window.set_chat_submit_callback(on_chat_send)

    print("Holle Pet started!")
    print("Click: center=play/pause | left/right=prev/next | top=mode | bottom=chat")
    print("Drag to move. Right-click for menu. Middle-click to switch to terminal.")

    window.show()


if __name__ == "__main__":
    main()
