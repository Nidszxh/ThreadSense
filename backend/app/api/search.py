from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.thread import SearchCommentHit, SearchResponse, SearchSummaryHit
from app.services import search as search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse)
def search(
    q: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> SearchResponse:
    return SearchResponse(
        query=q,
        keyword_comments=[
            SearchCommentHit.model_validate(h, from_attributes=True)
            for h in search_service.keyword_search_comments(db, q, limit)
        ],
        keyword_summaries=[
            SearchSummaryHit.model_validate(h, from_attributes=True)
            for h in search_service.keyword_search_summaries(db, q, limit)
        ],
        semantic_comments=[
            SearchCommentHit.model_validate(h, from_attributes=True)
            for h in search_service.semantic_search_comments(db, q, limit)
        ],
    )
