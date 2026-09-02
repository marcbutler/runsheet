"""Announcement UI: short status text meant to be copied elsewhere.

- AnnouncementsBox: a bordered 'ANNOUNCEMENTS' panel with STARTED/FINISHED
  rows, used inside a step panel for its per-step announcements.
- NoteStep: a minimal single-message 'pseudo step' panel for a kind="note"
  [[Step]] entry (model.Note) — no summary, state, or commands, just the
  text and a Copy chip, interspersed among the real steps or bookending
  the list. Styled distinctly from a real StepPanel (tinted background +
  a left accent stripe) so it doesn't read as just another step.
"""

from __future__ import annotations

import tkinter as tk

from . import theme


def make_copy_chip(master: tk.Misc, value: str) -> tk.Label:
    """A small 'Copy' pill that copies `value` to the clipboard when
    clicked, flashing to confirm."""
    chip = tk.Label(
        master, text="Copy", bg=theme.BG_HEADER, fg=theme.TEXT_SECONDARY,
        font=("TkDefaultFont", 8, "bold"), padx=8, pady=3, cursor="hand2",
        highlightthickness=1, highlightbackground=theme.BORDER,
    )

    def copy(_event: tk.Event | None = None) -> None:
        chip.clipboard_clear()
        chip.clipboard_append(value)
        chip.configure(text="Copied", bg=theme.GREEN_TINT, fg=theme.GREEN)
        chip.after(
            900, lambda: chip.configure(text="Copy", bg=theme.BG_HEADER, fg=theme.TEXT_SECONDARY)
        )

    chip.bind("<Button-1>", copy)
    return chip


class AnnouncementsBox(tk.Frame):
    def __init__(self, master: tk.Misc, started: str, finished: str, wraplength: int = 680):
        super().__init__(
            master, bg=theme.BG_PANEL, highlightthickness=1, highlightbackground=theme.BORDER,
        )
        head = tk.Frame(self, bg=theme.BG_HEADER)
        head.pack(fill="x")
        tk.Label(
            head, text="ANNOUNCEMENTS", bg=theme.BG_HEADER, fg=theme.TEXT_MUTED,
            font=("TkDefaultFont", 8, "bold"),
        ).pack(side="left", padx=10, pady=4)

        self._add_row("STARTED", started, wraplength)
        self._add_row("FINISHED", finished, wraplength)

    def _add_row(self, label: str, text: str, wraplength: int) -> None:
        row = tk.Frame(self, bg=theme.BG_PANEL)
        row.pack(fill="x", padx=10, pady=6)
        tk.Label(
            row, text=label, bg=theme.BG_PANEL, fg=theme.TEXT_MUTED,
            font=("TkDefaultFont", 8, "bold"), width=8, anchor="nw",
        ).pack(side="left", anchor="n")
        tk.Label(
            row, text=text, bg=theme.BG_PANEL, fg=theme.TEXT_PRIMARY,
            font=("TkDefaultFont", 9), justify="left", anchor="w", wraplength=wraplength,
        ).pack(side="left", fill="x", expand=True, padx=(4, 8))
        make_copy_chip(row, text).pack(side="right", anchor="n")


class NoteStep(tk.Frame):
    """A pseudo step panel for a single note: no summary, state, or
    commands, just the text and a Copy chip. The outer frame's own
    background shows through as a left accent stripe (via the inner
    content frame's asymmetric padding) and the content frame itself uses
    a distinct tint — both deliberately different from a StepPanel's
    plain white — so a note reads as a different kind of card, not just
    another (oddly shaped) step, while scrolling past it."""

    def __init__(self, master: tk.Misc, text: str):
        super().__init__(
            master, bg=theme.GRAY, highlightthickness=1, highlightbackground=theme.BORDER,
        )
        content = tk.Frame(self, bg=theme.NOTE_TINT)
        content.pack(fill="both", expand=True, padx=(4, 0))

        tk.Label(
            content, text="NOTE", bg=theme.NOTE_TINT, fg=theme.GRAY,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w", padx=14, pady=(10, 4))

        row = tk.Frame(content, bg=theme.NOTE_TINT)
        row.pack(fill="x", padx=14, pady=(0, 10))
        tk.Label(
            row, text=text, bg=theme.NOTE_TINT, fg=theme.TEXT_PRIMARY,
            font=("TkDefaultFont", 9), justify="left", anchor="w", wraplength=900,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))
        make_copy_chip(row, text).pack(side="right")
