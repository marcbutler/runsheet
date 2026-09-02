# Runsheet Format

- **[Runsheet]**: Required table of runsheet-level metadata (since it holds the required **name** field below).
  - **name**: Required - shown next to RUNSHEET in the toolbar.
  - **time_guidance**: Optional - a total duration guidance for the whole runsheet. When set, the RUNSHEET toolbar group shows one fixed-width digital clock: it counts down from time_guidance once the first step is started, and once that runs out it flips to counting up from zero — prefixed `+` and in bold — to show how far over the guidance the run is.
  - **announcement_started** / **announcement_finished**: Optional - short text for the whole run. Shown as two pseudo steps bookending the step list — RUNSHEET STARTED before the first step, RUNSHEET FINISHED after the last — each just the text and a Copy chip, not a real step. A runsheet with either must have both.
  - **[Runsheet.variables]**: Optional table of `name="value"` pairs. Reference one anywhere in name/description/summary/commands/announcements as `{{name}}` — it's substituted at load time. Referencing an undefined variable is a load error. Variable values are literal (never themselves re-scanned for `{{...}}`), and `{{...}}` is otherwise left alone, so real shell variables like `$HOME` in a commands block are untouched. To write a literal `{{name}}` without it being treated as a reference, double the braces: `{{{{name}}}}` renders as the literal text `{{name}}` (mirrors Python's `str.format()` escaping — `{{` -> `{`, `}}` -> `}`).
- **[Step]**
  - **summary**: Required - one line description.
  - **description**: Optional - contextual notes.
  - **time**: Optional - budgeted time.
  - **commands**: Optional - command reference.
  - **announcement_started** / **announcement_finished**: Optional - short text meant to be pasted into an external comms channel (Slack, a bridge, etc.) when the step starts/finishes. A step with either must have both.

## Sample

```TOML
[Runsheet]
name="This is displayed next to RUNSHEET in the toolbar."
time_guidance=hh:mm:ss
announcement_started="Short status line, copied to the clipboard, for when the whole runsheet starts."
announcement_finished="Short status line, copied to the clipboard, for when the whole runsheet finishes."

[Runsheet.variables]
change_ticket="CHG-48213"
db_host="pg-primary-01.internal"

[[Step]]
summary="This is a typically one line entry for {{change_ticket}}."
description="This is a more detailed contextual explanation."
time=hh:mm:ss
commands="""
ssh {{db_host}} 'ls /'

rm /tmp/**
"""
announcement_started="Short status line, copied to the clipboard, for when this step starts."
announcement_finished="Short status line, copied to the clipboard, for when this step finishes."
```

## Examples

- [sample_runsheet.toml](sample_runsheet.toml)
- [sample_runsheet_large.toml](sample_runsheet_large.toml)
