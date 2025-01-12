from django import forms
from .models import FileInfo, FileAppertain


class FileInfoForm(forms.ModelForm):
    class Meta:
        model = FileInfo
        fields = ['name', 'album', 'subject', 'remark']
    
    
class FileAppertainForm(forms.ModelForm):
    parent = forms.ModelChoiceField(
        queryset=FileAppertain.objects.all(),
        required=False,
        empty_label="无父分类",
        label="父分类",
    )

    class Meta:
        model = FileAppertain
        fields = ['name', 'flag', 'parent']
        labels = {
            'name': '名称',
            'flag': '类型',
            'parent': '父分类',
        }
        
        widgets = {
            'flag': forms.Select(choices=FileAppertain.FLAG_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].label_from_instance = lambda obj: f"{obj.name} ({obj.flag})"

    def clean_parent(self):
        parent = self.cleaned_data.get('parent')
        return parent.id if parent else 0