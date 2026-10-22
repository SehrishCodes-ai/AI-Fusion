"""
Django settings for DocuLens AI.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Persistent data storage root (defaults to BASE_DIR for local development)
DATA_DIR_ENV = os.environ.get('DATA_DIR')
if DATA_DIR_ENV:
    DATA_DIR = Path(DATA_DIR_ENV).resolve()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
else:
    DATA_DIR = BASE_DIR

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

if not DEBUG and (not SECRET_KEY or 'insecure' in SECRET_KEY or 'xyz987' in SECRET_KEY):
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to a secure, unique value when DEBUG=False.")
elif not SECRET_KEY:
    SECRET_KEY = 'dev-insecure-key-for-local-development-only'


# Parse ALLOWED_HOSTS with quote-stripping and Render auto-detection
raw_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,.onrender.com').split(',')
ALLOWED_HOSTS = [h.strip().strip('"').strip("'") for h in raw_hosts if h.strip().strip('"').strip("'")]

# Automatically trust Render's assigned domain and internal health checks if on Render
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '').strip().strip('"').strip("'")
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Render internal load balancers and health-check probes often hit internal IP/0.0.0.0
if os.environ.get('RENDER') or RENDER_EXTERNAL_HOSTNAME:
    for internal in ['0.0.0.0', '127.0.0.1', 'localhost']:
        if internal not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(internal)

# Trust Render reverse-proxy headers for scheme and host
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

CSRF_TRUSTED_ORIGINS_ENV = os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '')
if CSRF_TRUSTED_ORIGINS_ENV:
    CSRF_TRUSTED_ORIGINS = [o.strip().strip('"').strip("'") for o in CSRF_TRUSTED_ORIGINS_ENV.split(',') if o.strip().strip('"').strip("'")]
elif RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS = [f'https://{RENDER_EXTERNAL_HOSTNAME}']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'documents',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DATA_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = []
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = DATA_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# File upload limits
MAX_UPLOAD_SIZE = int(os.environ.get('MAX_UPLOAD_SIZE_MB', 20)) * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE

# Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# Vector store persistence directory
VECTOR_STORE_DIR = DATA_DIR / 'vector_store'

# RAG configuration
RAG_CHUNK_SIZE = 700          # target characters per chunk
RAG_CHUNK_OVERLAP = 100       # overlap characters
RAG_TOP_K = 5                 # number of chunks to retrieve
RAG_SIMILARITY_THRESHOLD = 0.25  # cosine similarity threshold (lower is more similar for L2)
RAG_EMBEDDING_MODEL = 'gemini-embedding-001'
RAG_GENERATION_MODEL = 'gemini-3.5-flash-lite'
RAG_GENERATION_FALLBACK_MODEL = 'gemini-3.1-flash-lite'
