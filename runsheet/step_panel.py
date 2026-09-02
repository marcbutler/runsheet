"""The panel widget for a single step in the runsheet view."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from . import theme
from .announcements import AnnouncementsBox
from .model import Step, StepState

# Time-budget indicator: a small pie-wedge "clock" that sweeps clockwise
# from 12 o'clock as the budget is used up. Tkinter angles start at 3
# o'clock and increase counter-clockwise, so 12 o'clock is start=90, and a
# negative extent sweeps clockwise from there. Design-time pixel sizes
# (before theme.scaled() adjusts them per-instance for the real display —
# see StepPanel.__init__) — 22px icon, 2px padding.
_CLOCK_SIZE_PX = 22
_CLOCK_PAD_PX = 2

# Step badge: a small square "box" to the left of the title. For
# PENDING/ACTIVE it draws a right-pointing play-style triangle (unfilled
# when available to run, filled once running); other states keep a
# centered text glyph (see STATE_GLYPH). Design-time pixel sizes — 26px
# icon, 6px padding to the triangle's points.
_BADGE_SIZE_PX = 26
_BADGE_TRIANGLE_PAD_PX = 6

# (accent color, tint background) per state, used for the badge circle and pill.
STATE_COLORS: dict[StepState, tuple[str, str]] = {
    StepState.PENDING: (theme.GRAY, theme.BG_PANEL),
    StepState.ACTIVE: (theme.GREEN, theme.GREEN_TINT),
    StepState.FINISHED: (theme.BLUE, theme.BLUE_TINT),
    StepState.SKIPPED: (theme.BLACK, theme.BLACK_TINT),
    StepState.RESTARTED: (theme.AMBER, theme.AMBER_TINT),
}

STATE_LABEL: dict[StepState, str] = {
    StepState.PENDING: "PENDING",
    StepState.ACTIVE: "ACTIVE",
    StepState.FINISHED: "FINISHED",
    StepState.SKIPPED: "SKIPPED",
    StepState.RESTARTED: "RESTARTED",
}

STATE_GLYPH: dict[StepState, str] = {
    # ACTIVE and PENDING are drawn as triangles instead (see _draw_badge).
    StepState.FINISHED: "✓",  # check mark
    StepState.SKIPPED: "–",  # en dash
    StepState.RESTARTED: "↻",  # clockwise open circle arrow
}


def format_hms(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_hms_fixed(seconds: float) -> str:
    """Zero-padded HH:MM:SS, always all three segments — for fixed-width
    digital-clock displays where the string length must never jitter."""
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class StepPanel(tk.Frame):
    """One collapsible panel: header (badge, title, timer, state pill) + body
    (description, time budget bar, read-only commands box)."""

    def __init__(self, master: tk.Misc, step: Step, on_select: Callable[[int], None]):
        super().__init__(
            master, bg=theme.BG_PANEL, highlightthickness=1, highlightbackground=theme.BORDER
        )
        self.step = step
        self.on_select = on_select
        self.expanded = step.state is StepState.ACTIVE

        # Scaled once per panel (cheap — theme.scaled() caches the actual
        # display-scaling lookup globally after its first call) so the
        # badge/clock icons stay proportional to text on any display.
        self._badge_size = theme.scaled(self, _BADGE_SIZE_PX)
        badge_pad = theme.scaled(self, _BADGE_TRIANGLE_PAD_PX)
        self._badge_triangle_points = (
            badge_pad, badge_pad,
            badge_pad, self._badge_size - badge_pad,
            self._badge_size - badge_pad, self._badge_size / 2,
        )
        self._clock_size = theme.scaled(self, _CLOCK_SIZE_PX)
        clock_pad = theme.scaled(self, _CLOCK_PAD_PX)
        self._clock_bbox = (clock_pad, clock_pad, self._clock_size - clock_pad, self._clock_size - clock_pad)

        self._build_header()
        self._build_body()
        self.refresh()

    # -- construction ------------------------------------------------------

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=theme.BG_PANEL, cursor="hand2")
        header.pack(fill="x", padx=14, pady=10)
        header.bind("<Button-1>", self._select)
        self.header = header

        self.badge = tk.Canvas(
            header, width=self._badge_size, height=self._badge_size, bg=theme.BG_PANEL,
            highlightthickness=0,
        )
        self.badge.pack(side="left", padx=(0, 10))
        self.badge.bind("<Button-1>", self._select)

        self.title_label = tk.Label(
            header, text=self.step.title, bg=theme.BG_PANEL, fg=theme.TEXT_PRIMARY,
            font=("TkDefaultFont", 11, "bold"), anchor="w",
        )
        self.title_label.pack(side="left", fill="x", expand=True)
        self.title_label.bind("<Button-1>", self._select)

        self.chevron = tk.Label(
            header, text="▾", bg=theme.BG_PANEL, fg=theme.TEXT_MUTED,
            font=("TkDefaultFont", 9), cursor="hand2",
        )
        self.chevron.pack(side="right", padx=(8, 0))
        self.chevron.bind("<Button-1>", self._toggle_expand)

        self.state_pill = tk.Label(
            header, font=("TkDefaultFont", 8, "bold"), padx=8, pady=2,
        )
        self.state_pill.pack(side="right", padx=(8, 0))

        self.time_label = tk.Label(
            header, bg=theme.BG_PANEL, fg=theme.TEXT_MUTED, font=theme.mono_font(self, 9),
        )
        self.time_label.pack(side="right", padx=(8, 0))

    def _build_body(self) -> None:
        self.body = tk.Frame(self, bg=theme.BG_PANEL)
        step = self.step

        if step.description:
            tk.Label(
                self.body, text=step.description, bg=theme.BG_PANEL, fg=theme.TEXT_SECONDARY,
                font=("TkDefaultFont", 9), justify="left", anchor="w", wraplength=920,
            ).pack(fill="x", padx=14, pady=(0, 8))

        self.budget_clock: tk.Canvas | None = None
        self._clock_arc_id: int | None = None
        self.budget_label: tk.Label | None = None
        if step.budget_seconds:
            row = tk.Frame(self.body, bg=theme.BG_PANEL)
            row.pack(fill="x", padx=14, pady=(0, 8))

            clock = tk.Canvas(
                row, width=self._clock_size, height=self._clock_size, bg=theme.BG_PANEL,
                highlightthickness=0,
            )
            clock.pack(side="left")
            clock.create_oval(*self._clock_bbox, fill=theme.TRACK, outline=theme.BORDER)
            self._clock_arc_id = clock.create_arc(
                *self._clock_bbox, start=90, extent=0, fill=theme.GREEN, outline="",
                style=tk.PIESLICE,
            )
            self.budget_clock = clock

            self.budget_label = tk.Label(
                row, bg=theme.BG_PANEL, fg=theme.TEXT_MUTED, font=theme.mono_font(self, 8),
            )
            self.budget_label.pack(side="left", padx=(8, 0))

        self.commands_text: tk.Text | None = None
        if step.commands.strip():
            box = tk.Frame(
                self.body, bg=theme.BG_PANEL, highlightthickness=1, highlightbackground=theme.BORDER,
            )
            box.pack(fill="x", padx=14, pady=(0, 8))
            head = tk.Frame(box, bg=theme.BG_HEADER)
            head.pack(fill="x")
            tk.Label(
                head, text="COMMANDS", bg=theme.BG_HEADER, fg=theme.TEXT_MUTED,
                font=("TkDefaultFont", 8, "bold"),
            ).pack(side="left", padx=10, pady=4)

            body_text = step.commands.strip("\n")
            height = min(12, body_text.count("\n") + 1)
            text = tk.Text(
                box, height=height, wrap="none", bg="#fbfbfc", fg=theme.TEXT_PRIMARY,
                font=theme.mono_font(self, 9), relief="flat", padx=10, pady=8, borderwidth=0,
            )
            text.insert("1.0", body_text)
            text.configure(state="disabled")
            text.pack(fill="x")
            self.commands_text = text

        if step.has_announcements:
            AnnouncementsBox(
                self.body, step.announcement_started, step.announcement_finished
            ).pack(fill="x", padx=14, pady=(0, 12))

    # -- selection / expansion ----------------------------------------------

    def _select(self, _event: tk.Event | None = None) -> None:
        self.on_select(self.step.index - 1)

    def _toggle_expand(self, _event: tk.Event | None = None) -> None:
        self.set_expanded(not self.expanded)

    def set_expanded(self, expanded: bool) -> None:
        self.expanded = expanded
        is_packed = bool(self.body.winfo_manager())
        if expanded and not is_packed:
            self.body.pack(fill="x")
            self.chevron.configure(text="▾")
        elif not expanded and is_packed:
            self.body.pack_forget()
            self.chevron.configure(text="▸")

    def set_selected(self, selected: bool) -> None:
        self.configure(
            highlightbackground=theme.TEXT_PRIMARY if selected else theme.BORDER,
            highlightthickness=2 if selected else 1,
        )

    # -- rendering ------------------------------------------------------

    def _draw_badge(self, state: StepState, accent: str, tint: str) -> None:
        """Redraw the badge box: a right-pointing triangle for PENDING
        (outline only) / ACTIVE (filled), always black regardless of the
        state's accent color; everything else keeps its existing tinted
        box with a centered text glyph."""
        self.badge.delete("all")
        pad = 1
        self.badge.create_rectangle(
            pad, pad, self._badge_size - pad, self._badge_size - pad,
            fill=tint, outline=accent, width=1,
        )
        if state in (StepState.PENDING, StepState.ACTIVE):
            filled = state is StepState.ACTIVE
            self.badge.create_polygon(
                *self._badge_triangle_points, outline=theme.BLACK,
                fill=theme.BLACK if filled else "", width=1.5, joinstyle="round",
            )
        else:
            self.badge.create_text(
                self._badge_size / 2, self._badge_size / 2, text=STATE_GLYPH[state],
                fill=accent, font=("TkDefaultFont", 10, "bold"),
            )

    def refresh(self) -> None:
        step = self.step
        accent, tint = STATE_COLORS[step.state]

        self._draw_badge(step.state, accent, tint)

        self.state_pill.configure(text=STATE_LABEL[step.state], fg=accent, bg=tint)
        self.title_label.configure(
            fg=theme.TEXT_MUTED if step.state is StepState.SKIPPED else theme.TEXT_PRIMARY
        )

        # steps that have never run collapse by default; everything else can
        # be expanded/collapsed freely once it has state worth showing.
        if step.state is StepState.ACTIVE and not self.expanded:
            self.set_expanded(True)

        self.refresh_timer()

    def refresh_timer(self) -> None:
        step = self.step
        if step.state in (StepState.ACTIVE, StepState.FINISHED, StepState.RESTARTED):
            self.time_label.configure(text=format_hms(step.elapsed_seconds))
        else:
            self.time_label.configure(text="")

        if self.budget_clock is not None and step.budget_seconds:
            frac = step.elapsed_seconds / step.budget_seconds

            # Two laps, both sweeping clockwise: green drains from a full
            # circle down to empty over the budget (0x-1x, trailing edge
            # anchored at 12, leading/boundary edge sweeps clockwise as it
            # empties); amber then fills the inverse way, from empty up to
            # a full circle, over a grace period (1x-2x, leading edge
            # anchored at 12 instead, trailing edge sweeps clockwise as it
            # fills); past double the budget it just sits solid red.
            if frac <= 1.0:
                color = theme.GREEN
                filled = min(0.9999, max(0.0, 1.0 - frac))
                start = 90 - (1 - filled) * 360
            elif frac <= 2.0:
                color = theme.AMBER_PILL_BG
                filled = min(0.9999, max(0.0, frac - 1.0))
                start = 90
            else:
                color = theme.RED
                # Tk's canvas arc wraps an extent of exactly +/-360 back to
                # 0 (a full sweep is indistinguishable from no sweep), so
                # cap just under a full turn — visually a complete circle.
                filled = 0.9999
                start = 90

            extent = -360 * filled
            self.budget_clock.itemconfigure(
                self._clock_arc_id, start=start, extent=extent, fill=color
            )

            remaining = step.budget_seconds - step.elapsed_seconds
            suffix = f"≈ {format_hms(remaining)} left" if remaining > 0 else "over budget"
            self.budget_label.configure(
                text=f"{format_hms(step.elapsed_seconds)} / {format_hms(step.budget_seconds)}  {suffix}"
            )
