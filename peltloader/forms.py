from django import forms
from .models import CarData

class FileUploadForm(forms.ModelForm):
    class Meta:
        model = CarData
        fields = ['body_no', 'date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
