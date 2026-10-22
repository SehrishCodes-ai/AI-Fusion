"""
Text extraction service — PDF and TXT.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text(file_path: str, file_type: str) -> list[dict]:
    """
    Extract text from a document file.

    Returns a list of page dicts: [{'page': int, 'text': str}, ...]
    Page numbers are 1-based for PDFs; TXT files use page=1 throughout.
    Raises ValueError for unsupported types or empty results.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if file_type == 'pdf':
        return _extract_pdf(file_path)
    elif file_type == 'txt':
        return _extract_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def _extract_pdf(file_path: Path) -> list[dict]:
    """Extract text page-by-page from a PDF using PyPDF2."""
    try:
        import PyPDF2
    except ImportError:
        raise RuntimeError("PyPDF2 is not installed. Run: pip install PyPDF2")

    pages = []
    try:
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            if len(reader.pages) == 0:
                raise ValueError("PDF has no pages.")

            for page_num, page in enumerate(reader.pages, start=1):
                try:
                    text = page.extract_text() or ''
                    text = text.strip()
                    if text:
                        pages.append({'page': page_num, 'text': text})
                except Exception as e:
                    logger.warning("Failed to extract page %d: %s", page_num, e)

    except PyPDF2.errors.PdfReadError as e:
        raise ValueError(f"Cannot read PDF: {e}")
    except Exception as e:
        raise ValueError(f"PDF extraction error: {e}")

    if not pages:
        raise ValueError(
            "No extractable text found in this PDF. "
            "The document may be scanned or image-based. "
            "Please upload a text-based PDF."
        )
    return pages


def _extract_txt(file_path: Path) -> list[dict]:
    """Read a plain text file."""
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
    for enc in encodings:
        try:
            text = file_path.read_text(encoding=enc)
            text = text.strip()
            if not text:
                raise ValueError("Text file is empty.")
            return [{'page': None, 'text': text}]
        except (UnicodeDecodeError, LookupError):
            continue
        except ValueError:
            raise

    raise ValueError("Cannot decode text file. Please ensure it is UTF-8 encoded.")
