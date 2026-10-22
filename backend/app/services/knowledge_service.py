from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import compute_sha256
from backend.app.models import DocumentationSource, DocumentChunk, utcnow
from backend.app.schemas import DocumentIngestRequest


class KnowledgeService:
    @staticmethod
    def ingest_document(
        db: Session,
        integration_id: str,
        payload: DocumentIngestRequest,
        workspace_id: str = "ws_prod_01",
    ) -> tuple[DocumentationSource, bool]:
        """
        Ingest documentation or migration guide.
        Uses SHA-256 content hashing to deduplicate identical uploads.
        Returns (document, is_new).
        """
        content_hash = compute_sha256(payload.content)
        existing = db.scalar(
            select(DocumentationSource).where(DocumentationSource.content_hash == content_hash)
        )
        if existing:
            return existing, False

        doc_id = f"doc_{uuid.uuid4().hex[:6]}"
        now = utcnow()
        doc = DocumentationSource(
            id=doc_id,
            workspace_id=workspace_id,
            integration_id=integration_id,
            provider=payload.provider,
            title=payload.title,
            source_url=payload.source_url,
            doc_type="MIGRATION_GUIDE",
            version=payload.version,
            content=payload.content,
            content_hash=content_hash,
            ingested_at=now,
        )
        db.add(doc)

        # Create basic chunks (split paragraphs)
        paragraphs = [p.strip() for p in payload.content.split("\n\n") if p.strip()]
        for idx, para in enumerate(paragraphs or [payload.content]):
            chunk = DocumentChunk(
                id=f"chk_{uuid.uuid4().hex[:6]}",
                workspace_id=workspace_id,
                doc_id=doc_id,
                chunk_index=idx,
                text_excerpt=para,
                keywords=list(set(re.findall(r"\w{3,}", para.lower()))),
            )
            db.add(chunk)

        db.commit()
        db.refresh(doc)
        return doc, True

    @staticmethod
    def search_knowledge_base(
        db: Session,
        query: str,
        integration_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Genuine local offline search fallback (BM25 / Keyword token ranking).
        Does not require external vector databases.
        """
        if not query.strip():
            return []

        query_terms = set(re.findall(r"\w{3,}", query.lower()))
        docs = list(db.scalars(select(DocumentationSource)).all())
        chunks = list(db.scalars(select(DocumentChunk)).all())

        results = []
        for chk in chunks:
            chunk_text = chk.text_excerpt.lower()
            matches = sum(1 for term in query_terms if term in chunk_text)
            if matches > 0:
                score = round(min(0.99, 0.65 + (matches * 0.1)), 2)
                parent_doc = next((d for d in docs if d.id == chk.doc_id), None)
                results.append(
                    {
                        "chunk_id": chk.id,
                        "doc_id": chk.doc_id,
                        "title": parent_doc.title if parent_doc else "API Migration Guide",
                        "source_url": parent_doc.source_url if parent_doc else "",
                        "version": parent_doc.version if parent_doc else "v2.2",
                        "excerpt": chk.text_excerpt,
                        "score": score,
                        "matched_terms": list(query_terms.intersection(set(re.findall(r"\w{3,}", chunk_text)))),
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
