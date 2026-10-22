# DocuLens AI 🔍

> **Find the evidence. Understand the answer.**

An AI-powered document intelligence system built for the **AI-Fusion 2026 Hackathon**.
Upload PDF and TXT documents, ask natural language questions, and receive **evidence-grounded answers** with verifiable source passages — powered by Google Gemini AI and FAISS semantic search.

---

## Architecture

```
USER UPLOADS PDF/TXT
        ↓
DJANGO VALIDATES THE FILE
        ↓
TEXT EXTRACTION (PyPDF2 / plain text)
        ↓
TEXT CHUNKING (boundary-aware, overlapping)
        ↓
EMBEDDING GENERATION (Gemini gemini-embedding-001)
        ↓
VECTOR INDEXING (FAISS IndexFlatL2 + IndexIDMap)
        ↓
USER ASKS A QUESTION
        ↓
QUESTION EMBEDDING (same model)
        ↓
SEMANTIC RETRIEVAL (cosine/L2 similarity search)
        ↓
EVIDENCE SUFFICIENCY CHECK
        ↓
RETRIEVED CONTEXT → GEMINI 3.8 FLASH
        ↓
GROUNDED ANSWER + SOURCE REFERENCES DISPLAYED
```

---

## Technology Stack

| Layer          | Technology                    |
|---------------|-------------------------------|
| Backend        | Python 3.14, Django 6.1       |
| Frontend       | Django Templates, Bootstrap 5, Vanilla JS |
| PDF Processing | PyPDF2 3.0                    |
| Embeddings     | Gemini `gemini-embedding-001` |
| Vector Store   | FAISS 1.15 (IndexFlatL2 + IndexIDMap) |
| Generation     | Gemini `gemini-3.8-flash`     |
| Database       | SQLite (Django ORM)           |
| Static Files   | WhiteNoise                    |

---

## Setup Instructions

### 1. Prerequisites

- Python 3.10+ (tested on 3.14)
- A Google Gemini API key — get one at [aistudio.google.com](https://aistudio.google.com/app/apikey)

### 2. Clone / navigate to the project

```bash
cd d:\AI-Fusion
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
copy .env.example .env
```

Edit `.env` and fill in:

```
GEMINI_API_KEY=your_actual_api_key_here
DJANGO_SECRET_KEY=a-long-random-string
DJANGO_DEBUG=True
```

### 5. Apply database migrations

```bash
python manage.py migrate
```

### 6. Run the application

```bash
python manage.py runserver
```

Open your browser at **http://127.0.0.1:8000/**

---

## Usage

1. **Upload** a PDF or TXT file using the Document Workspace panel.
2. **Wait** for the document to be processed and indexed (shown in the status badge).
3. **Ask** a natural language question in the Q&A panel.
4. **Review** the grounded answer and the supporting evidence passages.

---

## RAG Configuration

Settings in `config/settings.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `RAG_CHUNK_SIZE` | 700 chars | Target chunk size |
| `RAG_CHUNK_OVERLAP` | 100 chars | Overlap between chunks |
| `RAG_TOP_K` | 5 | Number of chunks retrieved per query |
| `RAG_SIMILARITY_THRESHOLD` | 0.25 | L2 distance threshold |
| `RAG_EMBEDDING_MODEL` | `gemini-embedding-001` | Embedding model |
| `RAG_GENERATION_MODEL` | `gemini-3.8-flash` | Generation model |

---

## Vector Index Persistence

The FAISS index and metadata are stored in `vector_store/`:
- `doculens.index` — FAISS binary index
- `doculens_meta.pkl` — Python pickle mapping FAISS IDs → chunk UUIDs

These files are automatically reloaded on application startup.

---

## Project Structure

```
doculens_ai/
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── __init__.py
├── documents/
│   ├── models.py          # Document + DocumentChunk models
│   ├── views.py           # Upload, delete, ask, status views
│   ├── urls.py
│   ├── forms.py
│   ├── admin.py
│   ├── apps.py            # App config (pre-loads FAISS index)
│   ├── services/
│   │   ├── extraction.py  # PDF + TXT text extraction
│   │   ├── chunking.py    # Boundary-aware text chunking
│   │   ├── embeddings.py  # Gemini embedding generation
│   │   ├── vector_store.py# FAISS index management
│   │   ├── retrieval.py   # Semantic search + evidence checks
│   │   ├── generation.py  # Gemini grounded answer generation
│   │   └── evidence.py    # Full pipeline orchestrator
│   └── templates/
│       └── documents/
│           └── index.html
├── media/                 # Uploaded files (gitignored)
├── vector_store/          # FAISS index files (gitignored)
└── tests/
    └── sample_document.txt
```

---

## Testing

Use `tests/sample_document.txt` for demonstration.

### Manual test sequence

| Test | Expected Result |
|------|----------------|
| Upload `sample_document.txt` | Status changes to "Indexed" |
| Ask "What is RAG?" | Grounded answer + source excerpt from Section 3 |
| Ask "What are the judging criteria?" | Answer with percentages from Section 6 |
| Ask "What is the weather today?" | "I couldn't find sufficient information…" |
| Upload invalid file type | Error message, file rejected |

---

## Known Limitations

- **Scanned PDFs**: OCR is not implemented. Only text-based PDFs work.
- **Processing is synchronous**: Large documents may cause a slow upload response. For production, use Celery + Redis.
- **FAISS deletion**: Vector removal requires full index rebuild (FAISS limitation).
- **Session isolation**: Documents are tied to browser sessions — not user accounts.
- **Embedding rate limits**: Gemini API rate limits may apply for large documents.

---

## Deployment Notes

This application requires:
- Python runtime (Django + dependencies)
- Writable filesystem for SQLite and FAISS index
- Outbound HTTPS to `generativelanguage.googleapis.com`

Suitable platforms: Railway, Render, Fly.io, PythonAnywhere (with correct settings).

Not suitable for: static hosting platforms (Netlify, Vercel static tier).

---

## API Key Security

- API keys are read from environment variables only.
- Never commit `.env` to version control.
- The `.gitignore` excludes `.env` and vector store binaries.
- API keys are never exposed in JavaScript or HTML output.

---

## Presentation Outline (7 Minutes)

1. **Problem** — Documents contain critical information that is hard to query semantically.
2. **Solution** — DocuLens AI: a RAG pipeline that retrieves evidence and generates grounded answers.
3. **Upload flow** — Django validates → extracts text → chunks → embeds → FAISS indexes.
4. **Chunking** — Boundary-aware splitting with overlap to preserve context.
5. **Embeddings** — Gemini `gemini-embedding-001` maps text to high-dimensional vectors.
6. **Retrieval** — User question embedded → L2 similarity search → top-K chunks returned.
7. **Generation** — Retrieved context + strict system prompt → Gemini 3.8 Flash → grounded answer.
8. **Source attribution** — Sources constructed from retrieved chunk metadata, not model output.
9. **Unsupported questions** — Evidence sufficiency check prevents hallucinated answers.
10. **Demo** — Live upload, supported question, paraphrased question, unsupported question.

---

Built with ❤️ for AI-Fusion 2026
