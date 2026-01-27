from django import forms
from django.contrib.auth.models import User
from .models import EmployeeProfile, Department, Company
from .validators import EmployeePasswordValidator, DEFAULT_PASSWORD


class EmployeeProfileForm(forms.ModelForm):
    """Form for creating and updating employee profiles."""
    
    # Add password field (not part of model, handled separately)
    password = forms.CharField(
        max_length=6,
        initial=DEFAULT_PASSWORD,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password'
        }),
        validators=[EmployeePasswordValidator()],
        help_text='Max 6 characters, at least 3 letters',
        label='Password'
    )
    
    class Meta:
        model = EmployeeProfile
        fields = ['name', 'age', 'employee_id', 'email', 'company', 'department']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter full name'
            }),
            'age': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter age',
                'min': 18,
                'max': 100
            }),
            'employee_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter employee ID'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email address'
            }),
            'company': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_company'
            }),
            'department': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_department'
            }),
        }
        labels = {
            'name': 'Name',
            'age': 'Age',
            'employee_id': 'Employee ID',
            'email': 'Email Address',
            'company': 'Company',
            'department': 'Department',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Load all companies
        self.fields['company'].queryset = Company.objects.all()
        self.fields['company'].empty_label = "Select your company"
        
        # Load all departments (will be filtered by JavaScript in frontend)
        self.fields['department'].queryset = Department.objects.all()
        self.fields['department'].empty_label = "Select a department"
    
    def clean_age(self):
        """Validate age is within reasonable range."""
        age = self.cleaned_data.get('age')
        if age and (age < 18 or age > 100):
            raise forms.ValidationError("Age must be between 18 and 100.")
        return age
    
    def clean_employee_id(self):
        """Validate employee ID format."""
        employee_id = self.cleaned_data.get('employee_id')
        if employee_id and not employee_id.strip():
            raise forms.ValidationError("Employee ID cannot be empty.")
        return employee_id.strip()
    
    def clean_company(self):
        """Ensure a company is selected."""
        company = self.cleaned_data.get('company')
        if not company:
            raise forms.ValidationError("Please select a company.")
        return company
    
    def clean_department(self):
        """Ensure a department is selected."""
        department = self.cleaned_data.get('department')
        if not department:
            raise forms.ValidationError("Please select a department.")
        return department
    
    def clean(self):
        """Validate that department belongs to selected company."""
        cleaned_data = super().clean()
        company = cleaned_data.get('company')
        department = cleaned_data.get('department')
        
        if company and department:
            if department.company != company:
                raise forms.ValidationError(
                    f"Department '{department.display_name}' does not belong to '{company.name}'."
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save to create Django User with synced credentials."""
        # Don't save the instance yet
        instance = super().save(commit=False)
        
        # Get password from cleaned data
        password = self.cleaned_data.get('password')
        employee_id = self.cleaned_data.get('employee_id')
        email = self.cleaned_data.get('email')
        
        # Create Django User with employee_id as username
        user = User.objects.create_user(
            username=employee_id,
            email=email,
            password=password  # set_password is called internally
        )
        
        # Link user to employee profile
        instance.user = user
        
        if commit:
            instance.save()
        
        return instance
