"""Entry point: python -m runsheet path/to/runsheet.toml"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from . import __version__
from .app import RunsheetApp
from .export import export_text
from .logbook import Logbook
from .model import Runsheet, retarget


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="runsheet", description=__doc__)
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}",
    )
    parser.add_argument("runsheet", type=Path, help="path to the runsheet .toml file")
    parser.add_argument(
        "--log-dir", type=Path, default=None,
        help="directory for the JSONL session log (default: alongside the runsheet)",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="check the runsheet for errors (undefined {{variables}}, a time_guidance/step-time "
        "mismatch, and everything else load-time validation covers), print the result, and "
        "exit — never starts the UI",
    )
    parser.add_argument(
        "--update", type=Path, default=None, metavar="TARGET",
        help="update TARGET, an existing copy of a runsheet, with the structure of the "
        "runsheet given as the main argument (treated as the source) while keeping "
        "TARGET's own [Runsheet.variables] values — for pushing an edit made to a "
        "master runsheet out to a copy that was customized only by its variables "
        "(e.g. per-environment or per-customer). Source and target must declare the "
        "same set of variable names and must not be the same file. Never starts the UI",
    )
    parser.add_argument(
        "--export", nargs="?", const=True, default=None, type=Path, metavar="PATH",
        help="write the runsheet out as sparse, readable plain UTF-8 text (no BOM), with all "
        "{{variables}} already substituted, to PATH — or, with no PATH given, to "
        "<runsheet-stem>.txt alongside it — never starts the UI",
    )
    args = parser.parse_args(argv)

    modes = {"--validate": args.validate, "--update": args.update is not None, "--export": args.export is not None}
    selected = [name for name, on in modes.items() if on]
    if len(selected) > 1:
        parser.error(f"{' and '.join(selected)} cannot be combined")

    runsheet_path = args.runsheet.expanduser().resolve()
    if not runsheet_path.is_file():
        parser.error(f"no such file: {runsheet_path}")

    if args.update is not None:
        target_path = args.update.expanduser().resolve()
        if not target_path.is_file():
            parser.error(f"no such file: {target_path}")
        if target_path == runsheet_path:
            parser.error("--update must not be the same file as the source runsheet")

        try:
            merged_text = retarget(runsheet_path, target_path)
        except ValueError as exc:
            print(exc)
            return 1

        # Write to a scratch file next to the target and validate that
        # first — a load error must never leave target overwritten with a
        # broken file. Only once it's confirmed to load cleanly does the
        # atomic rename replace target's actual content.
        fd, tmp_name = tempfile.mkstemp(
            dir=target_path.parent, prefix=f".{target_path.name}.", suffix=".tmp"
        )
        tmp_path = Path(tmp_name)
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(merged_text)
            Runsheet.load(tmp_path)
        except ValueError as exc:
            # Reword the scratch file's own path back to target's, so the
            # error reads like it's about the file the user actually named.
            tmp_path.unlink(missing_ok=True)
            print(str(exc).replace(str(tmp_path), str(target_path), 1))
            return 1
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
        tmp_path.replace(target_path)
        print(f"{target_path}: updated from {runsheet_path}")
        return 0

    if args.validate:
        try:
            Runsheet.load(runsheet_path)
        except ValueError as exc:
            print(exc)
            return 1
        print("No errors")
        return 0

    if args.export is not None:
        if args.export is True:  # bare --export, no PATH given
            export_path = runsheet_path.with_suffix(".txt")
        else:
            export_path = args.export.expanduser().resolve()
            if not export_path.parent.is_dir():
                parser.error(f"no such directory: {export_path.parent}")

        try:
            runsheet = Runsheet.load(runsheet_path)
        except ValueError as exc:
            print(exc)
            return 1
        # encoding="utf-8" (never "utf-8-sig") never writes a BOM;
        # newline="\n" keeps line endings deterministic across platforms
        # rather than letting write_text translate them on Windows.
        export_path.write_text(export_text(runsheet), encoding="utf-8", newline="\n")
        print(f"{export_path}: exported from {runsheet_path}")
        return 0

    try:
        runsheet = Runsheet.load(runsheet_path)
    except ValueError as exc:
        parser.error(str(exc))
        return 2  # unreachable; parser.error exits, but keeps type-checkers happy

    log_dir = args.log_dir.expanduser().resolve() if args.log_dir else runsheet_path.parent
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = log_dir / f"{runsheet_path.stem}_{timestamp}.jsonl"
    logbook = Logbook(log_path)

    app = RunsheetApp(runsheet, logbook)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
