"""
Text chunking service — splits document pages into overlapping chunks.
"""
import re
import logging

logger = logging.getLogger(__name__)


def chunk_pages(pages: list[dict], chunk_size: int = 700, overlap: int = 100) -> list[dict]:
    """
    Split a list of page dicts into overlapping text chunks.

    Each page dict: {'page': int|None, 'text': str}
    Returns a list of chunk dicts:
      {
        'chunk_index': int,
        'text': str,
        'page_number': int|None,
        'char_start': int,
      }
    """
    chunks = []
    chunk_index = 0

    for page_data in pages:
        page_num = page_data.get('page')
        text = page_data.get('text', '').strip()
        if not text:
            continue

        # Split on sentence/paragraph boundaries first
        segments = _split_into_segments(text)

        current = ''
        current_start = 0
        absolute_start = 0

        for seg in segments:
            if len(current) + len(seg) <= chunk_size:
                current += seg
            else:
                if current.strip():
                    chunks.append({
                        'chunk_index': chunk_index,
                        'text': current.strip(),
                        'page_number': page_num,
                        'char_start': current_start,
                    })
                    chunk_index += 1
                    # Carry overlap from end of current chunk
                    overlap_text = current[-overlap:] if len(current) > overlap else current
                    current_start = current_start + len(current) - len(overlap_text)
                    current = overlap_text + seg
                else:
                    current = seg
                    current_start = absolute_start

            absolute_start += len(seg)

        # Flush the last segment
        if current.strip():
            chunks.append({
                'chunk_index': chunk_index,
                'text': current.strip(),
                'page_number': page_num,
                'char_start': current_start,
            })
            chunk_index += 1

    if not chunks:
        logger.warning("No chunks produced from %d pages.", len(pages))

    return chunks


def _split_into_segments(text: str) -> list[str]:
    """
    Split text into sentence-like segments preserving delimiters.
    Tries to break on paragraph/sentence boundaries.
    """
    # Split on double-newlines (paragraphs) first
    paragraphs = re.split(r'(\n{2,})', text)
    segments = []
    for para in paragraphs:
        if len(para) <= 400:
            segments.append(para)
        else:
            # Split long paragraphs on sentences
            sentences = re.split(r'(?<=[.!?])\s+', para)
            segments.extend(sentences)
    return segments
