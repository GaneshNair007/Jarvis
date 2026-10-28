"""
JARVIS Memory Vault & Document Intelligence REST API Routes
Implements Part 7 Memory Vault endpoints:
  POST /memory/add
  POST /memory/search
  POST /memory/delete
  POST /memory/correction
  POST /documents/ingest
  POST /documents/query
  GET /memory
  GET /memory/storage
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from jarvis.memory.layers import memory_manager
from jarvis.memory.document_rag import document_rag
from jarvis.memory.correction_engine import correction_engine

router = APIRouter(tags=["Memory Vault"])

# Pydantic Schemas
class MemoryAddRequest(BaseModel):
    layer: str = Field(default="SEMANTIC", description="Cognitive layer (CAPTURE, RAW, EPISODIC, SEMANTIC, PROCEDURAL, WORKING, DIRECTIVE)")
    content: str = Field(..., description="Memory content to store")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Arbitrary JSON metadata")
    is_hypothesis: bool = Field(default=False, description="True if inferred pattern, False if verified fact")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence rating between 0.0 and 1.0")
    evidence_count: int = Field(default=1, ge=1, description="Number of independent observations supporting this")

class MemorySearchRequest(BaseModel):
    query: Optional[str] = Field(default=None, description="Substring or keyword match")
    layer: Optional[str] = Field(default=None, description="Optional layer filter")
    is_hypothesis: Optional[bool] = Field(default=None, description="Filter facts vs hypotheses")
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum confidence threshold")
    limit: int = Field(default=20, ge=1, le=100)

class MemoryDeleteRequest(BaseModel):
    node_id: str = Field(..., description="Unique ID of memory node to delete")

class CorrectionRequest(BaseModel):
    user_quote: str = Field(..., description="User's original statement or correction prompt")
    new_instruction: str = Field(..., description="The definitive standing instruction to adopt")
    scope: str = Field(default="always", description="'this_task', 'this_project', or 'always'")
    failure_id: Optional[str] = Field(default=None, description="Optional ID of failed task or action")
    old_behavior: Optional[str] = Field(default=None, description="Description of the previous erroneous behavior")

class DocumentIngestRequest(BaseModel):
    file_path: Optional[str] = Field(default=None, description="Absolute local path to file (PDF, TXT, MD)")
    content: Optional[str] = Field(default=None, description="Raw text content to ingest if not providing a file path")
    title: Optional[str] = Field(default=None, description="Title for raw text content")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata tags")

class DocumentQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language question or search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of cited chunks to return")
    doc_id: Optional[str] = Field(default=None, description="Optional scope to a single document")

# Endpoints
@router.post("/memory/add")
def add_memory(req: MemoryAddRequest) -> Dict[str, Any]:
    """Stores an explicit fact or inferred hypothesis in the private memory vault."""
    try:
        node_id = memory_manager.store_memory(
            layer=req.layer,
            content=req.content,
            metadata=req.metadata,
            is_hypothesis=req.is_hypothesis,
            confidence=req.confidence,
            evidence_count=req.evidence_count
        )
        return {
            "status": "STORED",
            "node_id": node_id,
            "layer": req.layer.upper(),
            "is_hypothesis": req.is_hypothesis,
            "confidence": req.confidence
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/memory/search")
def search_memory(req: MemorySearchRequest) -> Dict[str, Any]:
    """Searches memory nodes with confidence, layer, and keyword filtering."""
    results = memory_manager.recall(
        layer=req.layer,
        query=req.query,
        is_hypothesis=req.is_hypothesis,
        min_confidence=req.min_confidence,
        limit=req.limit
    )
    return {"results": results, "count": len(results)}

@router.post("/memory/delete")
def delete_memory(req: MemoryDeleteRequest) -> Dict[str, Any]:
    """Deletes a memory node by ID."""
    deleted = memory_manager.delete_memory(req.node_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Memory node '{req.node_id}' not found.")
    return {"status": "DELETED", "node_id": req.node_id}

@router.post("/memory/correction")
def record_correction(req: CorrectionRequest) -> Dict[str, Any]:
    """Records a user correction and promotes it into directive/procedural memory."""
    try:
        return correction_engine.record_correction(
            user_quote=req.user_quote,
            new_instruction=req.new_instruction,
            scope=req.scope,
            failure_id=req.failure_id,
            old_behavior=req.old_behavior
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/documents/ingest")
def ingest_document(req: DocumentIngestRequest) -> Dict[str, Any]:
    """Ingests a file or raw text into the document intelligence RAG system."""
    if req.file_path:
        try:
            return document_rag.ingest_file(req.file_path, metadata=req.metadata)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
    elif req.content and req.title:
        return document_rag.ingest_text(req.content, title=req.title, metadata=req.metadata)
    else:
        raise HTTPException(status_code=400, detail="Must provide either 'file_path' or both 'content' and 'title'.")

@router.post("/documents/query")
def query_documents(req: DocumentQueryRequest) -> Dict[str, Any]:
    """Queries indexed documents and returns cited excerpt passages with exact file and page provenance."""
    return document_rag.query_documents(
        query=req.query,
        top_k=req.top_k,
        doc_id=req.doc_id
    )

@router.get("/memory")
def list_memory(
    layer: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100)
) -> Dict[str, Any]:
    """Lists memory nodes filtered by layer and query."""
    results = memory_manager.recall(layer=layer, query=query, limit=limit)
    return {"results": results, "count": len(results)}

@router.get("/memory/storage")
def get_memory_storage() -> Dict[str, Any]:
    """Returns database size, layer breakdowns, and vault storage telemetry."""
    return memory_manager.get_storage_stats()
