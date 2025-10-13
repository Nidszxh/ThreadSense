from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class RawComment:
    author: str | None
    body: str
    score: int = 0
    depth: int = 0
    created_at: datetime | None = None
    parent_index: int | None = None


@dataclass
class RawThread:
    source: str
    source_id: str
    title: str
    url: str
    author: str | None = None
    comments: list[RawComment] = field(default_factory=list)


class IngestSource(Protocol):
    name: str

    def fetch(self, url: str) -> RawThread: ...


class SourceNotFoundError(ValueError):
    """Raised when no IngestSource can handle the given URL."""
