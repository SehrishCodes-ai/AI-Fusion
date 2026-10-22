"""
DocuLens AI — Service smoke test script.
Run from the project root: python tests/smoke_test.py
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

import django
django.setup()

# ── Test 1: Imports ──────────────────────────────────────────────────────────
print("=" * 60)
print("TEST 1: Service module imports")
print("=" * 60)

from documents.models import Document, DocumentChunk
from documents.services.extraction import extract_text, _extract_txt
from documents.services.chunking import chunk_pages
from documents.services.vector_store import get_index_size

print("PASS: All service modules imported successfully")

# ── Test 2: TXT extraction ───────────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 2: TXT extraction")
print("=" * 60)

sample_path = Path(__file__).parent / 'sample_document.txt'
result = _extract_txt(sample_path)
assert len(result) == 1, f"Expected 1 page, got {len(result)}"
assert len(result[0]['text']) > 100, "Extracted text is too short"
print(f"PASS: Extracted {len(result[0]['text'])} characters from sample_document.txt")

# ── Test 3: Chunking ─────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 3: Text chunking")
print("=" * 60)

pages = result  # reuse extracted pages
chunks = chunk_pages(pages, chunk_size=500, overlap=80)
assert len(chunks) > 0, "No chunks produced"
print(f"PASS: {len(chunks)} chunks produced")
for c in chunks[:3]:
    print(f"  Chunk {c['chunk_index']}: {len(c['text'])} chars | Page: {c['page_number']}")

# ── Test 4: Vector store initialises ────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 4: FAISS vector store")
print("=" * 60)

size = get_index_size()
print(f"PASS: Vector store accessible, currently contains {size} vectors")

# ── Test 5: Model fields ─────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST 5: Django models")
print("=" * 60)

fields = [f.name for f in Document._meta.get_fields()]
assert 'display_name' in fields
assert 'status' in fields
assert 'chunk_count' in fields
print("PASS: Document model fields verified:", fields)

chunk_fields = [f.name for f in DocumentChunk._meta.get_fields()]
assert 'text' in chunk_fields
assert 'page_number' in chunk_fields
assert 'faiss_index_id' in chunk_fields
print("PASS: DocumentChunk model fields verified:", chunk_fields)

# ── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("ALL SMOKE TESTS PASSED")
print("=" * 60)
print("\nNext step: Add GEMINI_API_KEY to .env and test the full pipeline.")
