"""
Automated test verifying CSRF token provisioning on index page and upload handling.
"""
import os
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()

from django.conf import settings
from django.test import Client

def test_csrf_and_upload():
    if 'testserver' not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS.append('testserver')
    client = Client(enforce_csrf_checks=True)

    # 1. Fetch index page
    print("1. Requesting GET / ...")
    resp = client.get('/')
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    
    # Verify CSRF cookie is set in response
    csrf_cookie = resp.cookies.get('csrftoken')
    assert csrf_cookie is not None, "FAIL: csrftoken cookie was not set in response!"
    token_val = csrf_cookie.value
    print(f"   PASS: csrftoken cookie received successfully (length: {len(token_val)} chars).")

    # Verify {% csrf_token %} input is rendered in HTML
    content = resp.content.decode('utf-8')
    assert 'name="csrfmiddlewaretoken"' in content or "name='csrfmiddlewaretoken'" in content or 'name=csrfmiddlewaretoken' in content, \
        "FAIL: csrfmiddlewaretoken input not found in rendered HTML!"
    print("   PASS: csrfmiddlewaretoken input found in rendered HTML template.")

    # 2. Test POST /upload/ with invalid CSRF token (should fail 403)
    print("\n2. Testing POST /upload/ with MISSING CSRF token...")
    file_payload = BytesIO(b"Hello CSRF test")
    file_payload.name = "test.txt"
    bad_resp = client.post('/upload/', {'file': file_payload})
    assert bad_resp.status_code == 403, f"Expected 403 Forbidden without CSRF, got {bad_resp.status_code}"
    print(f"   PASS: Correctly rejected with {bad_resp.status_code} Forbidden when CSRF token is missing.")

    # 3. Test POST /upload/ with VALID X-CSRFToken header
    print("\n3. Testing POST /upload/ with VALID X-CSRFToken header...")
    file_payload = BytesIO(b"Document intelligence test file content.")
    file_payload.name = "test_upload.txt"
    
    # Provide the token via HTTP_X_CSRFTOKEN as modern JS fetch sends it
    ok_resp = client.post(
        '/upload/',
        {'file': file_payload},
        HTTP_X_CSRFTOKEN=token_val,
    )
    assert ok_resp.status_code != 403, f"FAIL: Still received 403 Forbidden with valid CSRF token!"
    print(f"   PASS: CSRF verification succeeded! Response status: {ok_resp.status_code}")

    print("\nALL CSRF VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    test_csrf_and_upload()
