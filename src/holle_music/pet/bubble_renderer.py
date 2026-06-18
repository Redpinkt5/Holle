"""BubbleRenderer — renders speech/chat bubbles as RGBA images using Pillow."""

from __future__ import annotations

import io
from PIL import Image, ImageDraw, ImageFont

from holle_music.shared import _SHIMMER_PALETTES, get_shimmer_palette


# ── Visual constants ──────────────────────────────────────────────────────────
BG_COLOR = (35, 35, 35, 240)       # 半透明黑背景
TEXT_COLOR = (255, 255, 255)       # 白色文字
ACCENT_COLOR = (255, 105, 180)     # 粉色（用户消息）
BUTTON_CONFIRM = (0, 150, 0, 220)  # 绿色确认按钮
BUTTON_CANCEL = (150, 0, 0, 220)   # 红色取消按钮
ARROW_HEIGHT = 14                  # 向下箭头高度
ARROW_WIDTH = 20                   # 向下箭头底边宽度
PADDING = 14                       # 内边距
LINE_SPACING = 4                   # 行间距
BUTTON_HEIGHT = 28                 # 按钮高度
BUTTON_RADIUS = 6                  # 按钮圆角
BUBBLE_RADIUS = 0                  # 气泡圆角（0 为直角）
FONT_SIZE = 13                     # 默认字体大小
CHAR_WIDTH_EST = 7                 # 每字符估算宽度（px）


class BubbleRenderer:
    """Render mode-switch and chat bubbles as RGBA images for Win32 layered windows."""

    # Font preference lists. Different character classes need different fonts
    # because no single Windows system font covers Latin, CJK and color emoji.
    _NORMAL_FONT_NAMES = ("msyh.ttc", "msyh.ttf", "simhei.ttf", "arial.ttf", "segoeui.ttf")
    _EMOJI_FONT_NAMES = ("seguiemj.ttf", "segoeuiemoji.ttf", "NotoColorEmoji.ttf")

    # Per-size font cache to avoid reloading fonts every render.
    _FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def render_mode_bubble(
        self,
        current_mode: str,
        target_mode: str,
        width: int = 220,
        height: int = 110,
    ) -> Image.Image:
        """Render a mode-switch confirmation bubble.

        Args:
            current_mode: Current play mode name (e.g. "顺序播放").
            target_mode: Target play mode name to switch to.
            width: Bubble width in pixels.
            height: Bubble height in pixels.

        Returns:
            RGBA Image with rounded-rect background, downward arrow,
            text lines, and Confirm / Cancel buttons.
        """
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = self._get_font(FONT_SIZE)
        small_font = self._get_font(FONT_SIZE - 1)

        # Background (rounded rect + arrow)
        self._draw_rounded_rect(draw, (0, 0, width, height - ARROW_HEIGHT), BUBBLE_RADIUS, BG_COLOR)
        self._draw_arrow_down(draw, width // 2, height - ARROW_HEIGHT, ARROW_WIDTH, ARROW_HEIGHT, BG_COLOR)

        # Text
        y = PADDING
        draw.text((PADDING, y), f"当前: {current_mode}", fill=TEXT_COLOR, font=font)
        y += FONT_SIZE + LINE_SPACING + 4
        draw.text((PADDING, y), f"切换为 {target_mode}?", fill=TEXT_COLOR, font=font)
        y += FONT_SIZE + LINE_SPACING + 8

        # Buttons
        btn_w = (width - PADDING * 3) // 2
        btn_h = BUTTON_HEIGHT
        btn_y = height - ARROW_HEIGHT - btn_h - PADDING // 2

        confirm_bbox = (PADDING, btn_y, PADDING + btn_w, btn_y + btn_h)
        cancel_bbox = (width - PADDING - btn_w, btn_y, width - PADDING, btn_y + btn_h)

        self._draw_button(draw, confirm_bbox, "确认", BUTTON_CONFIRM)
        self._draw_button(draw, cancel_bbox, "取消", BUTTON_CANCEL)

        return img

    def render_chat_bubble(
        self,
        messages: list[tuple[str, str]],
        width: int = 300,
        height: int = 250,
    ) -> Image.Image:
        """Render a chat history bubble with input hint at bottom.

        Args:
            messages: List of (role, text) tuples. Role is "user" or "ai".
            width: Bubble width in pixels.
            height: Bubble height in pixels.

        Returns:
            RGBA Image with rounded-rect background, downward arrow,
            recent messages, and an input-hint area at the bottom.
        """
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = self._get_font(FONT_SIZE)
        small_font = self._get_font(FONT_SIZE - 1)

        # Background
        self._draw_rounded_rect(draw, (0, 0, width, height - ARROW_HEIGHT), BUBBLE_RADIUS, BG_COLOR)
        self._draw_arrow_down(draw, width // 2, height - ARROW_HEIGHT, ARROW_WIDTH, ARROW_HEIGHT, BG_COLOR)

        # Input area hint at bottom
        input_h = 34
        input_y = height - ARROW_HEIGHT - input_h - PADDING // 2
        self._draw_rounded_rect(
            draw,
            (PADDING, input_y, width - PADDING, input_y + input_h),
            4,
            (50, 50, 50, 220),
        )
        hint = "在下方输入，按 Enter 发送"
        tw = self._text_width(hint, small_font)
        draw.text(
            ((width - tw) // 2, input_y + (input_h - FONT_SIZE) // 2),
            hint,
            fill=(180, 180, 180),
            font=small_font,
        )

        # Show last 5 messages above input area
        recent = messages[-5:]
        content_top = PADDING // 2
        content_bottom = input_y - PADDING // 2
        available_h = content_bottom - content_top
        line_h = FONT_SIZE + LINE_SPACING
        max_lines = max(1, available_h // line_h)

        y = content_top
        max_text_w = width - PADDING * 2

        for role, text in recent:
            is_user = role == "user"
            color = ACCENT_COLOR if is_user else TEXT_COLOR
            align = "right" if is_user else "left"

            wrapped = self._wrap_text(text, max_text_w)
            lines_for_msg = wrapped[:max(1, max_lines // len(recent))]
            for line in lines_for_msg:
                if y + line_h > content_bottom:
                    break
                if align == "right":
                    tw = self._text_width(line, font)
                    x = width - PADDING - tw
                else:
                    x = PADDING
                draw.text((x, y), line, fill=color, font=font)
                y += line_h
            y += 2  # small gap between messages

        return img

    def render_input_bubble(
        self,
        text: str,
        cursor_visible: bool = True,
        height: int = 40,
        max_width: int = 320,
        min_width: int = 120,
    ) -> Image.Image:
        """Render a single-line input bubble with a cursor.

        The bubble width grows with the text up to ``max_width``.
        The cursor color follows the current shimmer palette.

        Args:
            text: Current input text.
            cursor_visible: Whether to draw the text cursor.
            height: Bubble height in pixels.
            max_width: Maximum bubble width in pixels.
            min_width: Minimum bubble width in pixels.

        Returns:
            RGBA Image with rounded black background, white text and colored cursor.
        """
        font = self._get_font(FONT_SIZE)
        hint = "/help以查看帮助"
        display_text = text if text else hint
        text_w = self._text_width_mixed(display_text, FONT_SIZE)
        width = max(min_width, min(max_width, text_w + PADDING * 2 + 16))

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        self._draw_rounded_rect(draw, (0, 0, width, height), BUBBLE_RADIUS, (0, 0, 0, 240))

        x = PADDING
        y = (height - FONT_SIZE) // 2
        if text:
            drawn_w = self._draw_text_mixed(draw, (x, y), text, FONT_SIZE, TEXT_COLOR)
        else:
            # Show a placeholder hint when the input is empty.
            self._draw_text_mixed(
                draw, (x, y), hint, FONT_SIZE, (180, 180, 180)
            )
            drawn_w = 0

        if cursor_visible:
            cursor_x = x + drawn_w + 1
            cursor_top = y - 2
            cursor_bottom = y + FONT_SIZE + 2
            draw.line(
                [(cursor_x, cursor_top), (cursor_x, cursor_bottom)],
                fill=self._cursor_color(),
                width=2,
            )

        return img

    @staticmethod
    def _cursor_color() -> tuple[int, int, int]:
        """Return the current shimmer palette color as an RGB tuple."""
        name = get_shimmer_palette()
        hex_color = _SHIMMER_PALETTES.get(name, _SHIMMER_PALETTES["pink"])[0]
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    def render_response_bubble(
        self,
        text: str,
        cover_image: Image.Image | None = None,
        max_width: int = 280,
        min_width: int = 80,
    ) -> Image.Image:
        """Render a multi-line response bubble with optional cover art.

        The bubble width and height are calculated from the rendered text so that
        short replies stay compact and long replies fill up to ``max_width``.
        The style matches the input bubble: rounded black rectangle, no arrow.

        Args:
            text: Response text to display.
            cover_image: Optional RGBA cover image to show above the text.
            max_width: Maximum bubble width in pixels.
            min_width: Minimum bubble width in pixels.

        Returns:
            RGBA Image with rounded black background and wrapped text.
        """
        # Wrap once at the maximum allowed text width using mixed fonts.
        # Preserve explicit line breaks from the caller (e.g. playlist formatting).
        raw_lines = text.split("\n")
        wrapped: list[str] = []
        for raw in raw_lines:
            wrapped.extend(self._wrap_text_by_width(raw, FONT_SIZE, max_width - PADDING * 2))
        if not wrapped:
            wrapped = [text]

        # Determine the actual width needed for the wrapped lines.
        line_widths = [self._text_width_mixed(line, FONT_SIZE) for line in wrapped]
        content_w = max(line_widths) if line_widths else 0
        width = max(min_width, min(max_width, content_w + PADDING * 2))

        # Re-wrap to the chosen width so the text definitely fits.
        final_w = width - PADDING * 2
        wrapped = self._wrap_text_by_width(text, FONT_SIZE, final_w)
        line_widths = [self._text_width_mixed(line, FONT_SIZE) for line in wrapped]
        content_w = max(line_widths) if line_widths else 0
        # Tighten width if the re-wrapped text is narrower.
        width = max(min_width, min(width, content_w + PADDING * 2))

        # Scale cover art to match bubble width and compute its layout space.
        cover_w = 0
        cover_h = 0
        cover_scaled: Image.Image | None = None
        if cover_image is not None:
            cover_w = width - PADDING * 2
            cover_h = int(cover_w * cover_image.height / cover_image.width)
            cover_scaled = cover_image.resize((cover_w, cover_h), Image.Resampling.LANCZOS)
            width = max(width, cover_w + PADDING * 2)

        line_h = FONT_SIZE + LINE_SPACING
        content_h = len(wrapped) * line_h
        text_top = (cover_h + PADDING) if cover_image else 0
        height = content_h + text_top + PADDING * 2

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Solid black to match the input bubble style.
        response_bg = (0, 0, 0, 240)
        self._draw_rounded_rect(draw, (0, 0, width, height), BUBBLE_RADIUS, response_bg)

        # Paste cover art centered at the top, scaled to match bubble width.
        if cover_scaled is not None:
            cx = (width - cover_w) // 2
            img.paste(cover_scaled, (cx, PADDING), cover_scaled)

        y = PADDING + text_top
        for line in wrapped:
            self._draw_text_mixed(draw, (PADDING, y), line, FONT_SIZE, TEXT_COLOR)
            y += line_h

        return img

    def render_loading_bubble(
        self,
        frame: int = 0,
        overlay: str | None = None,
        height: int = 50,
    ) -> Image.Image:
        """Render a loading/thinking bubble with animated dots.

        Args:
            frame: Animation frame (0-2) controlling the number of dots.
            overlay: Optional status text shown below the dots (e.g. mode switch).
            height: Minimum bubble height in pixels.

        Returns:
            RGBA Image with rounded black background and wrapped text.
        """
        dots = "." * ((frame % 3) + 1)
        text = f"思考中{dots}"

        font = self._get_font(FONT_SIZE)
        text_w = self._text_width(text, font)

        overlay_lines: list[str] = []
        if overlay:
            overlay_lines = self._wrap_text_by_width(
                overlay, FONT_SIZE, 260
            )

        overlay_w = max(
            (self._text_width_mixed(line, FONT_SIZE) for line in overlay_lines),
            default=0,
        )
        width = max(90, text_w + PADDING * 2, overlay_w + PADDING * 2)

        line_h = FONT_SIZE + LINE_SPACING
        content_h = line_h
        if overlay_lines:
            content_h += len(overlay_lines) * line_h
        height = max(height, content_h + PADDING * 2)

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        bg = (0, 0, 0, 240)
        self._draw_rounded_rect(draw, (0, 0, width, height), BUBBLE_RADIUS, bg)

        x = (width - text_w) // 2
        y = PADDING
        draw.text((x, y), text, fill=TEXT_COLOR, font=font)

        if overlay_lines:
            y += line_h
            for line in overlay_lines:
                line_w = self._text_width_mixed(line, FONT_SIZE)
                x = (width - line_w) // 2
                self._draw_text_mixed(draw, (x, y), line, FONT_SIZE, TEXT_COLOR)
                y += line_h

        return img

    def render_mode_picker(
        self,
        current_mode: str,
        width: int = 180,
        height: int = 60,
    ) -> Image.Image:
        """Render the play-mode picker with three white square buttons.

        Args:
            current_mode: One of "sequential", "random", "repeat".
            width: Bubble width in pixels.
            height: Bubble height in pixels.

        Returns:
            RGBA Image with black rounded background and three mode squares.
        """
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        self._draw_rounded_rect(draw, (0, 0, width, height), BUBBLE_RADIUS, (0, 0, 0, 240))

        modes = [
            ("sequential", "顺序"),
            ("random", "随机"),
            ("repeat", "循环"),
        ]
        sq = 40
        total_content = sq * 3
        remaining = width - total_content - PADDING * 2
        gap = remaining // 2
        y = (height - sq) // 2
        label_font = self._get_font(11)

        for i, (mode, label) in enumerate(modes):
            x = PADDING + i * (sq + gap)
            draw.rectangle([x, y, x + sq, y + sq], fill=(255, 255, 255, 255))
            if mode == current_mode:
                draw.rectangle(
                    [x - 2, y - 2, x + sq + 2, y + sq + 2],
                    outline=ACCENT_COLOR,
                    width=2,
                )
            tw = self._text_width(label, label_font)
            th = 11
            draw.text(
                (x + (sq - tw) // 2, y + (sq - th) // 2),
                label,
                fill=(20, 20, 20, 255),
                font=label_font,
            )

        return img

    @staticmethod
    def extract_cover_image(path: str, size: tuple[int, int] = (100, 100)) -> Image.Image | None:
        """Extract album cover from an audio file and return a resized RGBA image.

        Returns None if no cover art is found or extraction fails.
        """
        try:
            from mutagen import File as MutagenFile

            audio = MutagenFile(path)
            if audio is None:
                return None
            data = None
            if hasattr(audio, "pictures") and audio.pictures:
                data = audio.pictures[0].data
            if not data and hasattr(audio, "tags"):
                for tag in audio.tags.values():
                    if getattr(tag, "FrameID", "") == "APIC":
                        data = tag.data
                        break
            if not data:
                return None
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            img = img.resize(size, Image.Resampling.LANCZOS)
            return img
        except Exception:
            return None

    # ── Drawing helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _draw_rounded_rect(
        draw: ImageDraw.Draw,
        bbox: tuple[int, int, int, int],
        radius: int,
        color: tuple[int, ...],
    ) -> None:
        """Draw a filled rounded rectangle."""
        x0, y0, x1, y1 = bbox
        draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=color)

    @staticmethod
    def _draw_arrow_down(
        draw: ImageDraw.Draw,
        cx: int,
        y: int,
        w: int,
        h: int,
        color: tuple[int, ...],
    ) -> None:
        """Draw a downward-pointing triangle arrow below the bubble."""
        half = w // 2
        draw.polygon([(cx - half, y), (cx + half, y), (cx, y + h)], fill=color)

    def _draw_button(
        self,
        draw: ImageDraw.Draw,
        bbox: tuple[int, int, int, int],
        text: str,
        color: tuple[int, ...],
    ) -> None:
        """Draw a rounded button with centered text."""
        self._draw_rounded_rect(draw, bbox, BUTTON_RADIUS, color)
        font = self._get_font(FONT_SIZE)
        tw = self._text_width(text, font)
        th = FONT_SIZE
        x0, y0, x1, y1 = bbox
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        tx = cx - tw // 2
        ty = cy - th // 2
        draw.text((tx, ty), text, fill=TEXT_COLOR, font=font)

    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        """Simple word-wrap by spaces, estimating ~7px per character."""
        max_chars = max(1, max_width // CHAR_WIDTH_EST)
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= max_chars:
                current += " " + word
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines if lines else [text]

    def _wrap_text_by_width(
        self,
        text: str,
        size: int,
        max_width: int,
    ) -> list[str]:
        """Wrap text using actual font metrics, supporting mixed CJK/emoji/Latin.

        CJK characters and emoji are treated as individual tokens so Chinese and
        emoji sequences wrap correctly; Latin words are kept whole when they fit.
        """
        import re

        # CJK ranges + Hangul syllables + emoji blocks.
        # Each CJK char and each emoji becomes its own token; Latin words stay together.
        tokens = re.findall(
            r"[\U0001F300-\U0001FAFF]|"
            r"[一-鿿぀-ゟ゠-ヿ가-힯]|"
            r"\S+|\s+",
            text,
            re.UNICODE,
        )

        lines: list[str] = []
        current = ""
        current_width = 0

        for token in tokens:
            # Collapse whitespace between words.
            if token.isspace():
                if current:
                    current += " "
                    current_width = self._text_width_mixed(current, size)
                continue

            test = current + token if current else token
            test_w = self._text_width_mixed(test, size)

            if test_w <= max_width:
                current = test
                current_width = test_w
            else:
                if current:
                    lines.append(current.strip())
                current = token
                current_width = self._text_width_mixed(token, size)

        if current:
            lines.append(current.strip())

        return lines if lines else [text]

    # ── Font helpers ──────────────────────────────────────────────────────────

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Return the normal UI font (CJK + Latin)."""
        return self._load_font(self._NORMAL_FONT_NAMES, size)

    def _get_emoji_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Return the emoji font, falling back to the normal font."""
        try:
            return self._load_font(self._EMOJI_FONT_NAMES, size)
        except Exception:
            return self._get_font(size)

    def _load_font(
        self,
        names: tuple[str, ...],
        size: int,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Load and cache a font by name list + size."""
        for name in names:
            key = (name, size)
            if key in self._FONT_CACHE:
                return self._FONT_CACHE[key]
            try:
                font = ImageFont.truetype(name, size)
                self._FONT_CACHE[key] = font
                return font
            except Exception:
                continue
        return ImageFont.load_default()

    def _font_for_char(
        self,
        char: str,
        size: int,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Pick a font that is most likely to render ``char`` correctly."""
        if self._is_emoji_char(char):
            return self._get_emoji_font(size)
        return self._get_font(size)

    @staticmethod
    def _is_emoji_char(char: str) -> bool:
        """Return True if ``char`` is an emoji or emoji modifier."""
        if not char:
            return False
        cp = ord(char)
        # Common emoji blocks and symbol ranges.
        if (
            0x1F300 <= cp <= 0x1F5FF
            or 0x1F600 <= cp <= 0x1F64F
            or 0x1F680 <= cp <= 0x1F6FF
            or 0x1F700 <= cp <= 0x1F77F
            or 0x1F780 <= cp <= 0x1F7FF
            or 0x1F800 <= cp <= 0x1F8FF
            or 0x1F900 <= cp <= 0x1F9FF
            or 0x1FA00 <= cp <= 0x1FA6F
            or 0x1FA70 <= cp <= 0x1FAFF
            or 0x2600 <= cp <= 0x26FF
            or 0x2700 <= cp <= 0x27BF
            or 0x2300 <= cp <= 0x23FF
            or cp in (0x2764, 0x2B50, 0x2B55, 0x2615, 0x26A1)
        ):
            return True
        # Emoji modifiers: skin tones, variation selectors, ZWJ, keycap base.
        if 0x1F3FB <= cp <= 0x1F3FF or cp in (0xFE0E, 0xFE0F, 0x200D, 0x20E3):
            return True
        return False

    def _segment_by_font(
        self,
        text: str,
        size: int,
    ) -> list[tuple[str, ImageFont.FreeTypeFont | ImageFont.ImageFont]]:
        """Split text into consecutive runs using the same font."""
        if not text:
            return [("", self._get_font(size))]
        segments: list[tuple[str, ImageFont.FreeTypeFont | ImageFont.ImageFont]] = []
        current = ""
        current_font: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None
        for char in text:
            font = self._font_for_char(char, size)
            if current_font is None:
                current = char
                current_font = font
            elif font is current_font:
                current += char
            else:
                segments.append((current, current_font))
                current = char
                current_font = font
        if current and current_font is not None:
            segments.append((current, current_font))
        return segments

    def _text_width_mixed(self, text: str, size: int) -> int:
        """Measure width of text that may contain emoji."""
        width = 0
        for seg_text, seg_font in self._segment_by_font(text, size):
            width += self._text_width(seg_text, seg_font)
        return width

    def _draw_text_mixed(
        self,
        draw: ImageDraw.Draw,
        xy: tuple[int, int],
        text: str,
        size: int,
        fill: tuple[int, ...],
    ) -> int:
        """Draw mixed-language/emoji text, returning the pixel width drawn."""
        x, y = xy
        total_w = 0
        for seg_text, seg_font in self._segment_by_font(text, size):
            draw.text((x, y), seg_text, fill=fill, font=seg_font)
            seg_w = self._text_width(seg_text, seg_font)
            x += seg_w
            total_w += seg_w
        return total_w

    def _truncate_line(self, text: str, max_width: int, size: int = FONT_SIZE) -> str:
        """Return text truncated with '...' if it exceeds max_width."""
        if self._text_width_mixed(text, size) <= max_width:
            return text
        suffix = "..."
        suffix_w = self._text_width_mixed(suffix, size)
        available = max_width - suffix_w
        if available <= 0:
            return text[: max(1, len(text) // 2)] + suffix
        while text and self._text_width_mixed(text, size) > available:
            text = text[:-1]
        return text + suffix

    @staticmethod
    def _text_width(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
        """Return pixel width of text using font.getlength if available."""
        try:
            return int(font.getlength(text))
        except Exception:
            return len(text) * CHAR_WIDTH_EST
