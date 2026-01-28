"""
Forms for workspace app - task completion and file uploads.
"""
from django import forms
from decimal import Decimal
from workflows.models import QueryAttachment, QueryFieldDefinition, QueryType
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
        label='创建后续任务 / Create Follow-up Task',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    # NEW: Dynamic QueryType dropdown (filtered by user's department)
    next_query_type = forms.ModelChoiceField(
        label='后续任务类型 / Follow-up Task Type',
        queryset=QueryType.objects.none(),  # Empty by default, set in __init__
        required=False,
        empty_label='-- 选择任务类型 / Select Task Type --',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    child_target_dept = forms.ModelChoiceField(
        label='目标部门 / Target Department',
        queryset=Department.objects.all(),
        required=False,
        empty_label='-- 选择部门 / Select Department --',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    child_title = forms.CharField(
        label='后续任务标题 / Follow-up Task Title',
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter follow-up task title...'
        })
    )
    
    child_content = forms.CharField(
        label='后续任务内容 / Follow-up Task Content',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter follow-up task details...'
        }),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        self.user_dept = kwargs.pop('user_dept', None)
        super().__init__(*args, **kwargs)
        
        # Filter next_query_type queryset based on user's department permissions
        if self.user_dept:
            self.fields['next_query_type'].queryset = QueryType.objects.filter(
                is_active=True,
                creating_departments=self.user_dept  # Only show types this dept can create
            ).order_by('name')
            
            # Also filter target departments to only those allowed by the selected query type
            # (This will be refined on the frontend via JS, but provide a reasonable default)
    
    def clean(self):
        cleaned_data = super().clean()
        create_child = cleaned_data.get('create_child_query')
        
        # If creating child query, validate all child fields are provided
        if create_child:
            next_query_type = cleaned_data.get('next_query_type')
            child_target_dept = cleaned_data.get('child_target_dept')
            child_title = cleaned_data.get('child_title')
            child_content = cleaned_data.get('child_content')
            
            if not next_query_type:
                self.add_error('next_query_type', '创建后续任务时必须选择类型。/ Task type is required when creating follow-up task.')
            
            if not child_target_dept:
                self.add_error('child_target_dept', '创建后续任务时必须选择目标部门。/ Target department is required when creating follow-up task.')
            else:
                # Validate target department is allowed for this query type
                if next_query_type and child_target_dept not in next_query_type.allowed_departments.all():
                    self.add_error('child_target_dept', '所选部门不能接收此类型任务。/ Selected department cannot receive this task type.')
            
            if not child_title:
                self.add_error('child_title', '创建后续任务时必须提供标题。/ Title is required when creating follow-up task.')
            
            if not child_content:
                self.add_error('child_content', '创建后续任务时必须提供内容。/ Content is required when creating follow-up task.')
        
        return cleaned_data


# ============================================================================
# Dynamic Ticket Form - Builds itself from QueryType definition
# ============================================================================

class DynamicTicketForm(forms.Form):
    """
    Dynamic form that builds fields based on QueryType field definitions.
    Includes target_department field restricted to allowed departments.
    
    Usage:
        form = DynamicTicketForm(query_type=my_query_type)
        form = DynamicTicketForm(data=request.POST, files=request.FILES, query_type=my_query_type)
    """
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the form with dynamic fields from QueryType.
        
        Args:
            query_type: QueryType instance to build fields from
        """
        self.query_type = kwargs.pop('query_type', None)
        super().__init__(*args, **kwargs)
        
        if self.query_type:
            self._build_target_department_field()
            self._build_standard_fields()
            self._build_dynamic_fields()
    
    def _build_target_department_field(self):
        """Add target department field restricted to allowed departments."""
        self.fields['target_department'] = forms.ModelChoiceField(
            queryset=self.query_type.allowed_departments.all(),
            required=True,
            label='目标部门 / Target Department',
            empty_label='-- 选择部门 / Select Department --',
            widget=forms.Select(attrs={
                'class': 'form-select form-control'
            }),
            help_text='Only departments authorized to receive this query type are shown.'
        )
    
    def _build_standard_fields(self):
        """Add standard fields (title, description)."""
        self.fields['title'] = forms.CharField(
            label='标题 / Title',
            max_length=200,
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter ticket title...'
            })
        )
        
        self.fields['description'] = forms.CharField(
            label='描述 / Description',
            required=False,
            widget=forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter general description (optional)...'
            })
        )
    
    def _build_dynamic_fields(self):
        """Build form fields dynamically based on QueryType field definitions."""
        field_definitions = self.query_type.fields.all().order_by('order', 'id')
        
        for field_def in field_definitions:
            field = self._create_field(field_def)
            if field:
                self.fields[field_def.field_key] = field
    
    def _create_field(self, field_def):
        """
        Create a Django form field from a QueryFieldDefinition.
        
        Args:
            field_def: QueryFieldDefinition instance
            
        Returns:
            Form field instance
        """
        # Common widget attributes
        widget_attrs = {
            'class': 'form-control',
        }
        
        if field_def.placeholder:
            widget_attrs['placeholder'] = field_def.placeholder
        
        # Field type mapping
        field_type = field_def.field_type
        
        if field_type == QueryFieldDefinition.FieldType.TEXT:
            return forms.CharField(
                label=field_def.label,
                required=field_def.required,
                help_text=field_def.help_text,
                widget=forms.TextInput(attrs=widget_attrs)
            )
        
        elif field_type == QueryFieldDefinition.FieldType.TEXTAREA:
            widget_attrs['rows'] = 4
            return forms.CharField(
                label=field_def.label,
                required=field_def.required,
                help_text=field_def.help_text,
                widget=forms.Textarea(attrs=widget_attrs)
            )
        
        elif field_type == QueryFieldDefinition.FieldType.INTEGER:
            return forms.IntegerField(
                label=field_def.label,
                required=field_def.required,
                help_text=field_def.help_text,
                widget=forms.NumberInput(attrs=widget_attrs)
            )
        
        elif field_type == QueryFieldDefinition.FieldType.DECIMAL:
            return forms.DecimalField(
                label=field_def.label,
                required=field_def.required,
                help_text=field_def.help_text,
                max_digits=10,
                decimal_places=2,
                widget=forms.NumberInput(attrs={**widget_attrs, 'step': '0.01'})
            )
        
        elif field_type == QueryFieldDefinition.FieldType.DATE:
            widget_attrs['type'] = 'date'
            return forms.DateField(
                label=field_def.label,
                required=field_def.required,
                help_text=field_def.help_text,
                widget=forms.DateInput(attrs=widget_attrs)
            )
        
        elif field_type == QueryFieldDefinition.FieldType.FILE:
            return forms.FileField(
                label=field_def.label,
                required=field_def.required,
                help_text=field_def.help_text,
                widget=forms.FileInput(attrs={'class': 'form-control'})
            )
        
        elif field_type == QueryFieldDefinition.FieldType.BOOLEAN:
            return forms.BooleanField(
                label=field_def.label,
                required=False,  # Boolean fields should not be required
                help_text=field_def.help_text,
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
            )
        
        # Default to text field
        return forms.CharField(
            label=field_def.label,
            required=field_def.required,
            help_text=field_def.help_text,
            widget=forms.TextInput(attrs=widget_attrs)
        )
    
    def get_dynamic_field_values(self):
        """
        Get cleaned data for dynamic fields only (excludes title/description).
        Separates regular fields from file fields.
        
        Returns:
            tuple: (content_data dict, file_fields dict)
        """
        if not self.is_valid():
            return {}, {}
        
        content_data = {}
        file_fields = {}
        
        if not self.query_type:
            return content_data, file_fields
        
        for field_def in self.query_type.fields.all():
            field_key = field_def.field_key
            value = self.cleaned_data.get(field_key)
            
            if field_def.field_type == QueryFieldDefinition.FieldType.FILE:
                if value:
                    file_fields[field_key] = (value, field_def)
            else:
                if value is not None:
                    # Ensure JSON serializable
                    if hasattr(value, 'isoformat'):
                        content_data[field_key] = value.isoformat()
                    elif isinstance(value, Decimal):
                        content_data[field_key] = float(value)
                    else:
                        content_data[field_key] = value
        
        return content_data, file_fields
