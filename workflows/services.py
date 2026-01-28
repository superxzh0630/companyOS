"""
Workflow services for handling query ticket flow through the system.
"""
from django.db import transaction
from django.utils import timezone
from .models import QueryTicket, SystemConfig
from profiles.models import Department


class HubOverflowError(Exception):
    """Raised when the Big Hub is at capacity."""
    pass


class ReceiverBoxFullError(Exception):
    """Raised when a department's receiver box is at capacity."""
    pass


@transaction.atomic
def push_to_hub(query_ticket):
    """
    Push a query from SENDER_BOX to BIG_HUB.
    
    Args:
        query_ticket: QueryTicket instance currently in SENDER_BOX
        
    Raises:
        ValueError: If query is not in SENDER_BOX
        HubOverflowError: If BIG_HUB is at capacity
    """
    # Validate current location
    if query_ticket.location != QueryTicket.Location.SENDER_BOX:
        raise ValueError(f"Query {query_ticket.t_tag} is not in SENDER_BOX (current: {query_ticket.location})")
    
    # Get system configuration
    config = SystemConfig.get_config()
    
    # Check hub capacity
    hub_count = QueryTicket.objects.filter(location=QueryTicket.Location.BIG_HUB).count()
    if hub_count >= config.hub_capacity_limit:
        raise HubOverflowError(
            f"Big Hub is at capacity ({hub_count}/{config.hub_capacity_limit}). "
            f"Query {query_ticket.t_tag} must wait in SENDER_BOX."
        )
    
    # Move to BIG_HUB
    query_ticket.location = QueryTicket.Location.BIG_HUB
    query_ticket.status = QueryTicket.Status.PENDING
    query_ticket.save(update_fields=['location', 'status'])
    
    return query_ticket


@transaction.atomic
def run_dept_grabber(dept_code):
    """
    Grab the oldest pending query from BIG_HUB for a specific department.
    
    Args:
        dept_code: Target department code (e.g., 'PD', 'HRTJ')
        
    Returns:
        QueryTicket instance if successfully grabbed, None if no space or no queries
        
    Raises:
        ReceiverBoxFullError: If department's receiver box is at capacity
        ValueError: If department code is invalid
    """
    # Get department by code
    try:
        department = Department.objects.get(code=dept_code)
    except Department.DoesNotExist:
        raise ValueError(f"Department with code '{dept_code}' does not exist.")
    
    # Get system configuration
    config = SystemConfig.get_config()
    
    # Check receiver box capacity for this department
    receiver_count = QueryTicket.objects.filter(
        target_dept=department,
        location=QueryTicket.Location.RECEIVER_BOX
    ).count()
    
    if receiver_count >= config.dept_receiving_box_limit:
        raise ReceiverBoxFullError(
            f"Department {dept_code}'s receiver box is full "
            f"({receiver_count}/{config.dept_receiving_box_limit}). "
            f"Cannot grab new queries."
        )
    
    # Find the oldest PENDING query in BIG_HUB for this department
    query_ticket = QueryTicket.objects.select_for_update().filter(
        target_dept=department,
        location=QueryTicket.Location.BIG_HUB,
        status=QueryTicket.Status.PENDING
    ).order_by('created_at').first()
    
    if not query_ticket:
        # No queries available for this department
        return None
    
    # Move to RECEIVER_BOX
    query_ticket.location = QueryTicket.Location.RECEIVER_BOX
    query_ticket.status = QueryTicket.Status.RECEIVED
    query_ticket.grabbed_at = timezone.now()
    query_ticket.save(update_fields=['location', 'status', 'grabbed_at'])
    
    return query_ticket


@transaction.atomic
def assign_to_user(query_ticket, user):
    """
    Assign a query from RECEIVER_BOX to a specific user's TASK_BOX.
    
    Args:
        query_ticket: QueryTicket instance currently in RECEIVER_BOX
        user: User instance to assign the query to
        
    Raises:
        ValueError: If query is not in RECEIVER_BOX or already assigned
    """
    if query_ticket.location != QueryTicket.Location.RECEIVER_BOX:
        raise ValueError(
            f"Query {query_ticket.t_tag} is not in RECEIVER_BOX (current: {query_ticket.location})"
        )
    
    if query_ticket.current_owner is not None:
        raise ValueError(
            f"Query {query_ticket.t_tag} is already assigned to {query_ticket.current_owner.username}"
        )
    
    # Assign to user
    query_ticket.location = QueryTicket.Location.TASK_BOX
    query_ticket.status = QueryTicket.Status.ASSIGNED
    query_ticket.current_owner = user
    query_ticket.save(update_fields=['location', 'status', 'current_owner'])
    
    return query_ticket


@transaction.atomic
def complete_query(query_ticket):
    """
    Mark a query as completed.
    
    Args:
        query_ticket: QueryTicket instance to complete
        
    Raises:
        ValueError: If query is not assigned to someone
    """
    if query_ticket.status != QueryTicket.Status.ASSIGNED:
        raise ValueError(
            f"Query {query_ticket.t_tag} cannot be completed (current status: {query_ticket.status})"
        )
    
    if query_ticket.current_owner is None:
        raise ValueError(
            f"Query {query_ticket.t_tag} is not assigned to anyone"
        )
    
    # Mark as completed
    query_ticket.status = QueryTicket.Status.COMPLETED
    query_ticket.completed_at = timezone.now()
    query_ticket.save(update_fields=['status', 'completed_at'])
    
    return query_ticket


# ============================================================================
# Logistics Engine Functions (15-Second Background Cycles)
# ============================================================================

@transaction.atomic
def run_sender_cycle():
    """
    Push tickets from SENDER_BOX to BIG_HUB while respecting capacity.
    
    Logic:
    1. Get hub_limit from SystemConfig
    2. Count current BIG_HUB items
    3. If current < limit: Move oldest SENDER_BOX tickets to BIG_HUB
    
    Returns:
        dict: Summary of moved tickets
    """
    config = SystemConfig.get_config()
    hub_limit = config.hub_capacity_limit
    
    # Count current items in BIG_HUB
    hub_count = QueryTicket.objects.filter(
        location=QueryTicket.Location.BIG_HUB
    ).count()
    
    # Calculate available capacity
    available_capacity = hub_limit - hub_count
    
    if available_capacity <= 0:
        return {
            'moved': 0,
            'hub_count': hub_count,
            'hub_limit': hub_limit,
            'message': 'Hub is at capacity'
        }
    
    # Get oldest tickets in SENDER_BOX (up to available capacity)
    sender_tickets = QueryTicket.objects.select_for_update().filter(
        location=QueryTicket.Location.SENDER_BOX,
        status=QueryTicket.Status.PENDING
    ).order_by('created_at')[:available_capacity]
    
    moved_count = 0
    for ticket in sender_tickets:
        ticket.location = QueryTicket.Location.BIG_HUB
        ticket.status = QueryTicket.Status.PENDING
        ticket.save(update_fields=['location', 'status'])
        moved_count += 1
    
    return {
        'moved': moved_count,
        'hub_count': hub_count + moved_count,
        'hub_limit': hub_limit,
        'message': f'Moved {moved_count} ticket(s) to Hub'
    }


@transaction.atomic
def run_grabber_cycle():
    """
    Move tickets from BIG_HUB to RECEIVER_BOX for each department.
    
    Logic:
    1. Get dept_limit from SystemConfig
    2. Loop through all departments
    3. For each dept: Move oldest BIG_HUB tickets to RECEIVER_BOX if space
    
    Returns:
        dict: Summary of moved tickets per department
    """
    config = SystemConfig.get_config()
    dept_limit = config.dept_receiving_box_limit
    
    # Get all departments
    departments = Department.objects.all()
    
    results = {}
    total_moved = 0
    
    for dept in departments:
        # Count current items in department's RECEIVER_BOX
        receiver_count = QueryTicket.objects.filter(
            target_dept=dept,
            location=QueryTicket.Location.RECEIVER_BOX
        ).count()
        
        # Calculate available capacity
        available_capacity = dept_limit - receiver_count
        
        if available_capacity <= 0:
            results[dept.code] = {
                'moved': 0,
                'receiver_count': receiver_count,
                'message': 'Receiver box is full'
            }
            continue
        
        # Find oldest BIG_HUB tickets targeted for this department
        hub_tickets = QueryTicket.objects.select_for_update().filter(
            target_dept=dept,
            location=QueryTicket.Location.BIG_HUB,
            status=QueryTicket.Status.PENDING
        ).order_by('created_at')[:available_capacity]
        
        moved_count = 0
        for ticket in hub_tickets:
            ticket.location = QueryTicket.Location.RECEIVER_BOX
            ticket.status = QueryTicket.Status.RECEIVED
            ticket.grabbed_at = timezone.now()
            ticket.save(update_fields=['location', 'status', 'grabbed_at'])
            moved_count += 1
        
        results[dept.code] = {
            'moved': moved_count,
            'receiver_count': receiver_count + moved_count,
            'message': f'Moved {moved_count} ticket(s)' if moved_count > 0 else 'No pending tickets'
        }
        total_moved += moved_count
    
    return {
        'total_moved': total_moved,
        'dept_limit': dept_limit,
        'department_results': results
    }
