from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import EmployeeProfile, Department, Company
from workflows.models import SenderTicket, ReceiverTicket, QueryTicket


# ============================================================================
# Step 3: Custom User Admin with EmployeeProfile Inline
# ============================================================================

class EmployeeProfileInline(admin.StackedInline):
    """
    Inline editor for EmployeeProfile within User admin.
    Allows Admin to set Department directly on the User page.
    """
    model = EmployeeProfile
    can_delete = False
    verbose_name_plural = 'Employee Profile & Department'
    fk_name = 'user'
    
    fields = ('department', 'company', 'name', 'employee_id', 'email', 'age')
    
    def get_readonly_fields(self, request, obj=None):
        """Make some fields readonly after creation."""
        if obj:  # Editing existing user
            return ('created_at', 'updated_at')
        return ()


# Unregister the default User admin
admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Extended User admin with EmployeeProfile inline.
    Shows Department dropdown inside the User edit page.
    """
    inlines = (EmployeeProfileInline,)
    
    # Preserve default list_display and add department info
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_department', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'employeeprofile__department__display_name')
    
    def get_department(self, obj):
        """Display user's department."""
        if hasattr(obj, 'employeeprofile') and obj.employeeprofile.department:
            return obj.employeeprofile.department.display_name
        return '-'
    get_department.short_description = 'Department'
    get_department.admin_order_field = 'employeeprofile__department'


# ============================================================================
# Step 4: Department Members Inline for Department Admin
# ============================================================================

class DepartmentMembersInline(admin.TabularInline):
    """
    Read-only inline showing all members of a department.
    Displayed on the Department edit page.
    """
    model = EmployeeProfile
    fk_name = 'department'
    fields = ('get_username', 'get_full_name_cn', 'email')
    readonly_fields = ('get_username', 'get_full_name_cn', 'email')
    extra = 0  # Do not show empty rows
    can_delete = False
    verbose_name = 'Department Member'
    verbose_name_plural = 'Department Members'
    
    def get_username(self, obj):
        """Display the linked username."""
        return obj.user.username if obj.user else 'No User'
    get_username.short_description = 'Username'
    
    def get_full_name_cn(self, obj):
        """Display name in Chinese order (Last Name First)."""
        return obj.full_name_cn()
    get_full_name_cn.short_description = 'Name (姓名)'
    
    def has_add_permission(self, request, obj=None):
        """Prevent adding members through this inline."""
        return False


# ============================================================================
# Department Box Inlines (Sender Box & Receiver Box)
# ============================================================================

class SenderBoxInline(admin.TabularInline):
    """
    Inline showing tickets in Sender Box for this department.
    Displays outgoing tickets waiting to be pushed to Hub.
    """
    model = SenderTicket
    fk_name = 'source_dept'  # Links to the Dept acting as Sender
    fields = ('t_tag', 'query_type', 'target_dept', 'created_at', 'status')
    readonly_fields = ('t_tag', 'query_type', 'target_dept', 'created_at', 'status')
    extra = 0
    max_num = 0
    can_delete = False
    verbose_name = "Outgoing Ticket"
    verbose_name_plural = "📤 Sender Box (Waiting for Hub)"
    
    def get_queryset(self, request):
        """Filter to only show tickets in SENDER_BOX."""
        return super().get_queryset(request).filter(
            location=QueryTicket.Location.SENDER_BOX
        ).order_by('-created_at')
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


class ReceiverBoxInline(admin.TabularInline):
    """
    Inline showing tickets in Receiver Box for this department.
    Displays incoming tickets ready to be assigned.
    """
    model = ReceiverTicket
    fk_name = 'target_dept'  # Links to the Dept acting as Receiver
    fields = ('t_tag', 'query_type', 'source_dept', 'grabbed_at', 'status')
    readonly_fields = ('t_tag', 'query_type', 'source_dept', 'grabbed_at', 'status')
    extra = 0
    max_num = 0
    can_delete = False
    verbose_name = "Incoming Ticket"
    verbose_name_plural = "📥 Receiver Box (Ready to Assign)"
    
    def get_queryset(self, request):
        """Filter to only show tickets in RECEIVER_BOX."""
        return super().get_queryset(request).filter(
            location=QueryTicket.Location.RECEIVER_BOX
        ).order_by('-grabbed_at')
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


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
    
    list_display = ('code', 'display_name', 'company', 'get_member_count', 'created_at')
    list_filter = ('company',)
    search_fields = ('display_name', 'code', 'description', 'company__name')
    readonly_fields = ('created_at',)
    ordering = ('company', 'display_name')
    inlines = [DepartmentMembersInline, SenderBoxInline, ReceiverBoxInline]
    
    fieldsets = (
        ('Department Information', {
            'fields': ('company', 'display_name', 'code', 'description')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_member_count(self, obj):
        """Display count of department members."""
        return obj.employees.count()
    get_member_count.short_description = 'Members'


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
