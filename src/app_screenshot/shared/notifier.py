"""Notifier port and console implementation."""

import sys
from typing import Literal, Protocol

Level = Literal["info", "warn", "error"]


class Notifier(Protocol):
    def notify(self, level: Level, msg: str) -> None: ...


class ConsoleNotifier:
    _PREFIX = {"info": "[info]", "warn": "[WARN]", "error": "[ERROR]"}

    def notify(self, level: Level, msg: str) -> None:
        stream = sys.stdout if level == "info" else sys.stderr
        print(f"{self._PREFIX[level]} {msg}", file=stream, flush=True)
