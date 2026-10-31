"""
JARVIS Researcher Agent (PWR-290 / PWR-291)
PDF Spec: Pages 352-371 — Multi-Agent & Orchestration

Executes multi-source research tasks:
- Local search brain (SQLite FTS5 + Qdrant vectors)
- Web search via SearXNG / browser worker
- URL deep-reading via Playwright
- Synthesises results into a cited evidence package
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from jarvis.core.logger import get_logger

logger = get_logger("agents.researcher")


@dataclass
class ResearchResult:
    """A single research finding with provenance."""
    source: str
    title: str
    snippet: str
    url: Optional[str] = None
    relevance_score: float = 0.0
    retrieved_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "snippet": self.snippet,
            "url": self.url,
            "relevance_score": self.relevance_score,
            "retrieved_at": self.retrieved_at,
        }


@dataclass
class ResearchReport:
    """Aggregated research output with synthesis."""
    report_id: str = field(default_factory=lambda: f"res_{uuid.uuid4().hex[:8]}")
    query: str = ""
    findings: List[ResearchResult] = field(default_factory=list)
    synthesis: str = ""
    sources_consulted: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "query": self.query,
            "synthesis": self.synthesis,
            "sources_consulted": self.sources_consulted,
            "findings_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
            "duration_ms": self.duration_ms,
        }


class ResearcherAgent:
    """
    Multi-source research agent that:
    1. Queries local search brain (zero-latency hot cache)
    2. Falls back to web search (SearXNG / DuckDuckGo)
    3. Deep-reads URLs via browser worker
    4. Synthesises findings into a concise report
    """

    MAX_WEB_RESULTS = 5
    MAX_LOCAL_RESULTS = 10

    def research(
        self,
        query: str,
        user_id: str = "ganesh",
        deep: bool = False,
        url: Optional[str] = None,
    ) -> ResearchReport:
        """
        Primary research entry point.

        Args:
            query: Research question or topic.
            user_id: User context for memory retrieval.
            deep: If True, also deep-reads top URL result.
            url: If provided, deep-reads this specific URL.

        Returns:
            ResearchReport with findings and synthesis.
        """
        start = time.time()
        report_id = f"res_{uuid.uuid4().hex[:8]}"
        logger.info(f"ResearcherAgent: researching '{query[:60]}' (report={report_id})")

        findings: List[ResearchResult] = []
        sources: List[str] = []

        # ── 1. Local memory search ────────────────────────────────────────────
        local = self._search_local(query, user_id)
        findings.extend(local)
        if local:
            sources.append("local_memory")

        # ── 2. Local corpus / document search ────────────────────────────────
        docs = self._search_documents(query)
        findings.extend(docs)
        if docs:
            sources.append("local_documents")

        # ── 3. Web search ────────────────────────────────────────────────────
        web = self._search_web(query)
        findings.extend(web)
        if web:
            sources.append("web_search")

        # ── 4. URL deep-read (optional) ───────────────────────────────────────
        if url:
            url_result = self._read_url(url)
            if url_result:
                findings.append(url_result)
                sources.append(f"url:{url}")
        elif deep and web:
            top_url = web[0].url
            if top_url:
                url_result = self._read_url(top_url)
                if url_result:
                    findings.append(url_result)
                    sources.append(f"url:{top_url}")

        # ── 5. Synthesise ─────────────────────────────────────────────────────
        synthesis = self._synthesise(query, findings)

        duration_ms = round((time.time() - start) * 1000, 2)
        logger.info(
            f"ResearcherAgent: report={report_id} findings={len(findings)} "
            f"sources={sources} duration={duration_ms}ms"
        )

        return ResearchReport(
            report_id=report_id,
            query=query,
            findings=findings,
            synthesis=synthesis,
            sources_consulted=sources,
            duration_ms=duration_ms,
        )

    # ── Search backends ───────────────────────────────────────────────────────

    def _search_local(self, query: str, user_id: str) -> List[ResearchResult]:
        try:
            from jarvis.memory.mem0_client import mem0_client
            results = mem0_client.search(query=query, user_id=user_id, limit=5)
            if isinstance(results, dict):
                results = results.get("results", [])
            return [
                ResearchResult(
                    source="mem0_memory",
                    title=f"Memory: {item.get('memory', '')[:60]}",
                    snippet=item.get("memory", item.get("text", "")),
                    relevance_score=item.get("score", 0.8),
                )
                for item in (results or [])
                if item
            ]
        except Exception as exc:
            logger.debug(f"_search_local: {exc}")
            return []

    def _search_documents(self, query: str) -> List[ResearchResult]:
        try:
            from jarvis.memory.document_rag import document_rag
            results = document_rag.search(query, top_k=5)
            return [
                ResearchResult(
                    source="local_documents",
                    title=r.get("title", r.get("filename", "Document")),
                    snippet=r.get("snippet", r.get("text", ""))[:500],
                    relevance_score=r.get("score", 0.7),
                )
                for r in (results or [])
            ]
        except Exception as exc:
            logger.debug(f"_search_documents: {exc}")
            return []

    def _search_web(self, query: str) -> List[ResearchResult]:
        try:
            from jarvis.browser.search_wrapper import search_wrapper
            results = search_wrapper.search(query, max_results=self.MAX_WEB_RESULTS)
            return [
                ResearchResult(
                    source="web_search",
                    title=r.get("title", "Web Result"),
                    snippet=r.get("snippet", r.get("description", ""))[:500],
                    url=r.get("url", r.get("href")),
                    relevance_score=0.6,
                )
                for r in (results or [])
            ]
        except Exception as exc:
            logger.debug(f"_search_web: {exc}")
            return []

    def _read_url(self, url: str) -> Optional[ResearchResult]:
        try:
            from jarvis.browser.url_reader import url_reader
            content = url_reader.read(url, max_chars=3000)
            if content:
                return ResearchResult(
                    source="url_reader",
                    title=f"URL: {url[:80]}",
                    snippet=content[:500],
                    url=url,
                    relevance_score=0.9,
                )
        except Exception as exc:
            logger.debug(f"_read_url: {exc}")
        return None

    # ── Synthesis ─────────────────────────────────────────────────────────────

    def _synthesise(self, query: str, findings: List[ResearchResult]) -> str:
        if not findings:
            return f"No relevant information found for: {query}"

        top = sorted(findings, key=lambda f: f.relevance_score, reverse=True)[:5]
        snippets = "\n\n".join(
            f"[{f.source}] {f.title}:\n{f.snippet}" for f in top
        )

        try:
            from jarvis.core.model_router import model_router, RoutingRequest
            prompt = (
                f"Synthesise these research findings into a concise, factual answer "
                f"for the query: '{query}'\n\nFindings:\n{snippets}"
            )
            req = RoutingRequest(
                task_id=f"synth_{uuid.uuid4().hex[:6]}",
                user_intent=prompt,
                sensitivity_level="low",
            )
            decision = model_router.route(req)
            result = model_router.execute_inference(decision=decision, prompt=prompt)
            content = (
                result.get("choices", [{}])[0].get("message", {}).get("content", "")
                if isinstance(result, dict) else str(result)
            )
            return content.strip() if content else snippets[:1000]
        except Exception as exc:
            logger.debug(f"_synthesise LLM failed: {exc}")
            # Fallback: concatenate top snippets
            return f"Research summary for '{query}':\n\n" + snippets[:1500]


# ── Singleton ─────────────────────────────────────────────────────────────────
researcher_agent = ResearcherAgent()

__all__ = ["ResearcherAgent", "ResearchReport", "ResearchResult", "researcher_agent"]
