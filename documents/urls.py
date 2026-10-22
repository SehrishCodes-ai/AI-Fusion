"""
URL patterns for the documents app.
"""
from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_document, name='upload'),
    path('delete/<uuid:doc_id>/', views.delete_document, name='delete'),
    path('ask/', views.ask_question, name='ask'),
    path('status/<uuid:doc_id>/', views.document_status, name='status'),
]
