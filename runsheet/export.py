"""Plain-text export: render a fully-loaded (variable-substituted) Runsheet
as sparse, readable UTF-8 text — see README's "Exporting to plain text"
section for the format itself. Kept separate from model.py since this is
purely a rendering concern, not part of loading/validating the runsheet."""

from __future__ import annotations

import textwrap

from .model import Note, Runsheet, Step, format_seconds

# Free-text (descriptions, announcements) wraps at 100 columns for a
# readable, print-friendly width. Headings, rules, and commands are never
# wrapped — see _step_text/_indent_commands.
_WRAP_WIDTH = 100


def _wrap(text: str, indent: str = "") -> list[str]:
    """Reflow `text` to _WRAP_WIDTH, with `indent` as both the first-line
    prefix (e.g. a label) and the hanging indent for any continuation
    lines, so wrapped lines stay aligned under the first line's text."""
    return textwrap.wrap(
        text, width=_WRAP_WIDTH, initial_indent=indent, subsequent_indent=" " * len(indent),
        break_long_words=False, break_on_hyphens=False,
    ) or [indent.rstrip()]


def _rule(heading: str, char: str) -> str:
    return char * len(heading)


def _paired_lines(started_label: str, finished_label: str, started: str, finished: str) -> list[str]:
    """Two label/value blocks, the shorter label padded so both values
    start in the same column, each independently wrapped with its
    continuation lines hanging under that column — used for both the
    runsheet- and step-level started/finished announcement pairs."""
    width = max(len(started_label), len(finished_label)) + 1
    return [
        *_wrap(started, f"{started_label:<{width}}"),
        *_wrap(finished, f"{finished_label:<{width}}"),
    ]


def _indent_commands(commands: str) -> str:
    lines = commands.strip("\n").split("\n")
    return "\n".join(f"    {line}" if line.strip() else "" for line in lines)


def _note_text(note: Note) -> str:
    return "\n".join(_wrap(note.text, "Note: "))


def _step_text(step: Step) -> str:
    heading = f"Step {step.index}: {step.summary}"
    sections: list[str] = []
    if step.budget_seconds is not None:
        sections.append(f"Time budget: {format_seconds(step.budget_seconds)}")
    if step.description.strip():
        sections.append("\n".join(_wrap(step.description.strip())))
    if step.commands.strip():
        sections.append(f"Commands:\n{_indent_commands(step.commands)}")
    if step.has_announcements:
        sections.append(
            "\n".join(_paired_lines(
                "Announcement (started):", "Announcement (finished):",
                step.announcement_started, step.announcement_finished,
            ))
        )

    block = [heading, _rule(heading, "-")]
    if sections:
        block.append("\n\n".join(sections))
    return "\n".join(block)


def export_text(runsheet: Runsheet) -> str:
    """Render `runsheet` as sparse plain text: a compact metadata header
    (name, time guidance — whichever are set), then each step as its own
    rule-delimited section listing only the fields it actually sets, in a
    fixed order (time budget, description, commands, announcements).
    Notes (kind = "note" [[Step]] entries) are interspersed among the
    steps by their after_step anchor, matching the UI's ordering."""
    notes_by_anchor: dict[int, list[Note]] = {}
    for note in runsheet.notes:
        notes_by_anchor.setdefault(note.after_step, []).append(note)

    header = [runsheet.name, _rule(runsheet.name, "=")]
    if runsheet.time_guidance_seconds is not None:
        header.append(f"Time guidance: {format_seconds(runsheet.time_guidance_seconds)}")

    parts = ["\n".join(header)]
    parts.extend(_note_text(note) for note in notes_by_anchor.get(0, []))
    for step in runsheet.steps:
        parts.append(_step_text(step))
        parts.extend(_note_text(note) for note in notes_by_anchor.get(step.index, []))
    return "\n\n".join(parts) + "\n"
