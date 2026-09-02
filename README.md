# Runsheet

A basic portable UI for following a click-ops runsheet (checklist).

## Requires

- Python 3.14 or greater with Tkinter support

## Invocation

```sh
python3 -m runsheet sample_runsheet.toml
```

This creates a JSONL session log named `<runsheet-stem>_<timestamp>.jsonl` (e.g. `sample_runsheet_20260902-143205.jsonl`) **next to the runsheet file** — since the example above runs from the same directory the runsheet lives in, that log lands in the current directory too. Point at a runsheet elsewhere (`python3 -m runsheet ~/ops/runsheet.toml`) and the log goes next to *that* file instead, not your current directory. Pass `--log-dir` to put it somewhere else entirely:

```sh
python3 -m runsheet sample_runsheet.toml --log-dir ~/runsheet-logs
```

### Validating a runsheet

```sh
python3 -m runsheet sample_runsheet.toml --validate
```

Runs the same load-time checks (undefined `{{variables}}`, a `time_guidance`/step-time mismatch, missing `summary`, malformed `time`, an announcement with only `_started` or only `_finished`, etc.) without starting the UI. Prints `No errors` and exits 0 if the runsheet is clean; otherwise prints the first error found to stdout and exits 1. It stops at the first error — fix it and re-run to see the next one, if any.


## Runsheet Format

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

### Sample

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

## UI 

![UI](images/ui.png)

## Installation

Runsheet needs Python 3.14+ with Tkinter — on several platforms Tkinter is a separate package from Python itself, so it's called out below wherever that's the case.

### macOS (Homebrew)

```sh
brew install python@3.14 python-tk@3.14
```

### Windows (winget)

```sh
winget install --id Python.Python.3.14
```

The official python.org installer that winget uses bundles Tkinter already, so no separate package is needed.

### Debian / Ubuntu (apt)

```sh
sudo apt update
sudo apt install python3 python3-tk
```

### Fedora / RHEL / CentOS (dnf)

```sh
sudo dnf install python3 python3-tkinter
```

### Verify

```sh
python3 -c "import tkinter; print(tkinter.TkVersion)"
```

This should print a version number (e.g. `9.0`) with no errors.
