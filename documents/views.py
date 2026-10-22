"""
Django views for DocuLens AI.
"""
import json
import logging
import mimetypes
import os
import uuid

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_POST, require_GET

from .forms import DocumentUploadForm
from .models import Document, DocumentChunk
from .services.evidence import process_document
from .services.retrieval import retrieve_chunks, check_evidence_sufficiency
from .services.generation import generate_answer

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'pdf', 'txt'}
MAX_QUESTION_LENGTH = 1000


def _get_session_key(request):
    """Ensure the session has a key and return it."""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _get_session_documents(request):
    """Return documents belonging to the current session."""
    session_key = _get_session_key(request)
    return Document.objects.filter(session_key=session_key).order_by('-upload_timestamp')


# ──────────────────────────────────────────────────────────────────────────────
# Main workspace view
# ──────────────────────────────────────────────────────────────────────────────

def index(request):
    """Main workspace: shows uploaded docs and Q&A interface."""
    documents = _get_session_documents(request)
    form = DocumentUploadForm()
    return render(request, 'documents/index.html', {
        'documents': documents,
        'form': form,
        'has_indexed_docs': documents.filter(status=Document.Status.INDEXED).exists(),
    })


# ──────────────────────────────────────────────────────────────────────────────
# Upload view
# ──────────────────────────────────────────────────────────────────────────────

@require_POST
def upload_document(request):
    """Handle document upload, validate, and trigger processing."""
    form = DocumentUploadForm(request.POST, request.FILES)

    if not form.is_valid():
        errors = '; '.join(
            f"{field}: {', '.join(errs)}"
            for field, errs in form.errors.items()
        )
        return JsonResponse({'success': False, 'error': errors}, status=400)

    uploaded_file = request.FILES['file']
    file_name = uploaded_file.name
    ext = _get_extension(file_name)

    if ext not in ALLOWED_EXTENSIONS:
        return JsonResponse(
            {'success': False, 'error': f'Unsupported file type ".{ext}". Please upload a PDF or TXT file.'},
            status=400
        )

    # Size check
    max_size = settings.MAX_UPLOAD_SIZE
    if uploaded_file.size > max_size:
        mb = max_size // (1024 * 1024)
        return JsonResponse(
            {'success': False, 'error': f'File is too large. Maximum allowed size is {mb} MB.'},
            status=400
        )

    if uploaded_file.size == 0:
        return JsonResponse(
            {'success': False, 'error': 'The uploaded file is empty.'},
            status=400
        )

    session_key = _get_session_key(request)

    # Create document record
    safe_name = _safe_display_name(file_name)
    doc = Document(
        display_name=safe_name,
        file_type=ext,
        status=Document.Status.PENDING,
        session_key=session_key,
    )
    doc.file = uploaded_file
    doc.save()

    # Process synchronously (hackathon MVP — switch to Celery for production)
    try:
        process_document(str(doc.id))
        doc.refresh_from_db()
    except Exception as e:
        logger.error("Unexpected error during processing: %s", e)
        doc.status = Document.Status.ERROR
        doc.error_message = "An unexpected error occurred during processing."
        doc.save(update_fields=['status', 'error_message'])

    return JsonResponse({
        'success': doc.status == Document.Status.INDEXED,
        'document': _doc_to_dict(doc),
        'error': doc.error_message if doc.status == Document.Status.ERROR else None,
    })


# ──────────────────────────────────────────────────────────────────────────────
# Delete view
# ──────────────────────────────────────────────────────────────────────────────

@require_POST
def delete_document(request, doc_id):
    """Delete a document, its chunks, and remove its vectors from the index."""
    session_key = _get_session_key(request)

    try:
        doc = Document.objects.get(id=doc_id, session_key=session_key)
    except Document.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Document not found.'}, status=404)

    # Remove FAISS vectors
    faiss_ids = list(
        DocumentChunk.objects.filter(document=doc).values_list('faiss_index_id', flat=True)
    )
    faiss_ids = [fid for fid in faiss_ids if fid >= 0]

    if faiss_ids:
        try:
            from .services.vector_store import remove_document_vectors
            remove_document_vectors(faiss_ids)
        except Exception as e:
            logger.warning("FAISS removal partial failure: %s", e)

    # Delete file from disk
    try:
        if doc.file and os.path.isfile(doc.file.path):
            os.remove(doc.file.path)
    except Exception as e:
        logger.warning("Could not delete file: %s", e)

    doc.delete()  # cascades to chunks

    return JsonResponse({'success': True, 'document_id': str(doc_id)})


# ──────────────────────────────────────────────────────────────────────────────
# Question-answering view
# ──────────────────────────────────────────────────────────────────────────────

@require_POST
def ask_question(request):
    """Receive a question, run RAG, return answer + sources."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid request body.'}, status=400)

    question = body.get('question', '').strip()
    if not question:
        return JsonResponse({'success': False, 'error': 'Please enter a question.'}, status=400)

    if len(question) > MAX_QUESTION_LENGTH:
        return JsonResponse(
            {'success': False, 'error': f'Question is too long (max {MAX_QUESTION_LENGTH} characters).'},
            status=400
        )

    session_key = _get_session_key(request)
    session_docs = list(
        Document.objects.filter(
            session_key=session_key,
            status=Document.Status.INDEXED
        ).values_list('id', flat=True)
    )
    document_ids = [str(d) for d in session_docs]

    if not document_ids:
        return JsonResponse({
            'success': True,
            'answer': (
                "No indexed documents found in your session. "
                "Please upload a PDF or TXT document first."
            ),
            'evidence_status': 'unsupported',
            'sources': [],
            'error': None,
        })

    # Step 1: Retrieve relevant chunks
    try:
        chunks = retrieve_chunks(
            question=question,
            document_ids=document_ids,
            top_k=settings.RAG_TOP_K,
        )
    except RuntimeError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=503)
    except Exception as e:
        logger.error("Retrieval error: %s", e)
        return JsonResponse({'success': False, 'error': 'Retrieval service temporarily unavailable.'}, status=503)

    # Step 2: Check evidence sufficiency
    evidence_status = check_evidence_sufficiency(chunks)

    # Step 3: Generate grounded answer
    result = generate_answer(question, chunks, evidence_status)

    if result.get('error') and not result.get('answer'):
        return JsonResponse({'success': False, 'error': result['error']}, status=503)

    # Step 4: Format sources
    sources = []
    for chunk in chunks:
        sources.append({
            'document_name': chunk['document_name'],
            'page_number': chunk.get('page_number'),
            'text': chunk['text'][:500],   # truncate long passages for display
            'relevance_label': chunk.get('relevance_label', 'moderate'),
            'chunk_index': chunk.get('chunk_index'),
        })

    return JsonResponse({
        'success': True,
        'answer': result['answer'],
        'evidence_status': result['evidence_status'],
        'model_used': result.get('model_used'),
        'sources': sources,
        'error': result.get('error'),
    })


# ──────────────────────────────────────────────────────────────────────────────
# Document status poll
# ──────────────────────────────────────────────────────────────────────────────

@require_GET
def document_status(request, doc_id):
    session_key = _get_session_key(request)
    try:
        doc = Document.objects.get(id=doc_id, session_key=session_key)
    except Document.DoesNotExist:
        return JsonResponse({'error': 'Not found.'}, status=404)
    return JsonResponse(_doc_to_dict(doc))


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _get_extension(filename: str) -> str:
    """Extract lowercase extension without dot."""
    _, ext = os.path.splitext(filename)
    return ext.lstrip('.').lower()


def _safe_display_name(filename: str) -> str:
    """Return a safe display name for the file."""
    base = os.path.basename(filename)
    # Remove path traversal characters
    return base.replace('..', '').strip()[:200] or 'Unnamed Document'


def _doc_to_dict(doc: Document) -> dict:
    return {
        'id': str(doc.id),
        'display_name': doc.display_name,
        'file_type': doc.file_type,
        'status': doc.status,
        'status_label': doc.get_status_display(),
        'upload_timestamp': doc.upload_timestamp.isoformat(),
        'page_count': doc.page_count,
        'char_count': doc.char_count,
        'chunk_count': doc.chunk_count,
        'error_message': doc.error_message,
    }
