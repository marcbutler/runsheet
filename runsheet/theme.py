"""Shared colors and fonts, matching the design mockup's palette."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

BG_APP = "#f4f5f7"
BG_PANEL = "#ffffff"
BG_HEADER = "#f6f7f8"
BORDER = "#e1e3e7"
BORDER_STRONG = "#c9cdd3"

TEXT_PRIMARY = "#202225"
TEXT_SECONDARY = "#5b6470"
TEXT_MUTED = "#8a929c"

WHITE = "#ffffff"

GREEN = "#1a9850"
GREEN_TINT = "#e7f6ec"

BLUE = "#2563c9"
BLUE_TINT = "#e8f0fd"

AMBER = "#b45309"
AMBER_TINT = "#fdf1d8"
AMBER_PILL_BG = "#eab308"
AMBER_PILL_TEXT = "#3f2d00"

BLACK = "#16181c"
BLACK_TINT = "#eef0f2"

GRAY = "#8a929c"
GRAY_TINT = "#ffffff"

RED = "#dc2626"
RED_TINT = "#fdecec"

TRACK = "#e4e6e9"  # background ring for the circular time-budget indicator

_MONO_CANDIDATES = ("SF Mono", "Menlo", "Consolas", "DejaVu Sans Mono", "Courier New")
_mono_family_cache: str | None = None


def mono_font(widget: tk.Misc, size: int = 9, weight: str = "normal") -> tuple[str, int, str]:
    """Resolve the best available monospace family on this system, once."""
    global _mono_family_cache
    if _mono_family_cache is None:
        available = set(tkfont.families(widget))
        _mono_family_cache = next(
            (name for name in _MONO_CANDIDATES if name in available), "Courier"
        )
    return (_mono_family_cache, size, weight)


# The px/pt scaling factor Tk reports on this project's own development
# display (~96 dpi, "100%" OS scaling) — the baseline every literal pixel
# size in the UI (Canvas icon dimensions, the window's initial geometry)
# was chosen against. Tk already scales *point*-sized fonts correctly for
# whatever display it's actually running on; pixel-literal Canvas geometry
# doesn't participate in that at all. scaled() closes that gap: convert a
# design-time pixel value to the equivalent size on the current display by
# the ratio of its scaling factor to this one, so icons stay proportional
# to the text around them regardless of the display's real DPI.
_DESIGN_SCALING = 1.3331191088260494
_ui_scale_cache: float | None = None


def scaled(widget: tk.Misc, pixels: int) -> int:
    """Convert a design-time pixel value to the current display's scale."""
    global _ui_scale_cache
    if _ui_scale_cache is None:
        _ui_scale_cache = float(widget.tk.call("tk", "scaling")) / _DESIGN_SCALING
    return round(pixels * _ui_scale_cache)
