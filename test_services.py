"""
Test script for workflow services.
Run with: python manage.py shell < test_services.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from workflows.models import QueryTicket, SystemConfig
from workflows.services import push_to_hub, run_dept_grabber, HubOverflowError, ReceiverBoxFullError
from profiles.models import Department, Company
from django.contrib.auth.models import User

print("\n=== Testing Workflow Services ===\n")

# Ensure SystemConfig exists
config, created = SystemConfig.objects.get_or_create(
    id=1,
    defaults={
        'hub_capacity_limit': 5,  # Small limit for testing
        'dept_receiving_box_limit': 3
    }
)
print(f"SystemConfig: Hub limit = {config.hub_capacity_limit}, Receiver limit = {config.dept_receiving_box_limit}")

# Get or create test company
company, _ = Company.objects.get_or_create(
    city_code='TEST',
    defaults={
        'name': 'Test Company',
        'city_name': 'Test City'
    }
)
print(f"\nTest Company: {company.name}")

# Get or create test department and user
dept, _ = Department.objects.get_or_create(
    code='PD',
    defaults={
        'company': company,
        'name': 'Purchasing Department',
        'display_name': 'Purchasing Department'
    }
)
user, _ = User.objects.get_or_create(username='testuser', defaults={'email': 'test@example.com'})

print(f"\nTest Department: {dept.code} - {dept.name}")

# Clean up any existing test tickets
QueryTicket.objects.filter(t_tag__startswith='TEST-').delete()
print("\nCleaned up existing test tickets")

# Create test tickets in SENDER_BOX
from workflows.utils import generate_t_tag

test_tickets = []
for i in range(3):
    t_tag = f"TEST-PD-260122-{str(i+1).zfill(3)}"
    ticket = QueryTicket.objects.create(
        t_tag=t_tag,
        title=f"Test Query {i+1}",
        content=f"Test content for query {i+1}",
        status=QueryTicket.Status.PENDING,
        location=QueryTicket.Location.SENDER_BOX,
        source_dept=dept,
        target_dept=dept
    )
    test_tickets.append(ticket)
    print(f"Created: {ticket.t_tag} in {ticket.location}")

# Test 1: Push queries to hub
print("\n--- Test 1: Push to Hub ---")
for ticket in test_tickets[:2]:  # Push first 2
    try:
        result = push_to_hub(ticket)
        print(f"✓ Pushed {result.t_tag} to {result.location}, status: {result.status}")
    except HubOverflowError as e:
        print(f"✗ {e}")

# Verify hub count
hub_count = QueryTicket.objects.filter(location=QueryTicket.Location.BIG_HUB).count()
print(f"\nBig Hub count: {hub_count}")

# Test 2: Run department grabber
print("\n--- Test 2: Run Department Grabber ---")
try:
    grabbed = run_dept_grabber('PD')
    if grabbed:
        print(f"✓ Grabbed {grabbed.t_tag} for dept PD")
        print(f"  Location: {grabbed.location}, Status: {grabbed.status}")
        print(f"  Grabbed at: {grabbed.grabbed_at}")
    else:
        print("No queries to grab")
except ReceiverBoxFullError as e:
    print(f"✗ {e}")

# Verify locations
sender_count = QueryTicket.objects.filter(t_tag__startswith='TEST-', location=QueryTicket.Location.SENDER_BOX).count()
hub_count = QueryTicket.objects.filter(t_tag__startswith='TEST-', location=QueryTicket.Location.BIG_HUB).count()
receiver_count = QueryTicket.objects.filter(t_tag__startswith='TEST-', location=QueryTicket.Location.RECEIVER_BOX).count()

print(f"\n--- Final Status ---")
print(f"SENDER_BOX: {sender_count} tickets")
print(f"BIG_HUB: {hub_count} tickets")
print(f"RECEIVER_BOX: {receiver_count} tickets")

# Test 3: Test capacity limits
print("\n--- Test 3: Test Capacity Limits ---")

# Try to overflow the hub
remaining_ticket = test_tickets[2]
print(f"Attempting to push {remaining_ticket.t_tag}...")

# First, fill the hub to capacity
while QueryTicket.objects.filter(location=QueryTicket.Location.BIG_HUB).count() < config.hub_capacity_limit:
    extra_tag = f"EXTRA-PD-260122-{str(QueryTicket.objects.count()+1).zfill(3)}"
    extra_ticket = QueryTicket.objects.create(
        t_tag=extra_tag,
        title="Extra Query",
        content="Extra content",
        status=QueryTicket.Status.PENDING,
        location=QueryTicket.Location.SENDER_BOX,
        source_dept=dept,
        target_dept=dept
    )
    push_to_hub(extra_ticket)
    print(f"Filled hub: {extra_ticket.t_tag}")

# Now try to push when hub is full
hub_count = QueryTicket.objects.filter(location=QueryTicket.Location.BIG_HUB).count()
print(f"\nHub is now at capacity: {hub_count}/{config.hub_capacity_limit}")

try:
    push_to_hub(remaining_ticket)
    print("✗ Should have raised HubOverflowError!")
except HubOverflowError as e:
    print(f"✓ Correctly raised error: {e}")

print("\n=== Test Complete ===\n")
