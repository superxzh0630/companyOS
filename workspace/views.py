"""
Views for employee workspace - task management and completion.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from workflows.models import QueryTicket, QueryAttachment
from workflows.utils import generate_t_tag
from .forms import CompleteTaskForm, AttachmentUploadForm


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
