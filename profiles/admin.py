from django.contrib import admin
from django.contrib import messages
from .models import EmployeeProfile, Department, Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """Admin interface for Company management."""
    
    list_display = ('name', 'city_name', 'city_code', 'created_at')
    search_fields = ('name', 'city_name', 'city_code')
    readonly_fields = ('created_at',)
    ordering = ('name',)
    
    fieldsets = (
        ('Company Information', {
            'fields': ('name', 'city_name', 'city_code')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def delete_model(self, request, obj):
        """Override delete to show warning about cascading department deletion."""
        dept_count = obj.departments.count()
        emp_count = obj.employees.count()
        
        if dept_count > 0 or emp_count > 0:
            messages.warning(
                request,
                f'Deleting "{obj.name}" will CASCADE DELETE {dept_count} department(s) '
                f'and may affect {emp_count} employee(s). Their department references will be removed.'
            )
        
        super().delete_model(request, obj)
    
    def delete_queryset(self, request, queryset):
        """Override bulk delete to show warning."""
        total_depts = sum(company.departments.count() for company in queryset)
        total_emps = sum(company.employees.count() for company in queryset)
        
        if total_depts > 0 or total_emps > 0:
            messages.warning(
                request,
                f'Deleting {queryset.count()} compan(ies) will CASCADE DELETE {total_depts} '
                f'department(s) and may affect {total_emps} employee(s).'
            )
        
        super().delete_queryset(request, queryset)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin interface for Department management."""
    
    list_display = ('code', 'display_name', 'company', 'created_at')
    list_filter = ('company',)
    search_fields = ('display_name', 'code', 'description', 'company__name')
    readonly_fields = ('created_at',)
    ordering = ('company', 'display_name')
    
    fieldsets = (
        ('Department Information', {
            'fields': ('company', 'display_name', 'code', 'description')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    """Admin interface for Employee Profile management."""
    
    list_display = ('employee_id', 'name', 'email', 'get_username', 'age', 'company', 'department', 'created_at')
    list_filter = ('company', 'department', 'created_at')
    search_fields = ('name', 'employee_id', 'email', 'user__username', 'company__name', 'department__display_name')
    readonly_fields = ('user', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('User Account', {
            'fields': ('user',)
        }),
        ('Employee Information', {
            'fields': ('name', 'age', 'employee_id', 'email', 'company', 'department')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_username(self, obj):
        """Display linked username."""
        return obj.user.username if obj.user else 'No User'
    get_username.short_description = 'Username'
