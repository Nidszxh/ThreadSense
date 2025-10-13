"""Reddit ingestion via PRAW (credentials from env, never hardcoded).

Fetches the comment tree into the raw thread JSON shape, then passes it through
normalize_thread so all sources share one normalizer.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import praw
from praw.models import MoreComments

from app.config import get_settings
from app.ingest.base import IngestSource, RawThread
from app.ingest.normalize import normalize_thread

logger = logging.getLogger(__name__)

REDDIT_RE = re.compile(
    r"https?://(?:www\.|old\.|new\.|np\.)?reddit\.com/(?:r/[\w-]+/)?comments/"
    r"(?P<id>[\w]+)"
)


class RedditSource(IngestSource):
    name = "reddit"

    def __init__(self) -> None:
        self._reddit: praw.Reddit | None = None

    def _client(self) -> praw.Reddit:
        if self._reddit is not None:
            return self._reddit
        settings = get_settings()
        if not (settings.reddit_client_id and settings.reddit_client_secret):
            raise RuntimeError(
                "Reddit credentials missing: set REDDIT_CLIENT_ID and "
                "REDDIT_CLIENT_SECRET in your environment."
            )
        self._reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
            username=settings.reddit_username or None,
            password=settings.reddit_password or None,
        )
        return self._reddit

    def _submission_dict(self, submission: Any) -> dict[str, Any]:
        submission.comments.replace_more(limit=None)

        def extract_replies(comment: Any, depth: int = 0) -> dict[str, Any]:
            obj: dict[str, Any] = {
                "author": str(comment.author) if comment.author else "[deleted]",
                "body": getattr(comment, "body", "") or "",
                "score": getattr(comment, "score", 0),
                "depth": depth,
                "created_utc": getattr(comment, "created_utc", None),
                "replies": [],
            }
            for reply in getattr(comment, "replies", []):
                if isinstance(reply, MoreComments):
                    continue
                obj["replies"].append(extract_replies(reply, depth + 1))
            return obj

        comments: list[dict[str, Any]] = []
        for comment in submission.comments:
            if isinstance(comment, MoreComments):
                continue
            comments.append(extract_replies(comment, depth=0))

        return {
            "post_title": submission.title,
            "post_url": submission.url,
            "comments": comments,
        }

    def fetch(self, url: str) -> RawThread:
        match = REDDIT_RE.search(url)
        if not match:
            raise ValueError(f"Not a Reddit submission URL: {url}")
        submission_id = match.group("id")

        logger.info("Fetching Reddit submission %s from %s", submission_id, url)
        submission = self._client().submission(id=submission_id)
        raw = self._submission_dict(submission)
        return normalize_thread(
            raw,
            source=self.name,
            source_id=submission_id,
            url=submission.url,
            author=str(submission.author) if submission.author else None,
        )
