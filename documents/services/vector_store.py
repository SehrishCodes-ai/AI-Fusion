"""
FAISS vector store — persistent index with metadata mapping.

The index is stored as two files in settings.VECTOR_STORE_DIR:
  - doculens.index  : FAISS flat L2 index
  - doculens_meta.pkl : pickle dict mapping FAISS integer id → chunk UUID

We use a simple flat index (IndexFlatL2) suitable for small-to-medium collections.
For production use IndexIVFFlat or HNSW.
"""
import os
import pickle
import logging
import threading
from pathlib import Path

import numpy as np
import faiss
from django.conf import settings

logger = logging.getLogger(__name__)

_INDEX_FILENAME = 'doculens.index'
_META_FILENAME = 'doculens_meta.pkl'

_lock = threading.Lock()
_index = None          # faiss index
_meta = {}             # {faiss_int_id: chunk_uuid_str}
_next_id = 0           # monotonically increasing FAISS entry id
_dim = None            # embedding dimension


def _store_path(filename: str) -> Path:
    path = Path(settings.VECTOR_STORE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path / filename


def _load_or_create(dimension: int):
    """Load the existing index or create a new one."""
    global _index, _meta, _next_id, _dim
    index_path = _store_path(_INDEX_FILENAME)
    meta_path = _store_path(_META_FILENAME)

    if index_path.exists() and meta_path.exists():
        try:
            _index = faiss.read_index(str(index_path))
            with open(meta_path, 'rb') as f:
                saved = pickle.load(f)
                _meta = saved.get('meta', {})
                _next_id = saved.get('next_id', _index.ntotal)
                _dim = saved.get('dim', dimension)
            logger.info("Loaded FAISS index with %d vectors.", _index.ntotal)
            return
        except Exception as e:
            logger.warning("Could not load existing index (%s); creating fresh.", e)

    _index = faiss.IndexFlatL2(dimension)
    _meta = {}
    _next_id = 0
    _dim = dimension
    logger.info("Created new FAISS index (dim=%d).", dimension)


def _save():
    """Persist the index and metadata to disk."""
    faiss.write_index(_index, str(_store_path(_INDEX_FILENAME)))
    with open(_store_path(_META_FILENAME), 'wb') as f:
        pickle.dump({'meta': _meta, 'next_id': _next_id, 'dim': _dim}, f)


def add_embeddings(chunk_uuids: list[str], embeddings: list[list[float]]):
    """
    Add a batch of embeddings to the FAISS index.
    chunk_uuids must be string UUIDs matching DocumentChunk.id values.
    Returns a list of FAISS integer ids assigned to each chunk.
    """
    global _index, _meta, _next_id, _dim

    if not embeddings:
        return []

    vectors = np.array(embeddings, dtype='float32')
    if vectors.ndim != 2:
        raise ValueError("Embeddings must be a 2-D array.")

    dimension = vectors.shape[1]

    with _lock:
        if _index is None:
            _load_or_create(dimension)
        elif dimension != _dim:
            raise ValueError(
                f"Dimension mismatch: index has {_dim}, new embeddings have {dimension}."
            )

        assigned_ids = list(range(_next_id, _next_id + len(embeddings)))
        ids_array = np.array(assigned_ids, dtype='int64')

        # Use IndexIDMap to track explicit integer IDs
        if not isinstance(_index, faiss.IndexIDMap):
            id_index = faiss.IndexIDMap(_index)
            id_index.add_with_ids(vectors, ids_array)
            _index = id_index
        else:
            _index.add_with_ids(vectors, ids_array)

        for fid, uuid_str in zip(assigned_ids, chunk_uuids):
            _meta[fid] = uuid_str

        _next_id += len(embeddings)
        _save()

    return assigned_ids


def search(query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """
    Search the index for the top_k nearest neighbours.
    Returns list of dicts: {'faiss_id': int, 'chunk_uuid': str, 'distance': float}
    """
    global _index

    with _lock:
        if _index is None or _index.ntotal == 0:
            return []

        query = np.array([query_embedding], dtype='float32')
        k = min(top_k, _index.ntotal)
        distances, indices = _index.search(query, k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0:
            continue
        chunk_uuid = _meta.get(int(idx))
        if chunk_uuid:
            results.append({
                'faiss_id': int(idx),
                'chunk_uuid': chunk_uuid,
                'distance': float(dist),
            })
    return results


def remove_document_vectors(faiss_ids: list[int]):
    """
    Remove specific vectors from the index by their FAISS integer ids.
    Uses reconstruction + rebuild strategy since IndexFlatL2 doesn't support removal.
    """
    global _index, _meta, _next_id, _dim

    if not faiss_ids:
        return

    ids_to_remove = set(faiss_ids)

    with _lock:
        if _index is None or _index.ntotal == 0:
            return

        # Rebuild without removed ids
        remaining_ids = [fid for fid in _meta if fid not in ids_to_remove]
        if not remaining_ids:
            # All vectors removed — reset
            _index = faiss.IndexFlatL2(_dim) if _dim else faiss.IndexFlatL2(768)
            _meta = {}
            _next_id = 0
            _save()
            return

        # Reconstruct all remaining vectors
        inner = _index.index if isinstance(_index, faiss.IndexIDMap) else _index
        vectors = []
        valid_ids = []
        valid_uuids = []
        for fid in remaining_ids:
            try:
                vec = inner.reconstruct(fid)
                vectors.append(vec)
                valid_ids.append(fid)
                valid_uuids.append(_meta[fid])
            except Exception:
                pass  # silently skip if reconstruction fails

        if not vectors:
            _index = faiss.IndexFlatL2(_dim)
            _meta = {}
            _next_id = 0
        else:
            new_flat = faiss.IndexFlatL2(_dim)
            new_index = faiss.IndexIDMap(new_flat)
            vecs = np.array(vectors, dtype='float32')
            ids = np.array(valid_ids, dtype='int64')
            new_index.add_with_ids(vecs, ids)
            _index = new_index
            _meta = {fid: uuid for fid, uuid in zip(valid_ids, valid_uuids)}
            # Remove deleted ids from meta
            for fid in ids_to_remove:
                _meta.pop(fid, None)

        _save()


def get_index_size() -> int:
    """Return the total number of indexed vectors."""
    with _lock:
        if _index is None:
            _load_or_create(768)  # attempt load
        return _index.ntotal if _index else 0


def initialize():
    """Eagerly load the index at startup."""
    global _index
    with _lock:
        if _index is None:
            try:
                _load_or_create(768)
            except Exception as e:
                logger.warning("Could not pre-load FAISS index: %s", e)
