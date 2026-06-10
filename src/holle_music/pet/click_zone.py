class ClickZone:
    """Map click coordinates to action zones.

    Zones (normalized 0.0-1.0 coordinates):
        top:    (0.0, 0.0) to (1.0, 0.2)  -> cycle play mode
        left:   (0.0, 0.2) to (0.2, 0.8)  -> previous track
        center: (0.2, 0.2) to (0.8, 0.8)  -> toggle play/pause
        right:  (0.8, 0.2) to (1.0, 0.8)  -> next track
        bottom: (0.2, 0.8) to (0.8, 1.0)  -> open chat dialog
    """

    def detect(self, x: int, y: int, width: int, height: int) -> str:
        """Return zone name or empty string."""
        if width <= 0 or height <= 0:
            return ""

        nx = x / width
        ny = y / height

        if nx < 0.0 or nx > 1.0 or ny < 0.0 or ny > 1.0:
            return ""

        if ny < 0.2:
            if 0.2 <= nx <= 0.8:
                return "top"
            return ""
        if ny > 0.8:
            if 0.2 <= nx <= 0.8:
                return "bottom"
            return ""
        if nx < 0.2:
            return "left"
        if nx > 0.8:
            return "right"
        return "center"
