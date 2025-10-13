"""Participant / context statistics computed locally from stored comments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ParticipantRow:
    author: str
    comment_count: int
    avg_score: float
    max_depth: int
    is_root_author: bool


def compute_participants(
    comments: list[dict[str, Any]],
) -> list[ParticipantRow]:
    """Aggregate per-author stats from flat comments (author, score, depth)."""
    by_author: dict[str, dict[str, Any]] = {}
    for comment in comments:
        author = comment.get("author") or "[deleted]"
        stats = by_author.setdefault(
            author,
            {
                "comment_count": 0,
                "score_sum": 0,
                "max_depth": 0,
                "is_root_author": False,
            },
        )
        stats["comment_count"] += 1
        stats["score_sum"] += comment.get("score", 0) or 0
        stats["max_depth"] = max(stats["max_depth"], comment.get("depth", 0) or 0)
        if comment.get("depth", 0) == 0:
            stats["is_root_author"] = True

    rows = [
        ParticipantRow(
            author=author,
            comment_count=stats["comment_count"],
            avg_score=stats["score_sum"] / stats["comment_count"],
            max_depth=stats["max_depth"],
            is_root_author=stats["is_root_author"],
        )
        for author, stats in by_author.items()
    ]
    return sorted(rows, key=lambda r: r.comment_count, reverse=True)
