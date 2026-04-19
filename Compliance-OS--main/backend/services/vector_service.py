"""
ChromaDB vector database service for RAG (Retrieval Augmented Generation).
Provides semantic search over regulations, reports, and documents.
"""

import datetime
from typing import Optional
from backend.config import settings
from backend.utils.logger import logger

_chroma_client = None
_collections = {}


def _get_client():
    """Lazy-initialize ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            _chroma_client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIR,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            logger.info(f"ChromaDB initialized at {settings.CHROMA_PERSIST_DIR}")
        except ImportError:
            logger.error("chromadb package not installed — vector features disabled")
            return None
        except Exception as e:
            logger.error(f"ChromaDB initialization failed: {e}")
            return None
    return _chroma_client


def _get_collection(name: str):
    """Get or create a named collection."""
    full_name = f"{settings.CHROMA_COLLECTION_PREFIX}_{name}"
    if full_name not in _collections:
        client = _get_client()
        if not client:
            return None
        _collections[full_name] = client.get_or_create_collection(
            name=full_name,
            metadata={"hnsw:space": "cosine"},
        )
    return _collections[full_name]


async def embed_document(
    text: str,
    doc_id: str,
    collection_name: str = "regulations",
    metadata: Optional[dict] = None,
) -> bool:
    """Embed a document into the vector store."""
    collection = _get_collection(collection_name)
    if not collection:
        return False

    try:
        # Chunk text into segments (max ~500 chars each for better retrieval)
        chunks = _chunk_text(text, max_chars=500)
        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        base_meta = metadata or {}
        metadatas = []
        for i, chunk in enumerate(chunks):
            meta = {**base_meta, "chunk_index": i, "total_chunks": len(chunks)}
            # ChromaDB metadata values must be str, int, float, or bool
            clean_meta = {k: str(v) if not isinstance(v, (int, float, bool)) else v for k, v in meta.items()}
            metadatas.append(clean_meta)

        collection.upsert(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
        )
        logger.info(f"Embedded {len(chunks)} chunks into '{collection_name}' for doc {doc_id}")
        return True
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return False


async def search_similar(
    query: str,
    collection_name: str = "regulations",
    n_results: int = 5,
    where_filter: Optional[dict] = None,
) -> list[dict]:
    """Semantic search across stored documents."""
    collection = _get_collection(collection_name)
    if not collection:
        return []

    try:
        kwargs = {
            "query_texts": [query],
            "n_results": n_results,
        }
        if where_filter:
            kwargs["where"] = where_filter

        results = collection.query(**kwargs)

        formatted = []
        for i in range(len(results["documents"][0])):
            formatted.append({
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else None,
                "id": results["ids"][0][i],
            })
        return formatted
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []


async def ask_with_context(
    question: str,
    collection_name: str = "regulations",
    n_context: int = 3,
) -> dict:
    """RAG — retrieves relevant context and synthesizes an answer."""
    # Step 1: Retrieve relevant chunks
    context_docs = await search_similar(question, collection_name, n_results=n_context)
    context_text = "\n\n---\n\n".join([doc["text"] for doc in context_docs])

    if not context_text:
        return {
            "answer": "No relevant documents found in the knowledge base. Please upload regulatory documents first.",
            "sources": [],
        }

    # Step 2: Generate answer using AI engine
    from backend.services.ai_engine import _groq_client, _call_groq_sync
    if _groq_client:
        system_prompt = (
            "You are ComplianceOS, a regulatory intelligence AI. Answer the user's question based ONLY on the provided context. "
            "If the context doesn't contain enough information, say so. Be concise and professional."
        )
        user_prompt = f"CONTEXT:\n{context_text}\n\nQUESTION:\n{question}"
        answer = _call_groq_sync(system_prompt, user_prompt, max_tokens=500)
        if answer:
            try:
                import json
                parsed = json.loads(answer)
                answer = parsed.get("answer", answer)
            except (json.JSONDecodeError, TypeError):
                pass
    else:
        answer = f"Based on {len(context_docs)} matching regulatory passages, the query relates to compliance obligations. Review the source documents for detailed guidance."

    return {
        "answer": answer,
        "sources": [{"id": d["id"], "snippet": d["text"][:200]} for d in context_docs],
        "context_count": len(context_docs),
    }


def get_collection_stats(collection_name: str = "regulations") -> dict:
    """Return stats about a collection."""
    collection = _get_collection(collection_name)
    if not collection:
        return {"status": "unavailable", "count": 0}
    return {
        "status": "active",
        "count": collection.count(),
        "name": collection.name,
    }


def _chunk_text(text: str, max_chars: int = 500) -> list[str]:
    """Split text into overlapping chunks for better embedding quality."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    sentences = text.replace("\n", " ").split(". ")
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            # 20% overlap
            overlap_point = max(0, len(current_chunk) - max_chars // 5)
            current_chunk = current_chunk[overlap_point:] + sentence + ". "
        else:
            current_chunk += sentence + ". "

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks or [text[:max_chars]]
