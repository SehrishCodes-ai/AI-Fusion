"""
Semantic retrieval service — question → relevant chunks.
"""
import logging
from django.conf import settings

from .embeddings import generate_single_embedding
from .vector_store import search
from documents.models import DocumentChunk, Document

logger = logging.getLogger(__name__)


def retrieve_chunks(
    question: str,
    document_ids: list[str] | None = None,
    top_k: int = None,
    distance_threshold: float = None,
) -> list[dict]:
    """
    Embed the question, search the vector store, and return matching chunks.

    Args:
        question: Natural language question.
        document_ids: Optional list of document UUID strings to restrict search.
        top_k: Number of nearest neighbours to retrieve.
        distance_threshold: Maximum L2 distance to accept (lower = more similar).

    Returns:
        List of result dicts with keys:
          chunk_uuid, text, page_number, chunk_index,
          document_id, document_name, distance, relevance_label
    """
    if top_k is None:
        top_k = settings.RAG_TOP_K
    if distance_threshold is None:
        distance_threshold = settings.RAG_SIMILARITY_THRESHOLD

    # Step 1: Embed the question
    try:
        query_embedding = generate_single_embedding(question)
    except Exception as e:
        logger.error("Failed to embed question: %s", e)
        raise RuntimeError(f"Could not generate question embedding: {e}")

    # Step 2: Search vector index
    raw_results = search(query_embedding, top_k=top_k * 2)  # over-fetch, then filter
    if not raw_results:
        return []

    # Step 3: Load matching chunks from DB
    chunk_uuid_to_result = {r['chunk_uuid']: r for r in raw_results}
    chunk_uuids = list(chunk_uuid_to_result.keys())

    try:
        chunks = DocumentChunk.objects.select_related('document').filter(
            id__in=chunk_uuids
        )
    except Exception as e:
        logger.error("DB lookup failed: %s", e)
        return []

    # Step 4: Filter by document scope and distance threshold
    results = []
    for chunk in chunks:
        raw = chunk_uuid_to_result.get(str(chunk.id))
        if raw is None:
            continue

        # Restrict to requested documents if specified
        if document_ids and str(chunk.document_id) not in document_ids:
            continue

        # Only keep results with document status = 'indexed'
        if chunk.document.status != Document.Status.INDEXED:
            continue

        distance = raw['distance']

        # For L2 distance: smaller = more similar.
        # Normalised relevance: 1 / (1 + distance)
        relevance_score = 1.0 / (1.0 + distance)

        results.append({
            'chunk_uuid': str(chunk.id),
            'text': chunk.text,
            'page_number': chunk.page_number,
            'chunk_index': chunk.chunk_index,
            'document_id': str(chunk.document_id),
            'document_name': chunk.document.display_name,
            'distance': distance,
            'relevance_score': relevance_score,
            'relevance_label': _label(relevance_score),
        })

    # Sort by ascending distance (best match first)
    results.sort(key=lambda x: x['distance'])
    return results[:top_k]


def _label(score: float) -> str:
    """Map relevance score to a human-readable label."""
    if score >= 0.5:
        return 'strong'
    elif score >= 0.25:
        return 'moderate'
    else:
        return 'weak'


def check_evidence_sufficiency(chunks: list[dict]) -> str:
    """
    Classify the retrieved evidence quality.
    Returns: 'supported', 'partial', or 'unsupported'
    """
    if not chunks:
        return 'unsupported'

    strong = [c for c in chunks if c['relevance_label'] == 'strong']
    moderate = [c for c in chunks if c['relevance_label'] == 'moderate']

    if strong:
        return 'supported'
    elif moderate:
        return 'partial'
    else:
        return 'unsupported'
