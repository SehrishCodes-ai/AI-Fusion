"""
Forms for document upload validation.
"""
from django import forms


class DocumentUploadForm(forms.Form):
    file = forms.FileField(
        label='Upload Document',
        help_text='Accepted formats: PDF, TXT. Maximum size: 20 MB.',
        error_messages={
            'required': 'Please select a file to upload.',
            'invalid': 'The uploaded file is invalid.',
        }
    )
