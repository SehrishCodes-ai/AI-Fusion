"""
Embedding generation service using Google Gemini.
"""
import logging
import time
from django.conf import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. "
                "Add it to your .env file or environment variables."
            )
        from google import genai
        _client = genai.Client(api_key=api_key)
    return _client


def generate_embeddings(texts: list[str], retries: int = 3) -> list[list[float]]:
    """
    Generate embeddings for a list of text strings.
    Uses gemini-embedding-001 (text-only model).
    Returns a list of float vectors, one per input text.
    Raises RuntimeError on persistent API failure.
    """
    if not texts:
        return []

    client = _get_client()
    model = settings.RAG_EMBEDDING_MODEL
    embeddings = []

    # Batch in groups of 100 (API limit)
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        for attempt in range(retries):
            try:
                response = client.models.embed_content(
                    model=model,
                    contents=batch,
                )
                # response.embeddings is a list of ContentEmbedding objects
                batch_vecs = [emb.values for emb in response.embeddings]
                embeddings.extend(batch_vecs)
                break
            except Exception as e:
                logger.warning("Embedding attempt %d failed: %s", attempt + 1, e)
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # exponential back-off
                else:
                    raise RuntimeError(
                        f"Embedding generation failed after {retries} attempts: {e}"
                    )

    return embeddings


def generate_single_embedding(text: str) -> list[float]:
    """Generate an embedding for a single query string."""
    results = generate_embeddings([text])
    if not results:
        raise RuntimeError("No embedding returned for the query.")
    return results[0]
