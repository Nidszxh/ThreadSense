from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IngestRequest(BaseModel):
    url: str = Field(..., min_length=5)


class IngestResponse(BaseModel):
    task_id: str
    url: str


class ThreadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    title: str
    url: str
    author: str | None
    status: str
    error: str | None
    created_at: datetime


class CommentOut(BaseModel):
    id: int
    thread_id: int
    parent_id: int | None
    author: str | None
    body: str
    score: int
    depth: int
    keywords: list[str] = Field(default_factory=list)


class ThreadDetailOut(ThreadOut):
    comment_count: int = 0


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    author: str
    comment_count: int
    avg_score: float
    max_depth: int
    is_root_author: bool


class SummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_id: int
    kind: str
    content: dict
    model: str | None
    tokens_in: int | None
    tokens_out: int | None
    created_at: datetime


class SearchCommentHit(BaseModel):
    id: int
    thread_id: int
    thread_title: str
    author: str | None
    body: str
    score: float
    distance: float | None = None


class SearchSummaryHit(BaseModel):
    id: int
    thread_id: int
    thread_title: str
    kind: str
    content: dict
    score: float


class SearchResponse(BaseModel):
    query: str
    keyword_comments: list[SearchCommentHit]
    keyword_summaries: list[SearchSummaryHit]
    semantic_comments: list[SearchCommentHit]
