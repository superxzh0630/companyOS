from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from .models import SystemConfig, DailySequence, QueryTicket, QueryAttachment
from .services import push_to_hub, run_dept_grabber, HubOverflowError, ReceiverBoxFullError


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    """
    Admin interface for System Configuration (Singleton).
    """
    list_display = ('hub_capacity_limit', 'dept_receiving_box_limit')
    
    def has_add_permission(self, request):
        """Only allow adding if no config exists."""
        return not SystemConfig.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the singleton config."""
        return False


@admin.register(DailySequence)
class DailySequenceAdmin(admin.ModelAdmin):
    """
    Admin interface for Daily Sequence tracking.
    """
    list_display = ('date', 'sequence')
    list_filter = ('date',)
    readonly_fields = ('date', 'sequence')
    ordering = ('-date',)
    
    def has_add_permission(self, request):
        """Prevent manual addition."""
        return False


@admin.register(QueryTicket)
class QueryTicketAdmin(admin.ModelAdmin):
    """
    Admin interface for Query Tickets.
    """
    list_display = (
        't_tag',
        'title',
        'status',
        'location',
        'source_dept',
        'target_dept',
        'current_owner',
        'created_at'
    )
    list_filter = ('status', 'location', 'source_dept', 'target_dept', 'created_at')
    search_fields = ('t_tag', 'title', 'content', 'target_dept__code', 'target_dept__name')
    readonly_fields = ('t_tag', 'created_at', 'grabbed_at', 'completed_at')
    ordering = ('-created_at',)
    actions = ['push_to_hub_action', 'run_grabber_action', 'delete_selected_queries']
    autocomplete_fields = ['target_dept', 'source_dept']
    
    fieldsets = (
        ('Ticket Information', {
            'fields': ('t_tag', 'title', 'content')
        }),
        ('Status & Location', {
            'fields': ('status', 'location')
        }),
        ('Department & Ownership', {
            'fields': ('source_dept', 'target_dept', 'current_owner')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'grabbed_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Prevent manual ticket creation through admin."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete queries."""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Only superusers can change queries."""
        return request.user.is_superuser
    
    def has_view_permission(self, request, obj=None):
        """Only superusers can view queries in admin."""
        return request.user.is_superuser
    
    def get_readonly_fields(self, request, obj=None):
        """Allow superusers to edit fields while keeping timestamps readonly."""
        if request.user.is_superuser:
            return ('t_tag', 'created_at', 'grabbed_at', 'completed_at')
        return super().get_readonly_fields(request, obj)
    
    @admin.action(description='推送到大枢纽 (Push selected queries to Big Hub)')
    def push_to_hub_action(self, request, queryset):
        """Admin action to push queries from SENDER_BOX to BIG_HUB."""
        success_count = 0
        error_count = 0
        
        for query in queryset:
            try:
                push_to_hub(query)
                success_count += 1
            except (ValueError, HubOverflowError) as e:
                error_count += 1
                self.message_user(request, f"Error with {query.t_tag}: {str(e)}", level=messages.ERROR)
        
        if success_count > 0:
            self.message_user(
                request, 
                f"Successfully pushed {success_count} query(ies) to Big Hub.", 
                level=messages.SUCCESS
            )
        
        if error_count > 0:
            self.message_user(
                request,
                f"Failed to push {error_count} query(ies). See errors above.",
                level=messages.WARNING
            )
    
    @admin.action(description='运行部门抓取器 (Run department grabber for selected departments)')
    def run_grabber_action(self, request, queryset):
        """Admin action to run grabber for departments of selected queries."""
        # Get unique target department codes from selected queries
        dept_codes = queryset.values_list('target_dept__code', flat=True).distinct()
        
        success_count = 0
        error_count = 0
        
        for dept_code in dept_codes:
            try:
                grabbed_query = run_dept_grabber(dept_code)
                if grabbed_query:
                    success_count += 1
                    self.message_user(
                        request,
                        f"Department {dept_code} grabbed query {grabbed_query.t_tag}.",
                        level=messages.SUCCESS
                    )
                else:
                    self.message_user(
                        request,
                        f"No pending queries found for department {dept_code}.",
                        level=messages.INFO
                    )
            except (ReceiverBoxFullError, ValueError) as e:
                error_count += 1
                self.message_user(request, str(e), level=messages.ERROR)
        
        if success_count == 0 and error_count == 0:
            self.message_user(
                request,
                "No queries were grabbed. Check if there are pending queries in Big Hub.",
                level=messages.WARNING
            )
    
    @admin.action(description='永久删除选定的查询 (Permanently delete selected queries)')
    def delete_selected_queries(self, request, queryset):
        """Admin action to permanently delete selected query tickets."""
        if not request.user.is_superuser:
            self.message_user(
                request,
                "Only superusers can delete queries.",
                level=messages.ERROR
            )
            return
        
        # Count related attachments that will be cascaded
        attachment_count = QueryAttachment.objects.filter(query_ticket__in=queryset).count()
        query_count = queryset.count()
        
        # Perform hard delete
        deleted_queries = list(queryset.values_list('t_tag', flat=True))
        queryset.delete()
        
        # Success message
        msg = f"Successfully deleted {query_count} query ticket(s): {', '.join(deleted_queries[:5])}"
        if query_count > 5:
            msg += f" and {query_count - 5} more"
        
        if attachment_count > 0:
            msg += f" (including {attachment_count} related attachment(s))"
        
        self.message_user(request, msg, level=messages.SUCCESS)


@admin.register(QueryAttachment)
class QueryAttachmentAdmin(admin.ModelAdmin):
    """
    Admin interface for Query Attachments.
    """
    list_display = ('query_ticket', 'sequence_letter', 'original_filename', 'uploaded_by', 'uploaded_at')
    list_filter = ('uploaded_at', 'uploaded_by')
    search_fields = ('query_ticket__t_tag', 'original_filename')
    readonly_fields = ('sequence_letter', 'original_filename', 'uploaded_by', 'uploaded_at')
    
    def has_add_permission(self, request):
        """Allow adding attachments through admin."""
        return True
