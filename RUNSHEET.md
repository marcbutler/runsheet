# Runsheet Format

- **[Runsheet]**: Required table of runsheet-level metadata (since it holds the required **name** field below).
  - **name**: Required - shown next to RUNSHEET in the toolbar.
  - **time_guidance**: Optional - a total duration guidance for the whole runsheet. When set, the RUNSHEET toolbar group shows one fixed-width digital clock: it counts down from time_guidance once the first step is started, and once that runs out it flips to counting up from zero — prefixed `+` and in bold — to show how far over the guidance the run is.
  - **[Runsheet.variables]**: Optional table of `name="value"` pairs. Reference one anywhere in name/description/summary/commands/announcements as `{{name}}` — it's substituted at load time. Referencing an undefined variable is a load error. Variable values are literal (never themselves re-scanned for `{{...}}`), and `{{...}}` is otherwise left alone, so real shell variables like `$HOME` in a commands block are untouched. To write a literal `{{name}}` without it being treated as a reference, double the braces: `{{{{name}}}}` renders as the literal text `{{name}}` (mirrors Python's `str.format()` escaping — `{{` -> `{`, `}}` -> `}`).
- **[Step]**: An array of tables holding both real steps and interspersed notes, told apart by an optional **kind** field.
  - **kind**: Optional - `"task"` (the default, so existing runsheets need no change) or `"note"`.
  - Task fields (`kind="task"`, or `kind` omitted):
    - **summary**: Required - one line description.
    - **description**: Optional - contextual notes.
    - **time**: Optional - budgeted time.
    - **commands**: Optional - command reference.
    - **announcement_started** / **announcement_finished**: Optional - short text meant to be pasted into an external comms channel (Slack, a bridge, etc.) when the step starts/finishes. A step with either must have both.
  - Note fields (`kind="note"`):
    - **text**: Required - plain informational text, shown in the UI as its own pseudo step (not a real step: no state, no start/finish/reset/skip, no numbering) wherever it appears in the file, and interspersed the same way in `--export`'s output. A note placed before the first task or after the last one is the way to give the whole run its own start/finish message.

  A note is written as its own `[[Step]]` entry, positioned in the file wherever it should appear relative to the surrounding tasks:

  ```TOML
  [[Step]]
  summary="Take a snapshot"

  [[Step]]
  kind="note"
  text="Coffee break — the next step needs a clear head."

  [[Step]]
  summary="Apply the migration"
  ```

  Why a note is a `[[Step]]` entry with a `kind` field, rather than its own `[[Note]]` array: TOML gives each array-of-tables name its own list, so two separately-named arrays (`[[Step]]` and `[[Note]]`) would each preserve their *own* internal order but lose the order *between* them — there'd be no way to tell, from the parsed file, whether a given note came before or after a given step. Keeping both under one `[[Step]]` array means the file's declaration order *is* the display order, with no separate position field needed.

## Sample

```TOML
[Runsheet]
name="This is displayed next to RUNSHEET in the toolbar."
time_guidance=hh:mm:ss

[Runsheet.variables]
change_ticket="CHG-48213"
db_host="pg-primary-01.internal"

[[Step]]
kind="note"
text="Short status line, copied to the clipboard, for when the whole runsheet starts."

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

[[Step]]
kind="note"
text="Short status line, copied to the clipboard, for when the whole runsheet finishes."
```

## Examples

- [sample_runsheet.toml](sample_runsheet.toml)
- [sample_runsheet_large.toml](sample_runsheet_large.toml)
