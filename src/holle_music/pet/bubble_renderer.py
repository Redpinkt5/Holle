"""BubbleRenderer — renders speech/chat bubbles as RGBA images using Pillow."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont


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
BUBBLE_RADIUS = 12                 # 气泡圆角
FONT_SIZE = 13                     # 默认字体大小
CHAR_WIDTH_EST = 7                 # 每字符估算宽度（px）


class BubbleRenderer:
    """Render mode-switch and chat bubbles as RGBA images for Win32 layered windows."""

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

    # ── Font helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Return a TrueType font if available, else default bitmap font."""
        for name in ("msyh.ttc", "msyh.ttf", "simhei.ttf", "arial.ttf", "segoeui.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _text_width(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
        """Return pixel width of text using font.getlength if available."""
        try:
            return int(font.getlength(text))
        except Exception:
            return len(text) * CHAR_WIDTH_EST
