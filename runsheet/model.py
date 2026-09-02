"""Runsheet data model: loading the TOML runbook and tracking step state."""

from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass, field
from datetime import time as dtime
from enum import Enum
from pathlib import Path


class StepState(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    FINISHED = "finished"
    SKIPPED = "skipped"
    RESTARTED = "restarted"
    ABORTED = "aborted"


def _parse_time_seconds(value: object, field_description: str) -> int:
    """Convert a TOML hh:mm:ss local-time value (e.g. time=00:10:00) to a
    whole number of seconds, used for both a step's 'time' budget and the
    runsheet's 'time_guidance'."""
    if not isinstance(value, dtime):
        raise ValueError(
            f"{field_description} must be an hh:mm:ss local time (e.g. 00:10:00), got {value!r}"
        )
    return value.hour * 3600 + value.minute * 60 + value.second


def format_seconds(seconds: int) -> str:
    """Plain H:MM:SS — not tied to the UI's own fixed-width clock
    formatter, just readable in a load-time error or a text export."""
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:d}:{minutes:02d}:{secs:02d}"


_VARIABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# A real placeholder is exactly two braces each side; four in a row is the
# escape for a literal two (mirrors Python str.format()'s "{{" -> "{"), so
# it's tried first — a genuine {{name}} placeholder never has a 3rd/4th
# brace immediately adjacent, so there's no ambiguity between the two.
_PLACEHOLDER_RE = re.compile(r"\{\{\{\{|\}\}\}\}|\{\{\s*(\w+)\s*\}\}")


def _parse_variables(metadata: dict, error_prefix: str) -> dict[str, str]:
    """Parse the optional [Runsheet.variables] table into a name->value
    dict, for substitution into every free-text field via {{name}}."""
    raw = metadata.get("variables", {})
    if not isinstance(raw, dict):
        raise ValueError(f"{error_prefix} field 'variables' must be a table")
    variables: dict[str, str] = {}
    for key, value in raw.items():
        if not _VARIABLE_NAME_RE.match(key):
            raise ValueError(
                f"{error_prefix} variable {key!r} is not a valid name — use letters, "
                f"digits, and underscores, not starting with a digit"
            )
        if not isinstance(value, str):
            raise ValueError(f"{error_prefix} variable '{key}' must be a string, got {value!r}")
        variables[key] = value
    return variables


def _substitute(text: str, variables: dict[str, str], context: str) -> str:
    """Replace every {{name}} in `text` with its value from `variables`.
    A variable's own value is used literally — never itself re-scanned for
    further {{...}} placeholders, so substitution is always a single pass.
    {{{{ and }}}} escape to a literal {{ and }} (see _PLACEHOLDER_RE), so
    e.g. "{{{{example}}}}" renders as the literal text "{{example}}"."""

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token == "{{{{":
            return "{{"
        if token == "}}}}":
            return "}}"
        name = match.group(1)
        if name not in variables:
            placeholder = "{{" + name + "}}"
            raise ValueError(
                f"{context}: undefined variable {placeholder!r} "
                f"(not defined in [Runsheet.variables])"
            )
        return variables[name]

    return _PLACEHOLDER_RE.sub(replace, text)


def _paired_announcements(entry: dict, error_prefix: str) -> tuple[str, str]:
    """Read announcement_started/announcement_finished from a TOML table,
    used for both a step and the runsheet itself: a table with either must
    have both."""
    started = entry.get("announcement_started", "")
    finished = entry.get("announcement_finished", "")
    if bool(started) != bool(finished):
        raise ValueError(
            f"{error_prefix} has only one of 'announcement_started' / "
            f"'announcement_finished' — a table with either must have both"
        )
    return started, finished


def read_variables(path: Path) -> dict[str, str]:
    """Parse just the [Runsheet.variables] table of a runsheet TOML file,
    without loading (and requiring successful substitution across) the
    whole thing — used to compare/merge variable dictionaries between
    copies of a runsheet (see retarget()). Raises ValueError, with path
    context, on invalid TOML or a malformed variables table — the same
    checks Runsheet.load applies to this table."""
    raw = path.read_bytes()
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{path}: invalid TOML: {exc}") from exc
    metadata = data.get("Runsheet", {})
    if not isinstance(metadata, dict):
        raise ValueError(f"{path}: [Runsheet] must be a table, not a list of tables")
    return _parse_variables(metadata, f"{path}: [Runsheet]")


def _toml_quote(value: str) -> str:
    """Format a string as a TOML basic string literal."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


# Matches the [Runsheet.variables] table header through to its whole body —
# up to (not including) the next table header or end of file — so the body
# can be swapped out wholesale while leaving everything else in the source
# text untouched (comments, formatting, steps, all of it). The trailing
# blank-line run is split into its own group purely so it can be preserved
# verbatim in the replacement, keeping the usual blank-line-before-next-
# table spacing intact rather than collapsing it away.
_VARIABLES_TABLE_RE = re.compile(
    r"^\[Runsheet\.variables\][ \t]*\r?\n(?:.*?\n)*?(?P<trail>\n*)(?=^\[|\Z)",
    re.MULTILINE | re.DOTALL,
)


def retarget(source_path: Path, target_path: Path) -> str:
    """Build an updated runsheet: `source`'s full content — structure,
    steps, everything — with `target`'s own [Runsheet.variables] values
    swapped in for source's. This is how a structural edit to a master
    runsheet gets pushed out to a copy of it that was customized only by
    its variables (e.g. a per-environment or per-customer copy): rerun
    retarget with the updated master as `source` and the copy as `target`.

    Both runsheets must declare exactly the same set of variable names —
    only their values may differ — and must not be the same file (checked
    by the caller, which also decides what to do with the result)."""
    source_vars = read_variables(source_path)
    target_vars = read_variables(target_path)

    missing_in_target = source_vars.keys() - target_vars.keys()
    missing_in_source = target_vars.keys() - source_vars.keys()
    if missing_in_target or missing_in_source:
        details = []
        if missing_in_target:
            details.append(f"only in {source_path}: {sorted(missing_in_target)}")
        if missing_in_source:
            details.append(f"only in {target_path}: {sorted(missing_in_source)}")
        raise ValueError(
            f"variable dictionaries don't match between {source_path} and "
            f"{target_path} — {'; '.join(details)}"
        )

    source_text = source_path.read_text(encoding="utf-8")
    if not source_vars:
        return source_text  # neither side has variables — nothing to swap in

    body = "".join(f"{name} = {_toml_quote(target_vars[name])}\n" for name in source_vars)
    merged_text, count = _VARIABLES_TABLE_RE.subn(
        lambda m: f"[Runsheet.variables]\n{body}{m['trail']}", source_text, count=1
    )
    if count == 0:
        raise ValueError(
            f"{source_path}: declares [Runsheet.variables] entries but no "
            f"'[Runsheet.variables]' table header was found to update it — "
            f"inline 'variables = {{...}}' tables aren't supported by --update"
        )
    return merged_text


@dataclass
class Step:
    index: int  # 1-based position in the runsheet
    summary: str
    description: str = ""
    budget_seconds: int | None = None
    commands: str = ""
    announcement_started: str = ""
    announcement_finished: str = ""

    state: StepState = StepState.PENDING
    started_at: float | None = None  # time.monotonic() at the start of the current run
    elapsed_seconds: float = 0.0  # elapsed time for the current or last run
    restart_count: int = 0

    @property
    def title(self) -> str:
        return f"Step {self.index}: {self.summary}"

    @property
    def has_announcements(self) -> bool:
        return bool(self.announcement_started or self.announcement_finished)


@dataclass
class Runsheet:
    path: Path
    sha1: str
    name: str = ""  # from an optional [Runsheet] name=... metadata table
    time_guidance_seconds: int | None = None  # from an optional [Runsheet] time_guidance=...
    announcement_started: str = ""
    announcement_finished: str = ""
    steps: list[Step] = field(default_factory=list)

    @property
    def has_announcements(self) -> bool:
        return bool(self.announcement_started or self.announcement_finished)

    @classmethod
    def load(cls, path: Path) -> Runsheet:
        raw = path.read_bytes()
        sha1 = hashlib.sha1(raw).hexdigest()
        try:
            data = tomllib.loads(raw.decode("utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"{path}: invalid TOML: {exc}") from exc

        metadata = data.get("Runsheet", {})
        if not isinstance(metadata, dict):
            raise ValueError(f"{path}: [Runsheet] must be a table, not a list of tables")
        name = metadata.get("name")
        if not name or not isinstance(name, str):
            raise ValueError(f"{path}: [Runsheet] is missing required field 'name'")

        variables = _parse_variables(metadata, f"{path}: [Runsheet]")
        name = _substitute(name, variables, f"{path}: [Runsheet] field 'name'")

        time_guidance_seconds = None
        time_guidance_value = metadata.get("time_guidance")
        if time_guidance_value is not None:
            time_guidance_seconds = _parse_time_seconds(
                time_guidance_value, f"{path}: [Runsheet] field 'time_guidance'"
            )

        runsheet_announcement_started, runsheet_announcement_finished = _paired_announcements(
            metadata, f"{path}: [Runsheet]"
        )
        runsheet_announcement_started = _substitute(
            runsheet_announcement_started, variables, f"{path}: [Runsheet] field 'announcement_started'"
        )
        runsheet_announcement_finished = _substitute(
            runsheet_announcement_finished, variables, f"{path}: [Runsheet] field 'announcement_finished'"
        )

        entries = data.get("Step", [])
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"{path}: no [[Step]] entries found")

        steps: list[Step] = []
        for i, entry in enumerate(entries, start=1):
            summary = entry.get("summary")
            if not summary or not isinstance(summary, str):
                raise ValueError(f"{path}: Step {i} is missing required field 'summary'")

            budget_seconds = None
            time_value = entry.get("time")
            if time_value is not None:
                budget_seconds = _parse_time_seconds(time_value, f"{path}: Step {i} field 'time'")

            announcement_started, announcement_finished = _paired_announcements(
                entry, f"{path}: Step {i}"
            )

            steps.append(
                Step(
                    index=i,
                    summary=_substitute(summary, variables, f"{path}: Step {i} field 'summary'"),
                    description=_substitute(
                        entry.get("description", ""), variables, f"{path}: Step {i} field 'description'"
                    ),
                    budget_seconds=budget_seconds,
                    commands=_substitute(
                        entry.get("commands", ""), variables, f"{path}: Step {i} field 'commands'"
                    ),
                    announcement_started=_substitute(
                        announcement_started, variables, f"{path}: Step {i} field 'announcement_started'"
                    ),
                    announcement_finished=_substitute(
                        announcement_finished, variables, f"{path}: Step {i} field 'announcement_finished'"
                    ),
                )
            )

        if time_guidance_seconds is not None:
            specified_seconds = sum(s.budget_seconds for s in steps if s.budget_seconds is not None)
            if specified_seconds > time_guidance_seconds:
                raise ValueError(
                    f"{path}: [Runsheet] field 'time_guidance' "
                    f"({format_seconds(time_guidance_seconds)}) is less than the sum of all "
                    f"steps' specified 'time' budgets ({format_seconds(specified_seconds)}) — "
                    f"increase time_guidance or reduce step budgets"
                )

        return cls(
            path=path, sha1=sha1, name=name,
            time_guidance_seconds=time_guidance_seconds,
            announcement_started=runsheet_announcement_started,
            announcement_finished=runsheet_announcement_finished,
            steps=steps,
        )

    @property
    def short_sha1(self) -> str:
        return self.sha1[:7]
