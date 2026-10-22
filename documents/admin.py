"""
Admin configuration for DocuLens AI.
"""
from django.contrib import admin
from .models import Document, DocumentChunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'file_type', 'status', 'chunk_count', 'upload_timestamp']
    list_filter = ['status', 'file_type']
    readonly_fields = ['id', 'upload_timestamp', 'char_count', 'chunk_count', 'page_count']
    search_fields = ['display_name']


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ['document', 'chunk_index', 'page_number', 'faiss_index_id']
    list_filter = ['document']
    readonly_fields = ['id']
