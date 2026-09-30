"""
VectorStoreService: wraps Pinecone so the rest of the app never talks to
the Pinecone SDK directly. Swapping vector DBs later means rewriting only
this file.
"""
import time
from typing import List, Optional

from backend.config import settings
from backend.logger import logger

_pc = None
_index = None


def _get_index():
    global _pc, _index
    if _index is not None:
        return _index

    from pinecone import Pinecone, ServerlessSpec

    if not settings.PINECONE_API_KEY:
        raise RuntimeError("PINECONE_API_KEY is not set; cannot use the vector store.")

    _pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    spec = ServerlessSpec(cloud="aws", region=settings.PINECONE_ENV)

    existing = [i["name"] for i in _pc.list_indexes()]
    if settings.PINECONE_INDEX_NAME not in existing:
        _pc.create_index(
            name=settings.PINECONE_INDEX_NAME,
            dimension=settings.EMBEDDING_DIM,
            metric="dotproduct",
            spec=spec,
        )
        while not _pc.describe_index(settings.PINECONE_INDEX_NAME).status["ready"]:
            time.sleep(1)

    _index = _pc.Index(settings.PINECONE_INDEX_NAME)
    return _index


class VectorStoreService:
    def upsert(self, ids: List[str], vectors: List[List[float]], metadatas: List[dict]):
        index = _get_index()
        records = list(zip(ids, vectors, metadatas))
        if not records:
            return
        batch_size = 100
        for i in range(0, len(records), batch_size):
            index.upsert(vectors=records[i:i + batch_size])
        logger.info(f"Upserted {len(records)} vectors to Pinecone")

    def query(
        self,
        vector: List[float],
        top_k: int = 8,
        document_ids: Optional[List[str]] = None,
    ) -> list:
        index = _get_index()
        filter_ = {"document_id": {"$in": document_ids}} if document_ids else None
        res = index.query(
            vector=vector,
            top_k=top_k,
            include_metadata=True,
            filter=filter_,
        )
        return res.get("matches", [])

    def delete_document(self, document_id: str):
        index = _get_index()
        index.delete(filter={"document_id": {"$eq": document_id}})
        logger.info(f"Deleted vectors for document_id={document_id}")


vectorstore_service = VectorStoreService()
