"""
Query the Gemini API for models available to the current key that support generateContent.
Then test the verified IDs and determine the best primary and fallback models.

Security and Privacy Rules:
1. Never print raw exception messages, tracebacks, or server response bodies.
   Print only safe high-level categories (Authentication, Quota/Rate Limit, Model Unavailable, Network Error, etc.).
2. Never print, log, or store the API key or its characters.
3. Model discovery is based strictly on models returned by the API (client.models.list()).
4. Read-only diagnostic: preserves all project files, configuration, and the .env file.
"""
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()

from django.conf import settings
from google import genai
from google.genai.errors import APIError

def categorize_error(e: Exception) -> str:
    """
    Classify any error into a fixed, safe category string.
    Never returns raw exception text, headers, response payloads, or file paths.
    """
    if isinstance(e, APIError):
        code = getattr(e, 'code', None)
        status = str(getattr(e, 'status', '')).upper()

        if code in (401, 403) or 'UNAUTHENTICATED' in status or 'PERMISSION_DENIED' in status:
            return "Authentication failure (invalid credentials or unauthorized)"
        if code == 429 or 'RESOURCE_EXHAUSTED' in status:
            return "Quota / Rate limit reached (temporary throttle)"
        if code == 503 or 'UNAVAILABLE' in status:
            return "Model temporarily unavailable (high demand spike)"
        if code == 404 or 'NOT_FOUND' in status:
            return "Model not found or discontinued"
        if code and code >= 500:
            return f"Server error ({code})"
        return f"API error ({code or 'Unknown'})"

    err_type = type(e).__name__.lower()
    if any(k in err_type for k in ('connection', 'timeout', 'network', 'socket', 'http')):
        return "Network / Connection error"

    return "Internal client processing error"

def main():
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        print("FAIL: GEMINI_API_KEY is not configured in settings.")
        return

    print("Authenticating client and retrieving models available to key...")
    try:
        client = genai.Client(api_key=api_key)
        models_pager = client.models.list()
    except Exception as e:
        print(f"FAIL during client initialization/listing: {categorize_error(e)}")
        return

    content_gen_models = []
    embedding_models = []

    try:
        for m in models_pager:
            name = getattr(m, 'name', '') or ''
            clean_name = name.split('/')[-1] if '/' in name else name

            supported_actions = getattr(m, 'supported_actions', []) or []
            supported_methods = getattr(m, 'supported_generation_methods', []) or []
            actions = [str(a).lower() for a in (supported_actions + supported_methods)]

            if any('generatecontent' in a for a in actions) or 'generate_content' in actions:
                content_gen_models.append(clean_name)
            if any('embedcontent' in a for a in actions) or 'embed_content' in actions:
                embedding_models.append(clean_name)
    except Exception as e:
        print(f"FAIL during model filtering: {categorize_error(e)}")
        return

    print(f"Discovered {len(content_gen_models)} models supporting content generation.")
    print(f"Discovered {len(embedding_models)} models supporting embeddings.")
    print("Embedding models:", ", ".join(embedding_models[:5]))

    # Prioritize active 3.x / 4.x general purpose text/multimodal models for probing
    priority_order = [
        'gemini-3.5-flash-lite',
        'gemini-3.1-flash-lite',
        'gemini-3.8-flash',
        'gemini-4-argon'
    ]

    candidates = [m for m in priority_order if m in content_gen_models]
    for m in content_gen_models:
        if m not in candidates and ('flash' in m or 'pro' in m or 'argon' in m):
            candidates.append(m)

    print(f"\nProbing candidate models from discovered list (stops after 2 verified)...")
    working_models = []
    for model_id in candidates:
        try:
            resp = client.models.generate_content(
                model=model_id,
                contents="Respond with 'OK'",
            )
            txt = resp.text.strip() if resp.text else ""
            print(f"  [+] {model_id}: SUCCESS (response: \"{txt}\")")
            working_models.append(model_id)
            if len(working_models) >= 2:
                break
        except Exception as e:
            print(f"  [-] {model_id}: {categorize_error(e)}")

    print("\nRecommended Model Configuration for DocuLens AI:")
    if working_models:
        print(f"  Primary Model:  {working_models[0]}")
        fallback = working_models[1] if len(working_models) > 1 else "None verified yet"
        print(f"  Fallback Model: {fallback}")
    else:
        print("  No candidate models succeeded in probing.")

if __name__ == '__main__':
    main()
