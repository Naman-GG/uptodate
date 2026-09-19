"""Source adapters.

The ATS adapters enumerate a company board: `fetch(token) -> list[RawPosting]`.
Adzuna is query-driven instead: `fetch(query, country=..., pages=...)`, because
it is an aggregator with no notion of a per-company board.
"""
from . import adzuna, ashby, greenhouse, lever

# Board-oriented sources, driven by data/boards.json
BOARD_REGISTRY = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
}

# Query-oriented sources, driven by the search terms in the ingest config
QUERY_REGISTRY = {
    "adzuna": adzuna.fetch,
}


def fetch(source: str, token: str):
    """Fetch one company board from an ATS source."""
    try:
        adapter = BOARD_REGISTRY[source]
    except KeyError:
        raise ValueError(f"unknown board source: {source}") from None
    return adapter(token)
