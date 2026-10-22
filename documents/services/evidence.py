"""
Document processing orchestrator — coordinates extraction → chunking → embedding → indexing.
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def process_document(document_id: str):
    """
    Full pipeline: extract → chunk → embed → index.
    Updates Document model status fields.
    Must be called after the file has been saved to disk.
    """
    from documents.models import Document, DocumentChunk
    from .extraction import extract_text
    from .chunking import chunk_pages
    from .embeddings import generate_embeddings
    from .vector_store import add_embeddings

    try:
        doc = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        logger.error("Document %s not found.", document_id)
        return

    doc.status = Document.Status.PROCESSING
    doc.save(update_fields=['status'])

    try:
        # 1. Extract text
        file_path = doc.file.path
        pages = extract_text(file_path, doc.file_type)
        page_count = len(pages)
        char_count = sum(len(p['text']) for p in pages)
        logger.info("Extracted %d pages, %d chars from %s", page_count, char_count, doc.display_name)

        # 2. Chunk
        chunks_data = chunk_pages(
            pages,
            chunk_size=settings.RAG_CHUNK_SIZE,
            overlap=settings.RAG_CHUNK_OVERLAP,
        )
        if not chunks_data:
            raise ValueError("Text chunking produced no chunks.")
        logger.info("Produced %d chunks.", len(chunks_data))

        # 3. Embed
        texts = [c['text'] for c in chunks_data]
        embeddings = generate_embeddings(texts)
        if len(embeddings) != len(chunks_data):
            raise ValueError(
                f"Embedding count mismatch: {len(embeddings)} != {len(chunks_data)}"
            )

        # 4. Save chunks to DB first (to get UUIDs)
        # Clear existing chunks in case of re-processing
        DocumentChunk.objects.filter(document=doc).delete()

        db_chunks = []
        for cd in chunks_data:
            db_chunks.append(DocumentChunk(
                document=doc,
                chunk_index=cd['chunk_index'],
                text=cd['text'],
                page_number=cd.get('page_number'),
                char_start=cd.get('char_start', 0),
            ))
        DocumentChunk.objects.bulk_create(db_chunks)

        # Re-fetch with UUIDs
        saved_chunks = list(
            DocumentChunk.objects.filter(document=doc).order_by('chunk_index')
        )
        chunk_uuids = [str(c.id) for c in saved_chunks]

        # 5. Index in FAISS
        faiss_ids = add_embeddings(chunk_uuids, embeddings)

        # 6. Store faiss_index_id on each chunk
        for chunk, fid in zip(saved_chunks, faiss_ids):
            chunk.faiss_index_id = fid
        DocumentChunk.objects.bulk_update(saved_chunks, ['faiss_index_id'])

        # 7. Update document status
        doc.status = Document.Status.INDEXED
        doc.page_count = page_count
        doc.char_count = char_count
        doc.chunk_count = len(chunks_data)
        doc.error_message = ''
        doc.save(update_fields=['status', 'page_count', 'char_count', 'chunk_count', 'error_message'])
        logger.info("Document %s indexed successfully.", doc.display_name)

    except Exception as e:
        logger.error("Processing failed for %s: %s", document_id, e, exc_info=True)
        doc.status = Document.Status.ERROR
        doc.error_message = str(e)[:500]
        doc.save(update_fields=['status', 'error_message'])
