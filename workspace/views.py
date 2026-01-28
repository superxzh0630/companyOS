"""
Views for employee workspace - task management and completion.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from workflows.models import (
    QueryTicket, QueryAttachment, QueryType, 
    QueryFieldDefinition, TicketAttachment
)
from workflows.utils import generate_t_tag
from profiles.models import Department
from .forms import CompleteTaskForm, AttachmentUploadForm, DynamicTicketForm


@login_required
def my_tasks(request):
    """
    Display all tasks for the current user.
    Shows: Available tasks in receiver box, assigned tasks, completed tasks.
    """
    try:
        employee_profile = request.user.employeeprofile
        user_dept = employee_profile.department
    except:
        messages.error(request, "你没有员工档案。请联系管理员。/ You don't have an employee profile. Please contact admin.")
        return redirect('index')
    
    # Available tasks in department's receiver box
    available_tasks = QueryTicket.objects.filter(
        target_dept=user_dept,
        location=QueryTicket.Location.RECEIVER_BOX,
        status=QueryTicket.Status.RECEIVED
    ).select_related('source_dept').order_by('created_at')
    
    # Tasks assigned to current user
    my_assigned_tasks = QueryTicket.objects.filter(
        current_owner=request.user,
        status=QueryTicket.Status.ASSIGNED
    ).select_related('source_dept').prefetch_related('attachments').order_by('grabbed_at')
    
    # Completed tasks by current user (last 30 days)
    my_completed_tasks = QueryTicket.objects.filter(
        current_owner=request.user,
        status=QueryTicket.Status.COMPLETED
    ).select_related('source_dept').order_by('-completed_at')[:20]
    
    context = {
        'user_dept': user_dept,
        'available_tasks': available_tasks,
        'my_assigned_tasks': my_assigned_tasks,
        'my_completed_tasks': my_completed_tasks,
    }
    
    return render(request, 'workspace/my_tasks.html', context)


@login_required
@transaction.atomic
def pick_up_task(request, ticket_id):
    """
    Pick up a task from the department's receiver box.
    Changes: location → TASK_BOX, status → ASSIGNED, current_owner → User
    """
    ticket = get_object_or_404(QueryTicket, id=ticket_id)
    
    try:
        employee_profile = request.user.employeeprofile
        user_dept = employee_profile.department
    except:
        messages.error(request, "你没有员工档案。/ You don't have an employee profile.")
        return redirect('workspace:my_tasks')
    
    # Validate ticket is in correct state
    if ticket.location != QueryTicket.Location.RECEIVER_BOX:
        messages.error(request, f"任务 {ticket.t_tag} 不在接收箱中。/ Task {ticket.t_tag} is not in receiver box.")
        return redirect('workspace:my_tasks')
    
    if ticket.status != QueryTicket.Status.RECEIVED:
        messages.error(request, f"任务 {ticket.t_tag} 状态不正确。/ Task {ticket.t_tag} has incorrect status.")
        return redirect('workspace:my_tasks')
    
    if ticket.target_dept != user_dept:
        messages.error(request, f"任务 {ticket.t_tag} 不属于你的部门。/ Task {ticket.t_tag} is not for your department.")
        return redirect('workspace:my_tasks')
    
    # Pick up the task
    ticket.location = QueryTicket.Location.TASK_BOX
    ticket.status = QueryTicket.Status.ASSIGNED
    ticket.current_owner = request.user
    ticket.save(update_fields=['location', 'status', 'current_owner'])
    
    messages.success(request, f"成功领取任务 {ticket.t_tag}！/ Successfully picked up task {ticket.t_tag}!")
    return redirect('workspace:task_detail', ticket_id=ticket.id)


@login_required
def task_detail(request, ticket_id):
    """
    Display detailed view of a task with attachments.
    """
    ticket = get_object_or_404(QueryTicket, id=ticket_id)
    
    # Check if user has access to this task
    try:
        employee_profile = request.user.employeeprofile
        user_dept = employee_profile.department
    except:
        messages.error(request, "你没有员工档案。/ You don't have an employee profile.")
        return redirect('workspace:my_tasks')
    
    # User can view if: assigned to them, or it's in their dept's receiver box
    can_view = (
        ticket.current_owner == request.user or
        (ticket.target_dept == user_dept and 
         ticket.location == QueryTicket.Location.RECEIVER_BOX)
    )
    
    if not can_view:
        messages.error(request, "你无权查看此任务。/ You don't have permission to view this task.")
        return redirect('workspace:my_tasks')
    
    # Handle attachment upload
    if request.method == 'POST' and 'upload_file' in request.POST:
        attachment_form = AttachmentUploadForm(request.POST, request.FILES)
        if attachment_form.is_valid():
            attachment = attachment_form.save(commit=False)
            attachment.query_ticket = ticket
            attachment.uploaded_by = request.user
            attachment.save()
            messages.success(request, f"文件上传成功！/ File uploaded successfully as {attachment.sequence_letter}!")
            return redirect('workspace:task_detail', ticket_id=ticket.id)
    else:
        attachment_form = AttachmentUploadForm()
    
    context = {
        'ticket': ticket,
        'attachments': ticket.attachments.all(),
        'attachment_form': attachment_form,
        'user_dept': user_dept,
    }
    
    return render(request, 'workspace/task_detail.html', context)


@login_required
@transaction.atomic
def complete_task(request, ticket_id):
    """
    Complete a task and optionally create a child query.
    """
    ticket = get_object_or_404(QueryTicket, id=ticket_id)
    
    # Validate ownership
    if ticket.current_owner != request.user:
        messages.error(request, "你无权完成此任务。/ You don't have permission to complete this task.")
        return redirect('workspace:my_tasks')
    
    if ticket.status != QueryTicket.Status.ASSIGNED:
        messages.error(request, f"任务 {ticket.t_tag} 无法完成（状态不正确）。/ Task cannot be completed (incorrect status).")
        return redirect('workspace:my_tasks')
    
    try:
        employee_profile = request.user.employeeprofile
        user_dept = employee_profile.department
    except:
        messages.error(request, "你没有员工档案。/ You don't have an employee profile.")
        return redirect('workspace:my_tasks')
    
    if request.method == 'POST':
        form = CompleteTaskForm(request.POST, user_dept=user_dept)
        if form.is_valid():
            # Complete the current task
            ticket.status = QueryTicket.Status.COMPLETED
            ticket.completed_at = timezone.now()
            ticket.save(update_fields=['status', 'completed_at'])
            
            # Create child query if requested
            if form.cleaned_data['create_child_query']:
                child_query_type = form.cleaned_data['child_query_type']
                child_target_dept = form.cleaned_data['child_target_dept']
                child_title = form.cleaned_data['child_title']
                child_content = form.cleaned_data['child_content']
                
                # Generate t_tag for child query
                child_t_tag = generate_t_tag(child_query_type, child_target_dept.code)
                
                # Create child query
                child_ticket = QueryTicket.objects.create(
                    t_tag=child_t_tag,
                    title=child_title,
                    content=f"父任务: {ticket.t_tag}\n\n{child_content}",
                    status=QueryTicket.Status.PENDING,
                    location=QueryTicket.Location.SENDER_BOX,
                    source_dept=user_dept,
                    target_dept=child_target_dept
                )
                
                messages.success(
                    request,
                    f"任务 {ticket.t_tag} 已完成！子任务 {child_ticket.t_tag} 已创建。/ "
                    f"Task {ticket.t_tag} completed! Child task {child_ticket.t_tag} created."
                )
            else:
                messages.success(request, f"任务 {ticket.t_tag} 已完成！/ Task {ticket.t_tag} completed!")
            
            return redirect('workspace:my_tasks')
    else:
        form = CompleteTaskForm(user_dept=user_dept)
    
    context = {
        'ticket': ticket,
        'form': form,
        'user_dept': user_dept,
    }
    
    return render(request, 'workspace/complete_task.html', context)


# ============================================================================
# User Workspace with Pinyin/Username URL
# ============================================================================

@login_required
def user_workspace(request, username):
    """
    User-specific workspace view with username in URL.
    Provides access to departments and query types for creating new tickets.
    
    Security: Users can only access their own workspace.
    """
    # Security Check - users can only access their own workspace
    if request.user.username != username:
        raise PermissionDenied("You cannot access another colleague's workspace.")
    
    # Get user's employee profile
    try:
        employee_profile = request.user.employeeprofile
        user_dept = employee_profile.department
    except:
        messages.error(
            request, 
            "你没有员工档案。请联系管理员。/ You don't have an employee profile. Please contact admin."
        )
        return redirect('index')
    
    # Fetch all departments for the "Select Department" dropdown
    all_departments = Department.objects.all().order_by('name')
    
    # Fetch all active query types for display
    all_query_types = QueryType.objects.filter(is_active=True).prefetch_related(
        'allowed_departments', 'fields'
    ).order_by('name')
    
    # Build a mapping of department -> available query types for frontend filtering
    dept_query_types = {}
    for dept in all_departments:
        dept_query_types[dept.code] = list(
            QueryType.objects.filter(
                is_active=True,
                allowed_departments=dept
            ).values('id', 'name', 'code', 'description')
        )
    
    # Get user's assigned tasks
    my_assigned_tasks = QueryTicket.objects.filter(
        current_owner=request.user,
        status=QueryTicket.Status.ASSIGNED
    ).select_related('source_dept', 'query_type').order_by('grabbed_at')
    
    # Get available tasks in department's receiver box
    available_tasks = QueryTicket.objects.filter(
        target_dept=user_dept,
        location=QueryTicket.Location.RECEIVER_BOX,
        status=QueryTicket.Status.RECEIVED
    ).select_related('source_dept', 'query_type').order_by('created_at')
    
    context = {
        'username': username,
        'user_dept': user_dept,
        'all_departments': all_departments,
        'all_query_types': all_query_types,
        'dept_query_types_json': dept_query_types,  # For JavaScript filtering
        'my_assigned_tasks': my_assigned_tasks,
        'available_tasks': available_tasks,
    }
    
    return render(request, 'workspace/user_workspace.html', context)


# ============================================================================
# Query Type Selection & Dynamic Ticket Creation
# ============================================================================

@login_required
@login_required
def select_query_type(request):
    """
    View A: Display available query types for the user to select.
    Shows a grid of cards with all active query types.
    """
    # Get user's employee profile
    try:
        employee_profile = request.user.employeeprofile
        user_dept = employee_profile.department
    except:
        messages.error(
            request,
            "你没有员工档案。请联系管理员。/ You don't have an employee profile. Please contact admin."
        )
        return redirect('index')
    
    # Fetch all active query types
    query_types = QueryType.objects.filter(is_active=True).prefetch_related(
        'allowed_departments', 'fields'
    ).order_by('name')
    
    context = {
        'query_types': query_types,
        'user_dept': user_dept,
    }
    
    return render(request, 'workspace/query_select.html', context)


@login_required
@transaction.atomic
def create_ticket_view(request, query_type_id, dept_code=None):
    """
    View B: Create a new ticket using dynamic form based on QueryType definition.
    Handles both regular fields (stored in content_data JSON) and 
    file fields (stored as TicketAttachment objects).
    """
    # Get the query type
    query_type = get_object_or_404(QueryType, id=query_type_id, is_active=True)
    
    # Get user's employee profile
    try:
        employee_profile = request.user.employeeprofile
        user_dept = employee_profile.department
    except:
        messages.error(
            request,
            "你没有员工档案。请联系管理员。/ You don't have an employee profile. Please contact admin."
        )
        return redirect('index')
    
    # Check if user has a department
    if not user_dept:
        messages.error(
            request,
            "你的账户未关联部门。请联系管理员。/ Your account is not linked to a department. Please contact admin."
        )
        return redirect('index')
    
    # Get allowed departments for this query type
    allowed_depts = query_type.allowed_departments.all()
    
    if request.method == 'POST':
        form = DynamicTicketForm(
            data=request.POST,
            files=request.FILES,
            query_type=query_type
        )
        
        if form.is_valid():
            # Extract target department from form (routing)
            target_dept = form.cleaned_data['target_department']
            
            # Generate t_tag using query type code and target department code
            t_tag = generate_t_tag(query_type.code, target_dept.code)
            
            # Separate file fields from regular fields (Data Separation)
            content_data = {}
            file_fields = {}
            
            # Get field definitions for lookup
            field_definitions = {fd.field_key: fd for fd in query_type.fields.all()}
            
            for field_key, value in form.cleaned_data.items():
                # Skip the routing field and standard fields
                if field_key in ('target_department', 'title', 'description'):
                    continue
                
                # Get the field definition
                field_def = field_definitions.get(field_key)
                if not field_def:
                    continue
                
                # Check if this is a FILE type field
                if field_def.field_type == QueryFieldDefinition.FieldType.FILE:
                    if value:  # File was uploaded
                        file_fields[field_key] = (value, field_def)
                else:
                    # Convert non-serializable types for JSON
                    if value is not None:
                        if hasattr(value, 'isoformat'):  # Date/datetime
                            content_data[field_key] = value.isoformat()
                        elif hasattr(value, '__float__'):  # Decimal
                            content_data[field_key] = float(value)
                        else:
                            content_data[field_key] = value
            
            # Create the ticket
            ticket = QueryTicket.objects.create(
                t_tag=t_tag,
                title=form.cleaned_data.get('title', f"{query_type.name} - {t_tag}"),
                content=form.cleaned_data.get('description', ''),
                query_type=query_type,
                content_data=content_data,
                status=QueryTicket.Status.PENDING,
                location=QueryTicket.Location.SENDER_BOX,
                source_dept=user_dept,
                target_dept=target_dept,
                current_owner=request.user
            )
            
            # Create file attachments for each FILE field
            for field_key, (file_obj, field_def) in file_fields.items():
                TicketAttachment.objects.create(
                    ticket=ticket,
                    field_definition=field_def,
                    file=file_obj
                )
            
            messages.success(
                request,
                f"工单 {t_tag} 创建成功！已放入发送箱。/ Ticket {t_tag} created successfully! Placed in sender box."
            )
            return redirect('workspace:my_tasks')
    else:
        form = DynamicTicketForm(query_type=query_type)
    
    context = {
        'query_type': query_type,
        'form': form,
        'allowed_depts': allowed_depts,
        'user_dept': user_dept,
    }
    
    return render(request, 'workspace/query_create.html', context)
