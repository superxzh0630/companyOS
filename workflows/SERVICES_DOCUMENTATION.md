# Workflows Service Layer Documentation

## Overview
The `services.py` module implements the flow logic for moving query tickets through the system. It handles the physical movement of tickets between different locations (boxes) while enforcing capacity constraints.

## Architecture

### Flow Diagram
```
SENDER_BOX → BIG_HUB → RECEIVER_BOX → TASK_BOX
    ↓            ↓           ↓           ↓
 (Push)     (Grabber)   (Assign)    (Complete)
```

### Status Transitions
```
PENDING → RECEIVED → ASSIGNED → COMPLETED
```

## Custom Exceptions

### HubOverflowError
Raised when the Big Hub is at capacity and cannot accept more queries.

### ReceiverBoxFullError
Raised when a department's receiver box is at capacity and cannot grab more queries.

## Core Functions

### 1. push_to_hub(query_ticket)

**Purpose**: Push a query from SENDER_BOX to BIG_HUB

**Input**: 
- `query_ticket`: QueryTicket instance currently in SENDER_BOX

**Process**:
1. Validates query is in SENDER_BOX
2. Checks if BIG_HUB has space (count < hub_capacity_limit)
3. If space available:
   - Updates location to BIG_HUB
   - Updates status to PENDING
4. If no space:
   - Raises HubOverflowError

**Raises**:
- `ValueError`: If query is not in SENDER_BOX
- `HubOverflowError`: If BIG_HUB is at capacity

**Transaction Safety**: Uses `@transaction.atomic`

**Example**:
```python
from workflows.models import QueryTicket
from workflows.services import push_to_hub, HubOverflowError

ticket = QueryTicket.objects.get(t_tag='QGD-PD-260122-001')
try:
    result = push_to_hub(ticket)
    print(f"Pushed to {result.location}")
except HubOverflowError as e:
    print(f"Hub full: {e}")
```

### 2. run_dept_grabber(dept_code)

**Purpose**: Grab the oldest pending query from BIG_HUB for a specific department

**Input**:
- `dept_code`: Target department code (e.g., 'PD', 'HRTJ')

**Process**:
1. Checks if department's RECEIVER_BOX has space (count < dept_receiving_box_limit)
2. If space available:
   - Finds oldest PENDING query in BIG_HUB for this department
   - Updates location to RECEIVER_BOX
   - Updates status to RECEIVED
   - Sets grabbed_at timestamp
3. If no space:
   - Raises ReceiverBoxFullError
4. If no queries available:
   - Returns None

**Returns**:
- QueryTicket instance if successfully grabbed
- None if no queries available

**Raises**:
- `ReceiverBoxFullError`: If department's receiver box is at capacity

**Transaction Safety**: Uses `@transaction.atomic` and `select_for_update()` for row locking

**Example**:
```python
from workflows.services import run_dept_grabber, ReceiverBoxFullError

try:
    grabbed = run_dept_grabber('PD')
    if grabbed:
        print(f"Grabbed {grabbed.t_tag}")
    else:
        print("No queries available")
except ReceiverBoxFullError as e:
    print(f"Receiver box full: {e}")
```

### 3. assign_to_user(query_ticket, user)

**Purpose**: Assign a query from RECEIVER_BOX to a specific user's TASK_BOX

**Input**:
- `query_ticket`: QueryTicket instance currently in RECEIVER_BOX
- `user`: User instance to assign the query to

**Process**:
1. Validates query is in RECEIVER_BOX
2. Validates query is not already assigned
3. Updates location to TASK_BOX
4. Updates status to ASSIGNED
5. Sets current_owner to user

**Raises**:
- `ValueError`: If query is not in RECEIVER_BOX or already assigned

**Transaction Safety**: Uses `@transaction.atomic`

### 4. complete_query(query_ticket)

**Purpose**: Mark a query as completed

**Input**:
- `query_ticket`: QueryTicket instance to complete

**Process**:
1. Validates query status is ASSIGNED
2. Validates query has a current_owner
3. Updates status to COMPLETED
4. Sets completed_at timestamp

**Raises**:
- `ValueError`: If query is not assigned or has no owner

**Transaction Safety**: Uses `@transaction.atomic`

## Admin Integration

### Admin Actions

The admin panel includes two custom actions for testing the services:

#### 1. "推送到大枢纽 (Push selected queries to Big Hub)"
- Select one or more queries in SENDER_BOX
- Click action to push them to BIG_HUB
- Shows success/error messages for each query

#### 2. "运行部门抓取器 (Run department grabber for selected departments)"
- Select one or more queries (looks at their target_dept_code)
- Click action to run grabber for those departments
- Each department grabs one query from BIG_HUB
- Shows success/error messages for each department

### Admin Panel Usage

1. Navigate to: http://localhost:8000/admin/workflows/queryticket/
2. Filter by location to see queries in different boxes
3. Select queries and choose action from dropdown
4. Click "Go" to execute

## Capacity Limits

Limits are configured in SystemConfig:

- `hub_capacity_limit`: Maximum queries in BIG_HUB (default: 100)
- `dept_receiving_box_limit`: Maximum queries per department in RECEIVER_BOX (default: 50)

To modify limits:
1. Go to: http://localhost:8000/admin/workflows/systemconfig/
2. Edit the single configuration record
3. Save changes

## Testing

### Manual Testing Steps

1. **Create a test query**:
```python
# In Django shell
from workflows.models import QueryTicket
from profiles.models import Department

dept = Department.objects.first()
ticket = QueryTicket.objects.create(
    t_tag="TEST-PD-260122-001",
    title="Test Query",
    content="Test content",
    status=QueryTicket.Status.PENDING,
    location=QueryTicket.Location.SENDER_BOX,
    source_dept=dept,
    target_dept_code='PD'
)
```

2. **Test push_to_hub**:
   - Go to admin panel
   - Select the query
   - Use "Push to Big Hub" action

3. **Test run_dept_grabber**:
   - Ensure query is in BIG_HUB
   - Use "Run department grabber" action

### Capacity Testing

To test capacity limits:

1. Set low limits in SystemConfig (e.g., hub_capacity_limit=2)
2. Create 3 queries in SENDER_BOX
3. Try to push all 3 - the third should fail with HubOverflowError
4. Admin panel will show error message

## Error Handling

All functions include comprehensive error handling:

- **Validation errors**: Check location/status before operations
- **Capacity errors**: Check limits before moving queries
- **Transaction safety**: All operations are atomic
- **Row locking**: Grabber uses select_for_update() to prevent race conditions

## Thread Safety

The services are designed to be thread-safe:

- `@transaction.atomic` decorator ensures database consistency
- `select_for_update()` in grabber prevents concurrent grabs
- No global state is used

## Future Enhancements

Potential additions:
- Batch operations for moving multiple queries
- Scheduled auto-grabber (cron job or Celery task)
- Notifications when boxes are full
- Query priority system
- Routing rules based on query type
- User quota limits per day
