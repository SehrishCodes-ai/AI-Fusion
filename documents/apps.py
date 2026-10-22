"""
App configuration for DocuLens AI documents app.
"""
from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'documents'
    verbose_name = 'DocuLens AI Documents'

    def ready(self):
        """Pre-load the FAISS index when Django starts."""
        try:
            from documents.services.vector_store import initialize
            initialize()
        except Exception:
            pass  # Don't crash on startup if vector store isn't ready yet
