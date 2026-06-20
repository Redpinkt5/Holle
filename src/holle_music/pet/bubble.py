"""Bubble state machine — manages input, response and mode state for the pet window."""

from __future__ import annotations

import time
from typing import Callable


class BubbleManager:
    """Pure state manager for bubbles drawn inside the layered pet window.

    This class no longer creates tkinter windows; it only tracks what bubble
    should be rendered and forwards user input to the registered callbacks.
    """

    # Auto-hide timeouts (seconds)
    MODE_TIMEOUT = 8.0
    LOADING_TIMEOUT = 30.0

    # Cursor blink period
    CURSOR_PERIOD = 0.53

    # Loading animation period
    LOADING_PERIOD = 0.4

    def __init__(
        self,
        parent_hwnd: int = 0,
        on_action: Callable[[str], None] | None = None,
        on_chat_submit: Callable[[str], None] | None = None,
    ) -> None:
        self._parent_hwnd = parent_hwnd
        self._on_action = on_action
        self._on_chat_submit = on_chat_submit

        self._state: str = "none"  # none | input | loading | response | mode
        self._pending_response: str | None = None

        # Input state
        self._input_text: str = ""
        self._input_focused: bool = False
        self._input_history: list[str] = []
        self._history_index: int = -1  # -1 means current (not yet submitted) input
        self._history_draft: str = ""
        self._input_selection: tuple[int, int] | None = None  # (start, end) exclusive

        # Loading state
        self._loading_frame: int = 0
        self._last_loading_update: float = 0.0
        self._loading_until: float = 0.0
        self._loading_overlay: str | None = None

        # Response state
        self._response_text: str = ""
        self._response_cover: Image.Image | None = None
        self._last_ai_response: str = ""
        self._merged: bool = False

        # Mode picker state
        self._mode_until: float = 0.0

        # Cursor blink state
        self._cursor_visible: bool = True
        self._last_cursor_toggle: float = 0.0

    # ── Public state queries ────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def input_text(self) -> str:
        return self._input_text

    @property
    def response_text(self) -> str:
        return self._response_text

    @property
    def cursor_visible(self) -> bool:
        return self._cursor_visible and self._state == "input"

    @property
    def mode_active(self) -> bool:
        return self._state == "mode"

    @property
    def loading_active(self) -> bool:
        return self._state == "loading"

    @property
    def loading_frame(self) -> int:
        return self._loading_frame

    @property
    def loading_overlay(self) -> str | None:
        return self._loading_overlay

    def set_loading_overlay(self, text: str) -> None:
        """Show extra status text below the loading dots without replacing them."""
        self._loading_overlay = text

    def clear_loading_overlay(self) -> None:
        """Clear the loading overlay text."""
        self._loading_overlay = None

    @property
    def has_active_bubble(self) -> bool:
        return self._state in ("input", "loading", "response", "mode")

    # ── Input lifecycle ─────────────────────────────────────────────────

    def show_input(self) -> None:
        """Open the input bubble and reset its text."""
        self.hide_mode_picker()
        self._state = "input"
        self._input_text = ""
        self._input_selection = None
        self._input_focused = True
        self._cursor_visible = True
        self._last_cursor_toggle = time.monotonic()

    def hide_input(self) -> None:
        """Close the input bubble without submitting."""
        if self._state == "input":
            self._state = "none"
            self._input_focused = False
            self._input_selection = None

    def toggle_input(self) -> None:
        """Open the input bubble if closed, or close it if already open."""
        if self._state == "input":
            self.hide_input()
        else:
            self.show_input()

    @property
    def input_selection(self) -> tuple[int, int] | None:
        """Return the current text selection as (start, end) or None."""
        return self._input_selection

    @property
    def input_selected_text(self) -> str:
        """Return the currently selected text, or all text if selection covers all."""
        if self._input_selection is None:
            return ""
        start, end = self._input_selection
        return self._input_text[start:end]

    def input_select_all(self) -> None:
        """Select all text in the input bubble."""
        if self._state != "input" or not self._input_text:
            return
        self._input_selection = (0, len(self._input_text))

    def input_copy(self) -> str:
        """Return the text that should be copied to the clipboard."""
        if self._state != "input":
            return ""
        if self._input_selection is not None:
            return self.input_selected_text
        return self._input_text

    def input_append(self, char: str) -> None:
        """Append a typed character to the input text."""
        if self._state != "input":
            return
        # Ignore control characters that slip through WM_CHAR
        if not char.isprintable():
            return
        if self._input_selection is not None:
            self._input_text = char
            self._input_selection = None
        else:
            self._input_text += char

    def input_paste(self, text: str) -> None:
        """Paste clipboard text into the input bubble."""
        if self._state != "input":
            return
        # Only accept printable text; strip carriage returns.
        cleaned = "".join(
            ch
            for ch in text.replace("\r\n", "\n").replace("\r", "\n")
            if ch.isprintable() or ch == "\n"
        )
        if self._input_selection is not None:
            self._input_text = cleaned
            self._input_selection = None
        else:
            self._input_text += cleaned

    def input_backspace(self) -> None:
        """Remove the last character from the input text."""
        if self._state != "input" or not self._input_text:
            return
        if self._input_selection is not None:
            self._input_text = ""
            self._input_selection = None
        else:
            self._input_text = self._input_text[:-1]

    def input_history_up(self) -> bool:
        """Show the previous history entry; return True if the text changed."""
        if self._state != "input" or not self._input_history:
            return False
        if self._history_index == -1:
            self._history_draft = self._input_text
        if self._history_index < len(self._input_history) - 1:
            self._history_index += 1
            self._input_text = self._input_history[-(self._history_index + 1)]
            return True
        return False

    def input_history_down(self) -> bool:
        """Show the next history entry or restore the draft; return True if changed."""
        if self._state != "input" or self._history_index == -1:
            return False
        self._history_index -= 1
        if self._history_index == -1:
            self._input_text = self._history_draft
        else:
            self._input_text = self._input_history[-(self._history_index + 1)]
        return True

    def submit_input(self) -> None:
        """Submit the current input text and close the input bubble."""
        if self._state != "input":
            return
        text = self._input_text.strip()
        self.hide_input()
        if text and self._on_chat_submit:
            # Save to history (avoid duplicate consecutive entries)
            if not self._input_history or self._input_history[-1] != text:
                self._input_history.append(text)
            # Reset history navigation
            self._history_index = -1
            self._history_draft = ""
            self._on_chat_submit(text)
            self.show_loading()

    # ── Response lifecycle ──────────────────────────────────────────────

    def queue_response(
        self, text: str, cover: Image.Image | None = None, append: bool = False, merge: bool = False
    ) -> None:
        """Queue a response to be displayed on the next update cycle."""
        self._pending_response = text
        self._pending_cover = cover
        self._pending_append = append
        self._pending_merge = merge

    @property
    def response_cover(self) -> Image.Image | None:
        return self._response_cover

    def show_response(
        self,
        text: str,
        cover: Image.Image | None = None,
        append: bool = False,
        merge: bool = False,
    ) -> None:
        """Display a response bubble; it stays until explicitly dismissed.

        If ``append`` is True and a response bubble is already visible, the new
        text is appended to the existing one instead of replacing it.

        If ``merge`` is True, the new text is merged with the last AI response
        text. This is used to combine an AI reply with the subsequent
        now-playing cover bubble while keeping the reply visible.
        """
        self.hide_input()
        self.hide_loading()
        self.hide_mode_picker()

        if merge and self._last_ai_response:
            text = f"{self._last_ai_response}\n\n{text}"
            self._merged = True

        if append and self._state == "response" and self._response_text:
            self._response_text = f"{self._response_text}\n\n{text}"
        else:
            self._response_text = text

        # Remember the last pure AI response so we can merge now-playing info later.
        if not merge and not append:
            self._last_ai_response = text
            self._merged = False

        self._response_cover = cover
        self._state = "response"

    def hide_response(self) -> None:
        """Close the response bubble immediately."""
        self._close_response()

    def _close_response(self) -> None:
        if self._state == "response":
            self._state = "none"
        self._response_text = ""
        self._response_cover = None
        self._last_ai_response = ""
        self._merged = False

    # ── Loading lifecycle ───────────────────────────────────────────────

    def show_loading(self) -> None:
        """Show a loading/thinking bubble while waiting for AI reply."""
        self.hide_input()
        self._close_response()
        self.hide_mode_picker()
        self._state = "loading"
        self._loading_frame = 0
        self._last_loading_update = time.monotonic()
        self._loading_until = time.monotonic() + self.LOADING_TIMEOUT

    def hide_loading(self) -> None:
        """Close the loading bubble."""
        if self._state == "loading":
            self._state = "none"
        self._loading_overlay = None

    # ── Mode picker lifecycle ───────────────────────────────────────────

    def show_mode_picker(self) -> None:
        """Open the mode picker bubble."""
        self.hide_input()
        self.hide_loading()
        self._close_response()
        self._state = "mode"
        self._mode_until = time.monotonic() + self.MODE_TIMEOUT

    def hide_mode_picker(self) -> None:
        """Close the mode picker bubble."""
        if self._state == "mode":
            self._state = "none"
        self._mode_until = 0.0

    def select_mode(self, mode: str) -> None:
        """Select a mode and notify via on_action."""
        if self._state != "mode":
            return
        self.hide_mode_picker()
        if self._on_action:
            self._on_action(f"set_mode:{mode}")

    # ── Update pump ─────────────────────────────────────────────────────

    def update(self) -> bool:
        """Process timers, cursor blink and loading animation.

        Returns True if the visual state changed and a redraw is needed.
        """
        changed = False
        now = time.monotonic()

        # Loading animation frame / timeout
        if self._state == "loading":
            if now - self._last_loading_update >= self.LOADING_PERIOD:
                self._loading_frame = (self._loading_frame + 1) % 3
                self._last_loading_update = now
                changed = True
            if now >= self._loading_until:
                self.hide_loading()
                self.show_response("请求超时，请重试")
                changed = True

        # Mode picker auto-hide
        if self._state == "mode" and now >= self._mode_until:
            self.hide_mode_picker()
            changed = True

        # Cursor blink for input bubble
        if self._state == "input":
            if now - self._last_cursor_toggle >= self.CURSOR_PERIOD:
                self._cursor_visible = not self._cursor_visible
                self._last_cursor_toggle = now
                changed = True

        return changed

    def take_pending_response(self) -> tuple[str | None, Image.Image | None, bool, bool]:
        """Return and clear any queued response text, cover, append and merge flags."""
        text = self._pending_response
        cover = getattr(self, "_pending_cover", None)
        append = getattr(self, "_pending_append", False)
        merge = getattr(self, "_pending_merge", False)
        self._pending_response = None
        self._pending_cover = None
        self._pending_append = False
        self._pending_merge = False
        return text, cover, append, merge

    # ── Backwards-compatible aliases ────────────────────────────────────

    def update_pet_rect(self, pet_rect: tuple[int, int, int, int]) -> None:
        """No-op: kept for backwards compatibility with older callers."""

    def destroy(self) -> None:
        """Reset all state."""
        self._state = "none"
        self._input_text = ""
        self._response_text = ""
        self._response_cover = None
        self._mode_until = 0.0
        self._loading_frame = 0
        self._last_loading_update = 0.0
        self._loading_until = 0.0
        self._pending_response = None
