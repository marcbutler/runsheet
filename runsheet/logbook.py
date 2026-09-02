"""Append-only JSONL event log for a runsheet session."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO


class Logbook:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file: TextIO = path.open("a", encoding="utf-8")

    def write(self, event: str, **fields: Any) -> None:
        record = {
            "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
            "event": event,
            **fields,
        }
        self._file.write(json.dumps(record) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()
