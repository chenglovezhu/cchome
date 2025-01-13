from django import forms
from .models import FileInfo, FileAppertain


class FileInfoForm(forms.ModelForm):
    class Meta:
        model = FileInfo
        fields = ['name', 'album', 'subject', 'remark']  # 定义表单使用的模型和字段
        # 备注：'name' 是文件名称，'album' 是文件所属专辑，'subject' 是文件主题，'remark' 是附加备注
    
    
class FileAppertainForm(forms.ModelForm):
    parent = forms.ModelChoiceField(
        queryset=FileAppertain.objects.all(),
        required=False,
        empty_label="无父分类",
        label="父分类",
    )

    class Meta:
        model = FileAppertain
        fields = ['name', 'flag', 'parent']  # 定义表单使用的模型字段
        # 备注：'name' 是分类名称，'flag' 是分类类型标识，'parent' 是父级分类
        labels = {
            'name': '名称',    # 字段在表单中显示的中文标签
            'flag': '类型',    # 分类类型的显示标签
            'parent': '父分类', # 上级分类的显示标签
        }
        
        widgets = {
            'flag': forms.Select(choices=FileAppertain.FLAG_CHOICES),  # 使用下拉选择框展示分类类型选项
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].label_from_instance = lambda obj: f"{obj.name} ({obj.flag})"

    def clean_parent(self):
        parent = self.cleaned_data.get('parent')
        return parent.id if parent else 0