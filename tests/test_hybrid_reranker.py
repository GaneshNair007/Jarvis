"""Tests for Reciprocal Rank Fusion (RRF) Hybrid Reranker."""

from jarvis.search.hybrid_reranker import ReciprocalRankFusion, fuse_lexical_and_semantic


def test_rrf_scoring_combines_ranks():
    rrf = ReciprocalRankFusion(k=60)

    # Document 1 is #1 in lexical and #2 in semantic
    # Document 2 is #2 in lexical and #1 in semantic
    # Document 3 is only in lexical (#3)
    lexical = [
        {"id": "doc1", "text": "PostgreSQL indexing guide"},
        {"id": "doc2", "text": "SQLite memory storage"},
        {"id": "doc3", "text": "Docker compose setup"},
    ]
    semantic = [
        {"id": "doc2", "text": "SQLite memory storage"},
        {"id": "doc1", "text": "PostgreSQL indexing guide"},
    ]

    fused = rrf.fuse([lexical, semantic], limit=2)
    assert len(fused) == 2
    # Both doc1 and doc2 appeared in both lists: (1/(60+1) + 1/(60+2))
    assert fused[0]["id"] in ("doc1", "doc2")
    assert fused[0]["rrf_score"] > 0.03


def test_fuse_lexical_and_semantic_helper():
    lexical = [{"id": "a", "val": 10}, {"id": "b", "val": 20}]
    semantic = [{"id": "b", "val": 20}, {"id": "c", "val": 30}]

    results = fuse_lexical_and_semantic(lexical, semantic, limit=3)
    assert len(results) == 3
    # 'b' was in both lists, should be top rank
    assert results[0]["id"] == "b"
