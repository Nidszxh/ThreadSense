"""Prompt templates for the LLM pipeline.

Kept close to the research prompts in `src/experiments/prompt_experiments.py`
(hierarchical local+global summarization) so experiments stay reproducible.
"""

from __future__ import annotations

SYSTEM_SUMMARIZER = (
    "You summarize Reddit discussion threads. Be faithful to what commenters "
    "actually said, balance agreement and disagreement, and write in clear, "
    "plain English."
)


def build_local_prompt(root_comment: str, replies: str) -> str:
    return (
        "Root Comment: {root}\n"
        "Replies:\n{replies}\n\n"
        "Step 1: Identify the main discussion points of this branch.\n"
        "Step 2: Summarize in 2-3 sentences.\n\n"
        "Summary:"
    ).format(root=root_comment, replies=replies or "(no replies)")


def build_global_prompt(local_summaries: list[str]) -> str:
    joined = "\n- ".join(local_summaries) if local_summaries else "None."
    return (
        "You are given partial summaries of different discussion branches "
        "from one Reddit thread:\n- {joined}\n\n"
        "Step 1: Identify overlapping ideas.\n"
        "Step 2: Merge them into a single, coherent overall summary "
        "(maximum 5 sentences).\n\n"
        "Final Summary:"
    ).format(joined=joined)


def build_key_points_prompt(global_summary: str, local_summaries: list[str]) -> str:
    joined = "\n- ".join(local_summaries) if local_summaries else "None."
    return (
        "Below is the overall summary of a Reddit thread followed by its "
        "branch summaries.\n\n"
        "Overall summary:\n{summary}\n\n"
        "Branch summaries:\n{joined}\n\n"
        "List the 5-8 key points discussed. Respond ONLY with a JSON array "
        'of strings, e.g. ["point one", "point two"].'
    ).format(summary=global_summary, joined=joined)


def build_insights_prompt(global_summary: str, stats_summary: str) -> str:
    return (
        "Below is a Reddit thread summary plus locally computed participation "
        "stats.\n\n"
        "Overall summary:\n{summary}\n\n"
        "Participation stats:\n{stats}\n\n"
        "Respond ONLY with a JSON object with exactly these keys:\n"
        '  "consensus": array of strings - what most commenters agree on,\n'
        '  "controversy": array of strings - the most contested points,\n'
        '  "themes": array of strings - recurring themes or topics.'
    ).format(summary=global_summary, stats=stats_summary)
