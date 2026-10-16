"""Encoding ports and the raw frame value object."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RawFrame:
    width: int
    height: int
    rgb: bytes


class Encoder(Protocol):
    fmt: str  # "webp" | "jpeg"
    ext: str  # "webp" | "jpg"

    def luma_stddev(self, frame: RawFrame) -> float: ...

    def encode(self, frame: RawFrame) -> bytes: ...
