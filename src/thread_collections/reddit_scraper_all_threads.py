"""
Reddit Full Thread Extractor (for Dataset Building)
---------------------------------------------------
- Collects all top-level comments + all nested replies
- Designed for large-scale dataset creation
- Saves thread structure suitable for summarization or fine-tuning
"""

import praw
import json
from praw.models import MoreComments
from pathlib import Path

# ==============================
# REDDIT AUTHENTICATION
# ==============================
reddit = praw.Reddit(
    client_id="AEL7PpAUiOtlFdsTa5ZK-w",
    client_secret="MlOJ0isxgAXd5FKaQlqYOjz6HbLqWw",
    user_agent="ThreadSummarizer by /u/Frequent-Royal-6173",
    username="Frequent-Royal-6173",
    password="Rakshan@1234"
)


# ==============================
# RECURSIVE REPLY EXTRACTOR
# ==============================
def extract_replies(comment, depth=0):
    """
    Recursively extract a comment and all its replies,
    preserving depth and structure.
    """
    comment_obj = {
        "author": str(comment.author) if comment.author else "[deleted]",
        "body": getattr(comment, "body", ""),
        "score": getattr(comment, "score", 0),
        "depth": depth,
        "replies": []
    }

    for reply in getattr(comment, "replies", []):
        if isinstance(reply, MoreComments):
            continue
        comment_obj["replies"].append(extract_replies(reply, depth + 1))

    return comment_obj


# ==============================
# THREAD EXTRACTOR
# ==============================
def extract_all_comment_threads(submission_url=None, submission_id=None):
    """
    Extracts *all* top-level comments and their replies
    into the same structure as the old single-thread version.
    """
    if submission_url:
        submission = reddit.submission(url=submission_url)
    elif submission_id:
        submission = reddit.submission(id=submission_id)
    else:
        raise ValueError("Provide either a submission URL or submission ID.")

    print(f"🔍 Fetching full comment tree for: {submission.title}")
    submission.comments.replace_more(limit=None)

    all_threads = []
    for comment in submission.comments:
        if isinstance(comment, MoreComments):
            continue
        all_threads.append(extract_replies(comment, depth=0))

    data = {
        "post_title": submission.title,
        "post_url": submission.url,
        "comments": all_threads
    }

    return data


# ==============================
# MAIN EXECUTION
# ==============================
if __name__ == "__main__":
    submission_url = "https://www.reddit.com/r/AskReddit/comments/1m5z250/whats_a_completely_legal_action_that_would/"

    result = extract_all_comment_threads(submission_url=submission_url)

    # Save inside data/threads/
    output_dir = Path("data/threads")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clean filename from URL or title
    post_id = submission_url.strip("/").split("/")[-2]
    output_file = output_dir / "reddit_thread_all.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved full comment threads to: {output_file}")
    print(f"💬 Total top-level threads: {len(result['comments'])}")