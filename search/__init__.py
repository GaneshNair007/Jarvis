"""
JARVIS Local Search Engine Package.
Millisecond-speed private local search without external search APIs.
"""

from search.hybrid_ranker import HybridRanker
from search.local_search_engine import LocalSearchEngine, SearchHit
from search.meili_search import MeiliSearchEngine
from search.search_cache import SearchCache
from search.search_orchestrator import SearchOrchestrator
from search.searxng_client import SearXNGClient
from search.semantic_search import QdrantSemanticSearch

# Singleton orchestrator instance for app-wide use
search_orchestrator = SearchOrchestrator()

__all__ = [
    "LocalSearchEngine",
    "SearchHit",
    "SearchCache",
    "MeiliSearchEngine",
    "QdrantSemanticSearch",
    "SearXNGClient",
    "HybridRanker",
    "SearchOrchestrator",
    "search_orchestrator",
]
