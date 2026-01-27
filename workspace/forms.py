"""
Forms for workspace app - task completion and file uploads.
"""
from django import forms
from workflows.models import QueryAttachment
from profiles.models import Department


class AttachmentUploadForm(forms.ModelForm):
    """Form for uploading file attachments to query tickets."""
    
    class Meta:
        model = QueryAttachment
        fields = ['file']
        labels = {
            'file': '文件 / File'
        }
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'})
        }


class CompleteTaskForm(forms.Form):
    """Form for completing a task with optional child query creation."""
    
    # Completion notes
    completion_notes = forms.CharField(
        label='完成备注 / Completion Notes',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': '(Optional) Add any notes about task completion...'
        }),
        required=False
    )
    
    # Child query creation
    create_child_query = forms.BooleanField(
        label='创建子任务 / Create Child Query',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    child_query_type = forms.CharField(
        label='子任务类型 / Child Query Type',
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 报价单, 采购单, 发货单'
        }),
        help_text='中文类型名称，将转换为拼音首字母 / Chinese type name, will be converted to Pinyin initials'
    )
    
    child_target_dept = forms.ModelChoiceField(
        label='目标部门 / Target Department',
        queryset=Department.objects.all(),
        required=False,
        empty_label='-- 选择部门 / Select Department --',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    child_title = forms.CharField(
        label='子任务标题 / Child Task Title',
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter child task title...'
        })
    )
    
    child_content = forms.CharField(
        label='子任务内容 / Child Task Content',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter child task details...'
        }),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        self.user_dept = kwargs.pop('user_dept', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        create_child = cleaned_data.get('create_child_query')
        
        # If creating child query, validate all child fields are provided
        if create_child:
            child_query_type = cleaned_data.get('child_query_type')
            child_target_dept = cleaned_data.get('child_target_dept')
            child_title = cleaned_data.get('child_title')
            child_content = cleaned_data.get('child_content')
            
            if not child_query_type:
                self.add_error('child_query_type', '创建子任务时必须提供类型。/ Query type is required when creating child query.')
            
            if not child_target_dept:
                self.add_error('child_target_dept', '创建子任务时必须提供目标部门。/ Target department is required when creating child query.')
            
            if not child_title:
                self.add_error('child_title', '创建子任务时必须提供标题。/ Title is required when creating child query.')
            
            if not child_content:
                self.add_error('child_content', '创建子任务时必须提供内容。/ Content is required when creating child query.')
        
        return cleaned_data
