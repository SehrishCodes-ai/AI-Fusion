"""
Verification test for GEMINI_API_KEY loading and live Gemini API check.
DO NOT print or expose the API key or its characters.
"""
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load django settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()

from django.conf import settings
from google import genai
from google.genai import types

def test_api():
    key = settings.GEMINI_API_KEY
    if not key or key == 'your_gemini_api_key_here' or key == 'PASTE_YOUR_KEY_HERE':
        print("FAIL: GEMINI_API_KEY is not loaded or still contains placeholder.")
        sys.exit(1)
    
    print(f"SUCCESS: GEMINI_API_KEY loaded successfully (length: {len(key)} chars, not placeholder).")
    
    # Test 1: Embeddings
    print("Testing Gemini embedding generation (gemini-embedding-001)...")
    try:
        client = genai.Client(api_key=key)
        emb_resp = client.models.embed_content(
            model=settings.RAG_EMBEDDING_MODEL,
            contents="Document intelligence and RAG test query",
        )
        # Verify embedding dimension
        if hasattr(emb_resp, 'embedding') and emb_resp.embedding:
            dim = len(emb_resp.embedding.values)
        elif hasattr(emb_resp, 'embeddings') and emb_resp.embeddings:
            dim = len(emb_resp.embeddings[0].values)
        else:
            dim = "unknown"
        print(f"SUCCESS: Embeddings functional! Dimension: {dim}")
    except Exception as e:
        print(f"FAIL: Embedding API error: {e}")
        sys.exit(1)

    # Test 2: Text Generation
    print(f"Testing Gemini generation ({settings.RAG_GENERATION_MODEL})...")
    try:
        gen_resp = client.models.generate_content(
            model=settings.RAG_GENERATION_MODEL,
            contents="Say 'DocuLens AI connection verified' in exactly 4 words.",
        )
        response_text = gen_resp.text.strip() if gen_resp.text else ""
        print(f"SUCCESS: Generation functional! Model response: \"{response_text}\"")
    except Exception as e:
        print(f"FAIL: Generative model API error: {e}")
        sys.exit(1)

    print("\nALL GEMINI INTEGRATION TESTS PASSED PERFECTLY!")

if __name__ == '__main__':
    test_api()
