from app.ingest.base import IngestSource, SourceNotFoundError
from app.ingest.reddit import REDDIT_RE, RedditSource

SOURCES: dict[str, IngestSource] = {
    "reddit": RedditSource(),
}


def resolve_source(url: str) -> IngestSource:
    if REDDIT_RE.search(url):
        return SOURCES["reddit"]
    raise SourceNotFoundError(f"No ingestion source supports URL: {url}")
