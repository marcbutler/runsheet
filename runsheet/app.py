"""The main Tkinter application: toolbar, scrollable runsheet view, footer."""

from __future__ import annotations

import sys
import time
import tkinter as tk
import tkinter.messagebox as messagebox
import tkinter.ttk as ttk

from . import theme
from .announcements import AnnouncementStep
from .logbook import Logbook
from .model import Runsheet, Step, StepState
from .step_panel import StepPanel, format_hms_fixed

# Which prior states each toolbar action is allowed to act on. Restart
# resets a step back to PENDING (see _apply_action), so StepState.RESTARTED
# is never a resting step.state and doesn't appear as a value here.
_ALLOWED_FROM: dict[StepState, tuple[StepState, ...]] = {
    StepState.ACTIVE: (StepState.PENDING,),
    StepState.FINISHED: (StepState.ACTIVE,),
    StepState.RESTARTED: (StepState.ACTIVE, StepState.FINISHED, StepState.SKIPPED),
    StepState.SKIPPED: (StepState.PENDING, StepState.ACTIVE),
}

_ACTIONS: tuple[tuple[StepState, str, str, str], ...] = (
    # (target state, label text, background color, foreground color)
    (StepState.ACTIVE, "START", theme.GREEN, theme.WHITE),
    (StepState.FINISHED, "FINISH", theme.BLUE, theme.WHITE),
    (StepState.RESTARTED, "RESET", theme.AMBER_PILL_BG, theme.AMBER_PILL_TEXT),
    (StepState.SKIPPED, "SKIP", theme.BLACK, theme.WHITE),
)


class RunsheetApp(tk.Tk):
    def __init__(self, runsheet: Runsheet, logbook: Logbook):
        super().__init__()
        self.runsheet = runsheet
        self.logbook = logbook
        self.selected_index = 0
        self.run_started_at: float | None = None  # time.monotonic() at the first Start of the session

        self.title(f"Runsheet — {runsheet.path.name}")
        # Design-time pixel sizes, scaled to the current display so the
        # window itself isn't cramped or oversized relative to its
        # proportionally-scaled contents (see theme.scaled()).
        self.geometry(f"{theme.scaled(self, 1180)}x{theme.scaled(self, 800)}")
        self.minsize(theme.scaled(self, 760), theme.scaled(self, 480))
        self.configure(bg=theme.BG_APP)

        self._init_ttk_styles()

        self.action_labels: dict[StepState, tk.Label] = {}
        self.action_colors: dict[StepState, tuple[str, str]] = {}
        self.panels: list[StepPanel] = []

        self._build_toolbar()
        self._build_runsheet_view()
        self._build_footer()

        self._refresh_run_clock()
        self._select(0)
        self.logbook.write("session_start", runsheet=str(runsheet.path), sha1=runsheet.sha1)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._tick()

    # -- one-time setup -------------------------------------------------

    def _init_ttk_styles(self) -> None:
        style = ttk.Style(self)
        # 'clam' is the only built-in theme that reliably honors custom
        # Scrollbar colors across platforms.
        style.theme_use("clam")
        style.configure("Runsheet.Vertical.TScrollbar", background=theme.BORDER_STRONG)

    # -- construction -----------------------------------------------------

    def _build_toolbar(self) -> None:
        bar = tk.Frame(self, bg=theme.WHITE, highlightthickness=1, highlightbackground=theme.BORDER)
        bar.pack(side="top", fill="x")

        left = tk.Frame(bar, bg=theme.WHITE)
        left.pack(side="left", padx=16, pady=10)

        title_row = tk.Frame(left, bg=theme.WHITE)
        title_row.pack(anchor="w")
        tk.Label(
            title_row, text="RUNSHEET", bg=theme.WHITE, fg=theme.TEXT_PRIMARY,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="left")
        if self.runsheet.name:
            tk.Label(
                title_row, text=self.runsheet.name, bg=theme.WHITE, fg=theme.TEXT_SECONDARY,
                font=("TkDefaultFont", 10),
            ).pack(side="left", padx=(8, 0))

        self.progress_label = tk.Label(
            left, text="", bg=theme.WHITE, fg=theme.TEXT_MUTED, font=("TkDefaultFont", 9),
        )
        self.progress_label.pack(anchor="w")

        right = tk.Frame(bar, bg=theme.WHITE)
        right.pack(side="right", padx=16, pady=10)

        # Packed in reverse (side="right" places each new child to the left
        # of the previous one) so the visual left-to-right order reads the
        # Runsheet/Abort group, then a divider, then Step actions at the
        # far right edge, closest to the runsheet view they act on.
        step_group, pills_row = self._toolbar_group(right, "STEP")
        step_group.pack(side="right")
        for state, text, bg, fg in _ACTIONS:
            lbl = self._make_pill(
                pills_row, text, bg, fg, command=lambda s=state: self._apply_action(s)
            )
            self.action_labels[state] = lbl
            self.action_colors[state] = (bg, fg)

        tk.Frame(right, bg=theme.BORDER, width=1).pack(side="right", fill="y", padx=16)

        runsheet_group, runsheet_row = self._toolbar_group(right, "RUNSHEET")
        runsheet_group.pack(side="right")

        # Width 9 fits the widest form ("+HH:MM:SS"); the plain countdown
        # form ("HH:MM:SS", one char shorter) just right-aligns within it,
        # so the field never changes width when it flips to counting up.
        self.run_clock_label: tk.Label | None = None
        if self.runsheet.time_guidance_seconds is not None:
            self.run_clock_label = tk.Label(
                runsheet_row, bg=theme.WHITE, fg=theme.TEXT_PRIMARY,
                font=theme.mono_font(self, 11), width=9, anchor="e",
            )
            self.run_clock_label.pack(side="left", padx=(0, 10))

        self.end_label = self._make_pill(
            runsheet_row, "END", theme.RED, theme.WHITE, command=self._on_end
        )

    @staticmethod
    def _toolbar_group(master: tk.Misc, caption: str) -> tuple[tk.Frame, tk.Frame]:
        """A labeled group: a small muted caption above a row for pills."""
        group = tk.Frame(master, bg=theme.WHITE)
        tk.Label(
            group, text=caption, bg=theme.WHITE, fg=theme.TEXT_MUTED,
            font=("TkDefaultFont", 8, "bold"),
        ).pack(anchor="w")
        row = tk.Frame(group, bg=theme.WHITE)
        row.pack(anchor="w")
        return group, row

    @staticmethod
    def _make_pill(master: tk.Misc, text: str, bg: str, fg: str, command) -> tk.Label:
        lbl = tk.Label(
            master, text=text, bg=bg, fg=fg, padx=14, pady=6,
            font=("TkDefaultFont", 9, "bold"), cursor="hand2",
        )
        lbl.pack(side="left", padx=4)
        lbl.bind("<Button-1>", lambda _e: command())
        return lbl

    def _build_runsheet_view(self) -> None:
        outer = tk.Frame(self, bg=theme.BG_APP)
        outer.pack(side="top", fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=theme.BG_APP, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            outer, orient="vertical", command=canvas.yview, style="Runsheet.Vertical.TScrollbar"
        )
        self.canvas = canvas
        self.list_frame = tk.Frame(canvas, bg=theme.BG_APP)

        self.list_frame.bind(
            "<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        window_id = canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_mousewheel(event: tk.Event) -> None:
            # macOS reports small per-notch deltas; Windows scales by 120.
            step = int(event.delta) if sys.platform == "darwin" else int(event.delta / 120)
            step = max(-3, min(3, step)) or (-1 if event.delta > 0 else 1)
            canvas.yview_scroll(-1 * step, "units")

        def on_scroll_up(_event: tk.Event) -> None:
            canvas.yview_scroll(-1, "units")

        def on_scroll_down(_event: tk.Event) -> None:
            canvas.yview_scroll(1, "units")

        # bind_all's "all" bindtag is checked last, after any widget- or
        # class-level binding — reliable in practice, but a step panel's own
        # widgets are bound directly too, so scrolling works no matter which
        # nested label/frame/text the cursor happens to be over.
        for sequence, handler in (
            ("<MouseWheel>", on_mousewheel),  # Windows / macOS
            ("<Button-4>", on_scroll_up),  # Linux, scroll up
            ("<Button-5>", on_scroll_down),  # Linux, scroll down
        ):
            canvas.bind_all(sequence, handler)
            self._bind_scroll_recursive(self.list_frame, sequence, handler)

        # The runsheet's overall start/finish announcements (if any) bookend
        # the list as pseudo steps — not real Step objects, so they never
        # touch self.panels / self.runsheet.steps and stay outside the
        # state machine, selection, and progress count entirely.
        pseudo_steps: list[tk.Frame] = []
        if self.runsheet.has_announcements:
            start_step = AnnouncementStep(
                self.list_frame, "RUNSHEET STARTED", self.runsheet.announcement_started,
                theme.GREEN,
            )
            start_step.pack(fill="x", padx=20, pady=6)
            pseudo_steps.append(start_step)

        for step in self.runsheet.steps:
            panel = StepPanel(self.list_frame, step, on_select=self._select)
            panel.pack(fill="x", padx=20, pady=6)
            self.panels.append(panel)
            self._bind_scroll_recursive(panel, "<MouseWheel>", on_mousewheel)
            self._bind_scroll_recursive(panel, "<Button-4>", on_scroll_up)
            self._bind_scroll_recursive(panel, "<Button-5>", on_scroll_down)

        if self.runsheet.has_announcements:
            finish_step = AnnouncementStep(
                self.list_frame, "RUNSHEET FINISHED", self.runsheet.announcement_finished,
                theme.BLUE,
            )
            finish_step.pack(fill="x", padx=20, pady=6)
            pseudo_steps.append(finish_step)

        for pseudo in pseudo_steps:
            self._bind_scroll_recursive(pseudo, "<MouseWheel>", on_mousewheel)
            self._bind_scroll_recursive(pseudo, "<Button-4>", on_scroll_up)
            self._bind_scroll_recursive(pseudo, "<Button-5>", on_scroll_down)

        # Keyboard fallback: some environments (notably remote-control /
        # screen-sharing sessions) don't forward wheel-scroll deltas
        # reliably to Tk, but keyboard events always come through. Bound on
        # the root window itself since the step panels' labels/frames don't
        # take keyboard focus, so the root remains the default target.
        self.bind("<Up>", lambda _e: canvas.yview_scroll(-1, "units"))
        self.bind("<Down>", lambda _e: canvas.yview_scroll(1, "units"))
        self.bind("<Prior>", lambda _e: canvas.yview_scroll(-1, "pages"))  # Page Up
        self.bind("<Next>", lambda _e: canvas.yview_scroll(1, "pages"))  # Page Down
        self.bind("<Home>", lambda _e: canvas.yview_moveto(0))
        self.bind("<End>", lambda _e: canvas.yview_moveto(1))
        self.focus_set()

    @staticmethod
    def _bind_scroll_recursive(widget: tk.Misc, sequence: str, handler) -> None:
        """Bind a scroll handler directly on `widget` and every descendant,
        so scrolling works over any nested panel content, not just the
        canvas background."""
        widget.bind(sequence, handler)
        for child in widget.winfo_children():
            RunsheetApp._bind_scroll_recursive(child, sequence, handler)

    def _build_footer(self) -> None:
        bar = tk.Frame(self, bg=theme.BG_HEADER, highlightthickness=1, highlightbackground=theme.BORDER)
        bar.pack(side="bottom", fill="x")
        mono = theme.mono_font(self, 9)

        left = tk.Frame(bar, bg=theme.BG_HEADER)
        left.pack(side="left", padx=16, pady=6)

        self._copyable_label(
            left, text=self.runsheet.path.name, value=str(self.runsheet.path), font=mono
        ).pack(side="left")
        tk.Label(
            left, text="  ·  sha1 ", bg=theme.BG_HEADER, fg=theme.TEXT_SECONDARY, font=mono
        ).pack(side="left")
        self._copyable_label(
            left, text=self.runsheet.short_sha1, value=self.runsheet.sha1, font=mono
        ).pack(side="left")

        right = tk.Frame(bar, bg=theme.BG_HEADER)
        right.pack(side="right", padx=16, pady=6)

        tk.Label(
            right, text="log: ", bg=theme.BG_HEADER, fg=theme.TEXT_SECONDARY, font=mono
        ).pack(side="left")
        self._copyable_label(
            right, text=self.logbook.path.name, value=str(self.logbook.path), font=mono
        ).pack(side="left")

    def _copyable_label(
        self, master: tk.Misc, text: str, value: str, font: tuple[str, int, str]
    ) -> tk.Label:
        """A footer label that copies `value` to the clipboard when clicked,
        flashing to confirm the copy."""
        lbl = tk.Label(master, text=text, bg=theme.BG_HEADER, fg=theme.TEXT_SECONDARY, font=font, cursor="hand2")
        lbl.bind("<Button-1>", lambda _e: self._copy_to_clipboard(value, lbl, text))
        return lbl

    def _copy_to_clipboard(self, value: str, label: tk.Label, original_text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(value)
        label.configure(text="copied", fg=theme.GREEN)
        self.after(900, lambda: label.configure(text=original_text, fg=theme.TEXT_SECONDARY))

    # -- selection --------------------------------------------------------

    def _select(self, index: int) -> None:
        self.selected_index = index
        for i, panel in enumerate(self.panels):
            panel.set_selected(i == index)
        # The step you land on is the one eligible to run next (Start acts
        # on whichever step is selected) — expand it so its description and
        # commands are visible without an extra click.
        if self.runsheet.steps[index].state is StepState.PENDING:
            self.panels[index].set_expanded(True)
        self._refresh_toolbar()
        self._refresh_progress()

    def _refresh_progress(self) -> None:
        finished = sum(1 for s in self.runsheet.steps if s.state is StepState.FINISHED)
        skipped = sum(1 for s in self.runsheet.steps if s.state is StepState.SKIPPED)
        self.progress_label.configure(
            text=f"Step {self.selected_index + 1} of {len(self.runsheet.steps)}  ·  "
            f"{finished} complete  ·  {skipped} skipped"
        )

    def _refresh_toolbar(self) -> None:
        current = self.runsheet.steps[self.selected_index].state
        for target_state, lbl in self.action_labels.items():
            enabled = current in _ALLOWED_FROM[target_state]
            if enabled:
                bg, fg = self.action_colors[target_state]
            else:
                # tk has no real opacity; approximate "disabled" by
                # desaturating toward the toolbar background rather than
                # hiding the action, so the toolbar's four colors stay put.
                bg, fg = theme.BG_HEADER, theme.TEXT_MUTED
            lbl.configure(bg=bg, fg=fg, cursor="hand2" if enabled else "arrow")

    # -- actions ------------------------------------------------------------

    def _on_end(self) -> None:
        """END always exits the app (unlike the old lock-but-stay-open
        Abort) — a small modal offers Cancel, or exiting with the session
        log kept or deleted."""
        choice = self._ask_end_choice()
        if choice is None:
            return  # cancelled — back to the UI, nothing changed

        if choice == "keep":
            step = self.runsheet.steps[self.selected_index]
            self.logbook.write("session_end", step=step.index, summary=step.summary, reason="end")

        log_path = self.logbook.path
        self.logbook.close()
        if choice == "delete":
            log_path.unlink(missing_ok=True)
        self.destroy()

    def _ask_end_choice(self) -> str | None:
        """A modal Cancel / Exit-keep-log / Exit-delete-log dialog.
        tkinter.messagebox has no built-in 3-custom-button dialog, so this
        is a small hand-built Toplevel. Returns "keep", "delete", or None
        for cancel (including closing the dialog itself)."""
        result: list[str | None] = [None]
        dialog = tk.Toplevel(self)
        dialog.title("End runsheet")
        dialog.configure(bg=theme.BG_PANEL)
        dialog.transient(self)
        dialog.resizable(False, False)

        def finish(choice: str | None) -> None:
            result[0] = choice
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", lambda: finish(None))

        tk.Label(
            dialog, text="End this runsheet and exit?", bg=theme.BG_PANEL, fg=theme.TEXT_PRIMARY,
            font=("TkDefaultFont", 11, "bold"), justify="left", anchor="w",
        ).pack(fill="x", padx=20, pady=(20, 6))
        tk.Label(
            dialog, text=f"Session log:\n{self.logbook.path}", bg=theme.BG_PANEL,
            fg=theme.TEXT_SECONDARY, font=("TkDefaultFont", 9), justify="left", anchor="w",
            wraplength=380,
        ).pack(fill="x", padx=20, pady=(0, 16))

        button_row = tk.Frame(dialog, bg=theme.BG_PANEL)
        button_row.pack(fill="x", padx=20, pady=(0, 20))

        # Packed in reverse (side="right" places each new child to the
        # left of the previous one), so left-to-right this reads: Exit,
        # Delete Log / Exit, Keep Log / Cancel — the safe default rightmost.
        cancel_btn = tk.Button(button_row, text="Cancel", command=lambda: finish(None))
        cancel_btn.pack(side="right")
        tk.Button(
            button_row, text="Exit, Keep Log", command=lambda: finish("keep"),
        ).pack(side="right", padx=8)
        tk.Button(
            button_row, text="Exit, Delete Log", fg=theme.RED, command=lambda: finish("delete"),
        ).pack(side="right")

        dialog.bind("<Return>", lambda _e: finish(None))
        dialog.bind("<Escape>", lambda _e: finish(None))

        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        cancel_btn.focus_set()
        dialog.grab_set()
        dialog.wait_window()
        return result[0]

    def _apply_action(self, target_state: StepState) -> None:
        step = self.runsheet.steps[self.selected_index]
        panel = self.panels[self.selected_index]

        if step.state not in _ALLOWED_FROM[target_state]:
            return  # toolbar is disabled for this transition; ignore stray clicks

        if target_state is StepState.RESTARTED and step.state is StepState.FINISHED:
            if not messagebox.askyesno(
                "Reset finished step",
                f"Reset step {step.index} back to pending? It's already marked "
                f"finished — this clears that and its elapsed time.",
                icon="warning",
            ):
                return

        now = time.monotonic()

        if target_state is StepState.ACTIVE:
            step.started_at = now
            step.elapsed_seconds = 0.0
            step.state = StepState.ACTIVE
            panel.set_expanded(True)
            if self.run_started_at is None:
                self.run_started_at = now
        elif target_state is StepState.FINISHED:
            if step.started_at is not None:
                step.elapsed_seconds = now - step.started_at
            step.started_at = None
            step.state = StepState.FINISHED
            panel.set_expanded(False)
            self._advance_selection()
        elif target_state is StepState.RESTARTED:
            # Restart clears the step's progress entirely, back to its
            # untouched pending state — timer zeroed, no longer active or
            # finished. The operator presses Start again to re-run it.
            step.restart_count += 1
            step.started_at = None
            step.elapsed_seconds = 0.0
            step.state = StepState.PENDING
            # Stays selected (no _select() call), so _select()'s expand-on-
            # pending rule won't fire again — expand it explicitly here.
            panel.set_expanded(True)
        elif target_state is StepState.SKIPPED:
            step.started_at = None
            step.state = StepState.SKIPPED
            panel.set_expanded(False)
            self._advance_selection()

        self.logbook.write(
            target_state.value,
            step=step.index,
            summary=step.summary,
            elapsed_seconds=round(step.elapsed_seconds, 1),
            restart_count=step.restart_count,
        )
        panel.refresh()
        self._refresh_toolbar()
        self._refresh_progress()
        self._refresh_run_clock()
        if step.state is StepState.ACTIVE:
            self._scroll_into_view(self.selected_index)

    def _advance_selection(self) -> None:
        # More than one step can be active at once (started out of order),
        # so look across the WHOLE runsheet — not just forward from here —
        # for the earliest step that still needs attention (pending or
        # active); only FINISHED/SKIPPED get skipped over.
        for i, step in enumerate(self.runsheet.steps):
            if step.state not in (StepState.FINISHED, StepState.SKIPPED):
                self._select(i)
                self._scroll_into_view(i)  # keeps step i-1 in view above it, if possible
                return
        self._refresh_toolbar()

    def _scroll_into_view(self, index: int) -> None:
        """Scroll the runsheet view so the step at `index` lands as the
        second visible panel, leaving its predecessor visible above it for
        context. Scrolling to the predecessor's top edge is equivalent to
        (and simpler than) computing the target panel's own offset. Used
        both when a step becomes active and when Finish/Skip auto-advance
        focus to the next pending step."""
        self.update_idletasks()  # panel expansion above must be laid out first
        target_y = 0 if index == 0 else self.panels[index - 1].winfo_y()

        bbox = self.canvas.bbox("all")
        total_height = (bbox[3] - bbox[1]) if bbox else 0
        if total_height <= 0:
            return
        fraction = min(1.0, max(0.0, target_y / total_height))
        self.canvas.yview_moveto(fraction)

    # -- live timer ---------------------------------------------------------

    def _tick(self) -> None:
        now = time.monotonic()
        for step, panel in zip(self.runsheet.steps, self.panels):
            if step.state is StepState.ACTIVE and step.started_at is not None:
                step.elapsed_seconds = now - step.started_at
                panel.refresh_timer()
        self._refresh_run_clock()
        self.after(1000, self._tick)

    def _refresh_run_clock(self) -> None:
        """Update the RUNSHEET group's clock: counts down from
        time_guidance while time remains, then flips to counting up from
        zero — with a '+' prefix, in bold — once that guidance is used up."""
        if self.run_clock_label is None:
            return  # no time_guidance configured for this runsheet

        elapsed = (
            time.monotonic() - self.run_started_at if self.run_started_at is not None else 0.0
        )
        remaining = self.runsheet.time_guidance_seconds - elapsed
        over = remaining < 0

        if over:
            text = f"+{format_hms_fixed(-remaining)}"
        else:
            text = format_hms_fixed(remaining)
        self.run_clock_label.configure(
            text=text, font=theme.mono_font(self, 11, "bold" if over else "normal")
        )

    # -- shutdown -------------------------------------------------------

    def _on_close(self) -> None:
        self.logbook.write("session_end")
        self.logbook.close()
        self.destroy()
