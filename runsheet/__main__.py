"""Entry point: python -m runsheet path/to/runsheet.toml"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .app import RunsheetApp
from .logbook import Logbook
from .model import Runsheet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="runsheet", description=__doc__)
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
    args = parser.parse_args(argv)

    runsheet_path = args.runsheet.expanduser().resolve()
    if not runsheet_path.is_file():
        parser.error(f"no such file: {runsheet_path}")

    if args.validate:
        try:
            Runsheet.load(runsheet_path)
        except ValueError as exc:
            print(exc)
            return 1
        print("No errors")
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
