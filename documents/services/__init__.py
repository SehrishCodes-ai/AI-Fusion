"""
Services package init — expose process_document at the package level.
"""
from .evidence import process_document

__all__ = ['process_document']
