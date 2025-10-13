"""LLM summarization service.

Builds discussion branches from the DB comment tree (using real `parent_id`
foreign keys, NOT author-name matching like the research code), selects the
largest branches that fit a token budget, and generates three artifacts:
- summary       (hierarchical local + global, one row kind=summary)
- key_points    (JSON list of the main points)
- insights      (consensus / controversy / themes + local stats)

Each generation writes to the `summaries` table (upsert by thread_id+kind).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    SUMMARY_KIND_INSIGHTS,
    SUMMARY_KIND_KEY_POINTS,
    SUMMARY_KIND_SUMMARY,
    Comment,
    ParticipantStat,
    Summary,
)
from app.nlp import prompts
from app.nlp.llm_client import LLMError, get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class Branch:
    root: Comment
    comments: list[Comment] = field(default_factory=list)


def build_branches(comments: list[Comment]) -> list[Branch]:
    """Group comments into root branches using parent_id (exact tree)."""
    by_parent: dict[int | None, list[Comment]] = {}
    for comment in comments:
        by_parent.setdefault(comment.parent_id, []).append(comment)

    def collect(parent_id: int | None, out: list[Comment]) -> None:
        for comment in by_parent.get(parent_id, []):
            out.append(comment)
            collect(comment.id, out)

    branches: list[Branch] = []
    for root in by_parent.get(None, []):
        members: list[Comment] = []
        collect(root.id, members)
        branches.append(Branch(root=root, comments=[root, *members]))
    return branches


def select_branches(
    branches: list[Branch],
    max_branches: int,
    max_chars: int,
    max_comment_chars: int,
    max_comments_per_branch: int,
) -> list[Branch]:
    """Pick the biggest branches that fit the character budget; never return empty."""
    def size(branch: Branch) -> int:
        capped = min(len(branch.comments), max_comments_per_branch)
        return sum(
            min(len(c.body), max_comment_chars)
            for c in branch.comments[:capped]
        )

    ordered = sorted(branches, key=size, reverse=True)
    selected: list[Branch] = []
    budget = max_chars
    for branch in ordered:
        if len(selected) >= max_branches:
            break
        if size(branch) > budget:
            continue
        selected.append(branch)
        budget -= size(branch)

    if not selected and ordered:
        selected = [ordered[0]]
    return selected


def format_branch(
    branch: Branch,
    max_comment_chars: int,
    max_comments_per_branch: int,
) -> str:
    capped = branch.comments[:max_comments_per_branch]
    lines = [
        f"Root ({branch.root.author or '[deleted]'}): "
        f"{branch.root.body[:max_comment_chars]}"
    ]
    for comment in capped[1:]:
        author = comment.author or "[deleted]"
        lines.append(f"- {author}: {comment.body[:max_comment_chars]}")
    return "\n".join(lines)


def _stats_summary(participants: list[ParticipantStat], comment_count: int) -> str:
    if not participants:
        return "No participants recorded."
    most_active = participants[0]
    roots = [p for p in participants if p.is_root_author]
    lines = [
        f"- {comment_count} comments across {len(participants)} participants",
        f"- most active: {most_active.author} with {most_active.comment_count} comments",
        f"- top commenter avg score: {most_active.avg_score:.1f}",
        f"- {len(roots)} participants started top-level discussions",
        f"- deepest thread depth: {max((p.max_depth for p in participants), default=0)}",
    ]
    return "\n".join(lines)


def _clean_summary(text: str) -> str:
    text = text.strip()
    match = re.search(r"(?is)^\s*(?:final\s*)?summary:\s*", text)
    if match:
        text = text[match.end():]
    return text.strip()


def _parse_json(text: str) -> object:
    """Parse a JSON array/object out of the model's reply (defensive)."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return None


def _save_summary(
    db: Session,
    thread_id: int,
    kind: str,
    content: dict,
    model: str,
    tokens_in: int,
    tokens_out: int,
) -> None:
    row = (
        db.query(Summary)
        .filter(Summary.thread_id == thread_id, Summary.kind == kind)
        .first()
    )
    if row is None:
        row = Summary(thread_id=thread_id, kind=kind)
        db.add(row)
    row.content = content
    row.model = model
    row.tokens_in = tokens_in
    row.tokens_out = tokens_out
    db.commit()


def generate_summary(db: Session, thread_id: int) -> dict:
    settings = get_settings()
    client = get_llm_client()
    comments = (
        db.query(Comment)
        .filter(Comment.thread_id == thread_id)
        .order_by(Comment.position)
        .all()
    )
    if not comments:
        raise ValueError(f"Thread {thread_id} has no comments")

    branches = build_branches(comments)
    selected = select_branches(
        branches,
        settings.llm_max_branches,
        settings.llm_summary_max_chars,
        settings.llm_max_comment_chars,
        settings.llm_max_comments_per_branch,
    )
    if not selected:
        raise ValueError("No branches to summarize")

    total_in = total_out = 0
    local_summaries: list[str] = []
    for branch in selected:
        branch_text = format_branch(
            branch,
            settings.llm_max_comment_chars,
            settings.llm_max_comments_per_branch,
        )
        result = client.complete(
            prompts.SYSTEM_SUMMARIZER,
            prompts.build_local_prompt(branch.root.body, branch_text),
            max_tokens=300,
        )
        total_in += result.tokens_in
        total_out += result.tokens_out
        local_summaries.append(_clean_summary(result.text))

    result = client.complete(
        prompts.SYSTEM_SUMMARIZER,
        prompts.build_global_prompt(local_summaries),
        max_tokens=400,
    )
    total_in += result.tokens_in
    total_out += result.tokens_out
    summary = _clean_summary(result.text)

    _save_summary(
        db,
        thread_id,
        SUMMARY_KIND_SUMMARY,
        {
            "summary": summary,
            "local_summaries": local_summaries,
            "branches_covered": len(selected),
            "total_comments": len(comments),
        },
        client.model,
        total_in,
        total_out,
    )
    return {"summary": summary, "branches_covered": len(selected)}


def generate_key_points(db: Session, thread_id: int) -> dict:
    client = get_llm_client()
    summary_row = (
        db.query(Summary)
        .filter(
            Summary.thread_id == thread_id,
            Summary.kind == SUMMARY_KIND_SUMMARY,
        )
        .first()
    )
    if summary_row is None:
        raise ValueError(f"Thread {thread_id} has no summary to extract points from")

    content = summary_row.content or {}
    result = client.complete(
        prompts.SYSTEM_SUMMARIZER,
        prompts.build_key_points_prompt(
            content.get("summary", ""),
            content.get("local_summaries", []),
        ),
        max_tokens=400,
        json_mode=True,
    )
    points = _parse_json(result.text)
    if not isinstance(points, list) or not points:
        raise LLMError(f"key_points did not return a JSON array: {result.text[:200]!r}")
    points = [str(p).strip() for p in points]

    _save_summary(
        db,
        thread_id,
        SUMMARY_KIND_KEY_POINTS,
        {"points": points},
        client.model,
        result.tokens_in,
        result.tokens_out,
    )
    return {"points": points}


def generate_insights(db: Session, thread_id: int) -> dict:
    client = get_llm_client()
    summary_row = (
        db.query(Summary)
        .filter(
            Summary.thread_id == thread_id,
            Summary.kind == SUMMARY_KIND_SUMMARY,
        )
        .first()
    )
    if summary_row is None:
        raise ValueError(f"Thread {thread_id} has no summary to derive insights from")

    participants = (
        db.query(ParticipantStat)
        .filter(ParticipantStat.thread_id == thread_id)
        .order_by(ParticipantStat.comment_count.desc())
        .all()
    )
    comment_count = (
        db.query(func.count(Comment.id)).filter(Comment.thread_id == thread_id).scalar()
        or 0
    )
    content = summary_row.content or {}
    stats_text = _stats_summary(participants, comment_count)

    result = client.complete(
        prompts.SYSTEM_SUMMARIZER,
        prompts.build_insights_prompt(content.get("summary", ""), stats_text),
        max_tokens=400,
        json_mode=True,
    )
    data = _parse_json(result.text)
    if not isinstance(data, dict):
        raise LLMError(f"insights did not return a JSON object: {result.text[:200]!r}")

    _save_summary(
        db,
        thread_id,
        SUMMARY_KIND_INSIGHTS,
        data,
        client.model,
        result.tokens_in,
        result.tokens_out,
    )
    return data
