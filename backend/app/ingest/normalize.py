"""Normalize scraped thread JSON into a flat RawThread.

Handles both thread shapes used by the original research pipeline:
- new full-thread:  {"post_title", "comments": [{author, body, score, depth, replies: [...]}]}
- old single-thread: {"post_title", "selected_comment": {author, body, score, replies: [...]}}

This is the service-side port of `src/thread_keyword_extraction.py:flatten_json_thread`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.ingest.base import RawComment, RawThread


def _body(comment: dict[str, Any]) -> str:
    value = comment.get("body") or comment.get("text")
    return value or ""


def _created_at(comment: dict[str, Any]) -> datetime | None:
    ts = comment.get("created_utc")
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def normalize_thread(
    raw: dict[str, Any],
    *,
    source: str,
    source_id: str,
    url: str,
    title: str | None = None,
    author: str | None = None,
) -> RawThread:
    flat: list[RawComment] = []

    def traverse(comment: dict[str, Any], parent_index: int | None) -> None:
        flat.append(
            RawComment(
                author=comment.get("author"),
                body=_body(comment),
                score=comment.get("score", 0) or 0,
                depth=comment.get("depth", 0) or 0,
                created_at=_created_at(comment),
                parent_index=parent_index,
            )
        )
        index = len(flat) - 1
        for reply in comment.get("replies", []):
            traverse(reply, parent_index=index)

    if "selected_comment" in raw:
        traverse(raw["selected_comment"], parent_index=None)
    elif "comments" in raw:
        for top_comment in raw["comments"]:
            traverse(top_comment, parent_index=None)
    else:
        raise ValueError(
            "Invalid thread JSON: expected 'selected_comment' or 'comments'."
        )

    return RawThread(
        source=source,
        source_id=source_id,
        title=title or raw.get("post_title", ""),
        url=url,
        author=author,
        comments=flat,
    )
