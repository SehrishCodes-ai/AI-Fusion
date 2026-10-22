"""
Django models for DocuLens AI document management.
"""
import uuid
from django.db import models


class Document(models.Model):
    """Represents an uploaded document and its processing state."""

    class FileType(models.TextChoices):
        PDF = 'pdf', 'PDF'
        TXT = 'txt', 'TXT'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        INDEXED = 'indexed', 'Indexed'
        ERROR = 'error', 'Error'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_name = models.CharField(max_length=255)
    file = models.FileField(upload_to='uploads/')
    file_type = models.CharField(max_length=10, choices=FileType.choices)
    upload_timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error_message = models.TextField(blank=True, default='')
    page_count = models.IntegerField(default=0)
    char_count = models.IntegerField(default=0)
    chunk_count = models.IntegerField(default=0)
    session_key = models.CharField(max_length=40, db_index=True, default='')

    class Meta:
        ordering = ['-upload_timestamp']

    def __str__(self):
        return self.display_name


class DocumentChunk(models.Model):
    """A text chunk extracted from a document, ready for retrieval."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField()
    text = models.TextField()
    page_number = models.IntegerField(null=True, blank=True)
    char_start = models.IntegerField(default=0)
    faiss_index_id = models.IntegerField(default=-1)

    class Meta:
        ordering = ['document', 'chunk_index']

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.display_name}"
