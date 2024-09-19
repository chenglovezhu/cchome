from django import forms
from .models import FileAppertain, FileInfo

# 单文件上传测试所创
class UploadFileForm(forms.Form):
    file = forms.FileField()

# 多文件上传测试所创
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result

class FileFieldForm(forms.Form):
    album = forms.CharField(required=False)
    subject = forms.CharField(required=False)
    categorySelect = forms.CharField(required=False)
    levelSelect = forms.CharField(required=False)
    inputTags = forms.CharField(required=False)
    file_field = MultipleFileField()

class SearchFileForm(forms.Form):
    query = forms.CharField()
    
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
    
class FileInfoForm(forms.ModelForm):
    class Meta:
        model = FileInfo
        fields = ['name', 'album', 'subject']
