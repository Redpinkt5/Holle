"""Desktop pet entry point."""

from __future__ import annotations

from holle_music.pet.chat_dialog import ChatDialog
from holle_music.pet.player_proxy import PetPlayer
from holle_music.pet.window import PetWindow


def main() -> None:
    """Start the desktop pet."""
    player = PetPlayer()
    chat = ChatDialog()

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
            # Show chat dialog below the window
            # Get window position from PetWindow if possible
            # For now, center on screen
            try:
                import win32api
                sw = win32api.GetSystemMetrics(0)
                sh = win32api.GetSystemMetrics(1)
                x = sw // 2 - 160
                y = sh // 2 - 120
            except ImportError:
                x, y = 100, 100
            chat.show(x, y)

    window = PetWindow(on_action=on_action, dialog=chat)

    print("Holle Pet started!")
    print("Click: center=play/pause | left/right=prev/next | top=mode | bottom=chat")
    print("Drag to move. Right-click for menu.")

    window.show()


if __name__ == "__main__":
    main()
