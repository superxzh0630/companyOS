"""
Dashboard views for monitoring workflow system.
Provides Global Hub, Department, and Admin Monitor views.
"""
import json
from datetime import timedelta
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.db.models import Count, Q
from workflows.models import QueryTicket, SystemConfig
from profiles.models import Department


# ============================================================================
# Global Big Hub Dashboard
# ============================================================================

def global_hub_dashboard(request):
    """
    Global dashboard showing all queries in BIG_HUB.
    Implements the 5-Minute Ghost Rule: includes recently grabbed queries.
    """
    config = SystemConfig.get_config()
    five_minutes_ago = timezone.now() - timedelta(minutes=5)
    
    # Get all queries in BIG_HUB
    hub_queries = QueryTicket.objects.filter(
        location=QueryTicket.Location.BIG_HUB
    ).select_related('source_dept').order_by('created_at')
    
    # Get "ghost" queries - grabbed within last 5 minutes
    ghost_queries = QueryTicket.objects.filter(
        location=QueryTicket.Location.RECEIVER_BOX,
        grabbed_at__gte=five_minutes_ago
    ).select_related('source_dept').order_by('-grabbed_at')
    
    # Mark ghost queries with a flag
    ghost_ids = set(ghost_queries.values_list('id', flat=True))
    
    # Combine queries for display
    all_queries = []
    for query in hub_queries:
        all_queries.append({
            'ticket': query,
            'is_ghost': False
        })
    for query in ghost_queries:
        all_queries.append({
            'ticket': query,
            'is_ghost': True
        })
    
    # Calculate hub capacity
    hub_count = hub_queries.count()
    hub_capacity = config.hub_capacity_limit
    hub_percentage = (hub_count / hub_capacity * 100) if hub_capacity > 0 else 0
    
    context = {
        'all_queries': all_queries,
        'hub_count': hub_count,
        'ghost_count': ghost_queries.count(),
        'hub_capacity': hub_capacity,
        'hub_percentage': min(hub_percentage, 100),
        'config': config,
    }
    
    return render(request, 'dashboard/global_hub.html', context)


def global_hub_api(request):
    """
    JSON API for Global Hub Dashboard.
    Returns all BIG_HUB queries plus ghost queries.
    """
    config = SystemConfig.get_config()
    five_minutes_ago = timezone.now() - timedelta(minutes=5)
    
    # Get all queries in BIG_HUB
    hub_queries = QueryTicket.objects.filter(
        location=QueryTicket.Location.BIG_HUB
    ).select_related('source_dept').order_by('created_at')
    
    # Get ghost queries
    ghost_queries = QueryTicket.objects.filter(
        location=QueryTicket.Location.RECEIVER_BOX,
        grabbed_at__gte=five_minutes_ago
    ).select_related('source_dept').order_by('-grabbed_at')
    
    def serialize_ticket(ticket, is_ghost=False):
        return {
            'id': ticket.id,
            't_tag': ticket.t_tag,
            'title': ticket.title,
            'status': ticket.status,
            'location': ticket.location,
            'source_dept': ticket.source_dept.code if ticket.source_dept else None,
            'source_dept_name': ticket.source_dept.name if ticket.source_dept else None,
            'target_dept': ticket.target_dept.code if ticket.target_dept else None,
            'target_dept_name': ticket.target_dept.name if ticket.target_dept else None,
            'created_at': ticket.created_at.isoformat(),
            'grabbed_at': ticket.grabbed_at.isoformat() if ticket.grabbed_at else None,
            'is_ghost': is_ghost,
        }
    
    data = {
        'hub_queries': [serialize_ticket(q, False) for q in hub_queries],
        'ghost_queries': [serialize_ticket(q, True) for q in ghost_queries],
        'hub_count': hub_queries.count(),
        'ghost_count': ghost_queries.count(),
        'hub_capacity': config.hub_capacity_limit,
        'hub_percentage': (hub_queries.count() / config.hub_capacity_limit * 100) if config.hub_capacity_limit > 0 else 0,
        'timestamp': timezone.now().isoformat(),
    }
    
    return JsonResponse(data)


# ============================================================================
# Smart Router - Dashboard Dispatcher
# ============================================================================

@login_required
def dashboard_router(request):
    """
    Smart dispatcher that routes users to the appropriate dashboard.
    - Admins/Superusers -> Admin Department Selector
    - Employees with profile -> Their department dashboard
    - No profile -> Friendly error page
    """
    # Check 1: Admin/Superuser
    if request.user.is_superuser:
        return redirect('dashboard:admin_dept_selector')
    
    # Check 2: Employee with profile and department
    if hasattr(request.user, 'employeeprofile'):
        employee_profile = request.user.employeeprofile
        if employee_profile.department:
            return redirect('dashboard:department', dept_code=employee_profile.department.code)
        else:
            return render(request, 'dashboard/no_access.html', {
                'message': 'Your profile is not linked to a department.',
                'message_cn': '您的档案未关联任何部门。',
            })
    
    # Check 3: No profile - fallback error
    return render(request, 'dashboard/no_access.html', {
        'message': 'Account not linked to Department. Please contact IT.',
        'message_cn': '账户未关联部门，请联系IT部门。',
    })


# ============================================================================
# Admin Department Selector
# ============================================================================

@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='index')
def admin_dept_selector(request):
    """
    Admin-only view to select which department dashboard to view.
    """
    departments = Department.objects.all().order_by('name')
    
    context = {
        'departments': departments,
    }
    
    return render(request, 'dashboard/admin_dept_selector.html', context)


# ============================================================================
# Department Dashboard
# ============================================================================

@login_required
def department_dashboard(request, dept_code=None):
    """
    Department-specific dashboard showing RECEIVER_BOX and SENDER_BOX.
    If no dept_code provided, uses logged-in user's department.
    
    Security: Only superusers or employees of the department can access.
    """
    config = SystemConfig.get_config()
    
    # Get department
    if dept_code:
        try:
            department = Department.objects.get(code=dept_code)
        except Department.DoesNotExist:
            return render(request, 'dashboard/error.html', {
                'message': f'Department {dept_code} not found.'
            })
    else:
        # Use user's department
        if hasattr(request.user, 'employeeprofile') and request.user.employeeprofile.department:
            department = request.user.employeeprofile.department
        else:
            return render(request, 'dashboard/no_access.html', {
                'message': 'You do not have an employee profile with a department.',
                'message_cn': '您没有与部门关联的员工档案。',
            })
    
    # === SECURITY GUARD ===
    # Allow if superuser (God Mode)
    if request.user.is_superuser:
        pass  # Access granted
    # Allow if employee belongs to this department
    elif hasattr(request.user, 'employeeprofile') and request.user.employeeprofile.department:
        if request.user.employeeprofile.department.code != department.code:
            raise PermissionDenied("You do not have permission to view this department's dashboard.")
    # Block everyone else
    else:
        raise PermissionDenied("Access denied. You do not have an employee profile.")
    
    # Get RECEIVER_BOX queries for this department
    receiver_queries = QueryTicket.objects.filter(
        target_dept=department,
        location=QueryTicket.Location.RECEIVER_BOX
    ).select_related('source_dept').order_by('grabbed_at')
    
    # Get SENDER_BOX queries from this department
    sender_queries = QueryTicket.objects.filter(
        source_dept=department,
        location=QueryTicket.Location.SENDER_BOX
    ).order_by('created_at')
    
    # Get in-progress tasks for this department
    in_progress_queries = QueryTicket.objects.filter(
        target_dept=department,
        location=QueryTicket.Location.TASK_BOX,
        status=QueryTicket.Status.ASSIGNED
    ).select_related('source_dept', 'current_owner').order_by('grabbed_at')
    
    # Calculate capacities
    receiver_count = receiver_queries.count()
    receiver_capacity = config.dept_receiving_box_limit
    receiver_percentage = (receiver_count / receiver_capacity * 100) if receiver_capacity > 0 else 0
    
    context = {
        'department': department,
        'receiver_queries': receiver_queries,
        'sender_queries': sender_queries,
        'in_progress_queries': in_progress_queries,
        'receiver_count': receiver_count,
        'sender_count': sender_queries.count(),
        'in_progress_count': in_progress_queries.count(),
        'receiver_capacity': receiver_capacity,
        'receiver_percentage': min(receiver_percentage, 100),
        'config': config,
    }
    
    return render(request, 'dashboard/department.html', context)


@login_required
def department_api(request, dept_code):
    """
    JSON API for Department Dashboard.
    """
    config = SystemConfig.get_config()
    
    try:
        department = Department.objects.get(code=dept_code)
    except Department.DoesNotExist:
        return JsonResponse({'error': f'Department {dept_code} not found.'}, status=404)
    
    # Check access
    try:
        user_dept = request.user.employeeprofile.department
        if user_dept.code != dept_code and not request.user.is_staff:
            return JsonResponse({'error': 'Access denied.'}, status=403)
    except:
        if not request.user.is_staff:
            return JsonResponse({'error': 'No employee profile.'}, status=403)
    
    # Get queries
    receiver_queries = QueryTicket.objects.filter(
        target_dept=department,
        location=QueryTicket.Location.RECEIVER_BOX
    ).select_related('source_dept').order_by('grabbed_at')
    
    sender_queries = QueryTicket.objects.filter(
        source_dept=department,
        location=QueryTicket.Location.SENDER_BOX
    ).order_by('created_at')
    
    def serialize_ticket(ticket):
        return {
            'id': ticket.id,
            't_tag': ticket.t_tag,
            'title': ticket.title,
            'status': ticket.status,
            'location': ticket.location,
            'source_dept': ticket.source_dept.code if ticket.source_dept else None,
            'target_dept': ticket.target_dept.code if ticket.target_dept else None,
            'created_at': ticket.created_at.isoformat(),
            'grabbed_at': ticket.grabbed_at.isoformat() if ticket.grabbed_at else None,
        }
    
    receiver_count = receiver_queries.count()
    
    data = {
        'department': {
            'code': department.code,
            'name': department.name,
        },
        'receiver_box': {
            'queries': [serialize_ticket(q) for q in receiver_queries],
            'count': receiver_count,
            'capacity': config.dept_receiving_box_limit,
            'percentage': (receiver_count / config.dept_receiving_box_limit * 100) if config.dept_receiving_box_limit > 0 else 0,
        },
        'sender_box': {
            'queries': [serialize_ticket(q) for q in sender_queries],
            'count': sender_queries.count(),
        },
        'timestamp': timezone.now().isoformat(),
    }
    
    return JsonResponse(data)


# ============================================================================
# Admin Monitor
# ============================================================================

@staff_member_required
def admin_monitor(request):
    """
    Admin monitor showing fullness % of Hub and all Department Boxes.
    """
    config = SystemConfig.get_config()
    
    # Hub stats
    hub_count = QueryTicket.objects.filter(
        location=QueryTicket.Location.BIG_HUB
    ).count()
    hub_capacity = config.hub_capacity_limit
    hub_percentage = (hub_count / hub_capacity * 100) if hub_capacity > 0 else 0
    
    # Get all departments and their box stats
    departments = Department.objects.all().order_by('code')
    dept_stats = []
    
    for dept in departments:
        receiver_count = QueryTicket.objects.filter(
            target_dept=dept,
            location=QueryTicket.Location.RECEIVER_BOX
        ).count()
        
        sender_count = QueryTicket.objects.filter(
            source_dept=dept,
            location=QueryTicket.Location.SENDER_BOX
        ).count()
        
        task_count = QueryTicket.objects.filter(
            target_dept=dept,
            location=QueryTicket.Location.TASK_BOX
        ).count()
        
        receiver_percentage = (receiver_count / config.dept_receiving_box_limit * 100) if config.dept_receiving_box_limit > 0 else 0
        
        dept_stats.append({
            'department': dept,
            'receiver_count': receiver_count,
            'sender_count': sender_count,
            'task_count': task_count,
            'receiver_capacity': config.dept_receiving_box_limit,
            'receiver_percentage': min(receiver_percentage, 100),
        })
    
    # Overall stats
    total_queries = QueryTicket.objects.count()
    pending_queries = QueryTicket.objects.filter(status=QueryTicket.Status.PENDING).count()
    completed_queries = QueryTicket.objects.filter(status=QueryTicket.Status.COMPLETED).count()
    
    context = {
        'hub_count': hub_count,
        'hub_capacity': hub_capacity,
        'hub_percentage': min(hub_percentage, 100),
        'dept_stats': dept_stats,
        'total_queries': total_queries,
        'pending_queries': pending_queries,
        'completed_queries': completed_queries,
        'config': config,
    }
    
    return render(request, 'dashboard/admin_monitor.html', context)


@staff_member_required
def admin_monitor_api(request):
    """
    JSON API for Admin Monitor.
    """
    config = SystemConfig.get_config()
    
    # Hub stats
    hub_count = QueryTicket.objects.filter(
        location=QueryTicket.Location.BIG_HUB
    ).count()
    
    # Department stats
    departments = Department.objects.all().order_by('code')
    dept_stats = []
    
    for dept in departments:
        receiver_count = QueryTicket.objects.filter(
            target_dept=dept,
            location=QueryTicket.Location.RECEIVER_BOX
        ).count()
        
        sender_count = QueryTicket.objects.filter(
            source_dept=dept,
            location=QueryTicket.Location.SENDER_BOX
        ).count()
        
        task_count = QueryTicket.objects.filter(
            target_dept=dept,
            location=QueryTicket.Location.TASK_BOX
        ).count()
        
        dept_stats.append({
            'code': dept.code,
            'name': dept.name,
            'receiver_count': receiver_count,
            'sender_count': sender_count,
            'task_count': task_count,
            'receiver_capacity': config.dept_receiving_box_limit,
            'receiver_percentage': (receiver_count / config.dept_receiving_box_limit * 100) if config.dept_receiving_box_limit > 0 else 0,
        })
    
    data = {
        'hub': {
            'count': hub_count,
            'capacity': config.hub_capacity_limit,
            'percentage': (hub_count / config.hub_capacity_limit * 100) if config.hub_capacity_limit > 0 else 0,
        },
        'departments': dept_stats,
        'totals': {
            'total_queries': QueryTicket.objects.count(),
            'pending': QueryTicket.objects.filter(status=QueryTicket.Status.PENDING).count(),
            'received': QueryTicket.objects.filter(status=QueryTicket.Status.RECEIVED).count(),
            'assigned': QueryTicket.objects.filter(status=QueryTicket.Status.ASSIGNED).count(),
            'completed': QueryTicket.objects.filter(status=QueryTicket.Status.COMPLETED).count(),
        },
        'timestamp': timezone.now().isoformat(),
    }
    
    return JsonResponse(data)
