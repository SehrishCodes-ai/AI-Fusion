"""
Test production host resolution and reverse proxy settings.
Simulates Render reverse proxy headers, internal health checks, and domain parsing.
"""
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Simulate Render environment
os.environ['RENDER'] = 'true'
os.environ['RENDER_EXTERNAL_HOSTNAME'] = 'doculens-ai-n500.onrender.com'
os.environ['DJANGO_DEBUG'] = 'False'
os.environ['DJANGO_SECRET_KEY'] = 'production-safe-test-secret-key-123456789'
os.environ['DJANGO_ALLOWED_HOSTS'] = 'localhost, 127.0.0.1, .onrender.com'
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

import django
django.setup()

from django.conf import settings
from django.test import RequestFactory
from django.http.request import validate_host

def test_hosts():
    print("=== Configured ALLOWED_HOSTS ===")
    print(settings.ALLOWED_HOSTS)

    # 1. Check doculens-ai-n500.onrender.com
    assert validate_host('doculens-ai-n500.onrender.com', settings.ALLOWED_HOSTS), \
        "FAIL: doculens-ai-n500.onrender.com should be allowed!"
    print("[PASS] doculens-ai-n500.onrender.com is allowed")

    # 2. Check 0.0.0.0 (internal render probe)
    assert validate_host('0.0.0.0', settings.ALLOWED_HOSTS), \
        "FAIL: 0.0.0.0 should be allowed for Render health checks!"
    print("[PASS] 0.0.0.0 is allowed")

    # 3. Check 127.0.0.1
    assert validate_host('127.0.0.1', settings.ALLOWED_HOSTS), \
        "FAIL: 127.0.0.1 should be allowed!"
    print("[PASS] 127.0.0.1 is allowed")

    # 4. Check localhost
    assert validate_host('localhost', settings.ALLOWED_HOSTS), \
        "FAIL: localhost should be allowed!"
    print("[PASS] localhost is allowed")

    # 5. Check arbitrary untrusted host is blocked
    assert not validate_host('malicious-site.com', settings.ALLOWED_HOSTS), \
        "FAIL: malicious-site.com should be rejected!"
    print("[PASS] Untrusted hosts are properly rejected")

    # 6. Test RequestFactory with X-Forwarded-Host
    rf = RequestFactory()
    req = rf.get('/', HTTP_X_FORWARDED_HOST='doculens-ai-n500.onrender.com', HTTP_HOST='0.0.0.0:10000')
    resolved_host = req.get_host()
    assert resolved_host == 'doculens-ai-n500.onrender.com', \
        f"FAIL: Expected X-Forwarded-Host to resolve to doculens-ai-n500.onrender.com, got {resolved_host}"
    print(f"[PASS] USE_X_FORWARDED_HOST correctly resolves host to {resolved_host}")

    print("\nALL PRODUCTION HOST CONFIGURATION TESTS PASSED!")

if __name__ == '__main__':
    test_hosts()
