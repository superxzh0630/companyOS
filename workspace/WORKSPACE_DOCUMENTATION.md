# Workspace App Documentation

## Overview
The workspace app provides the employee-facing interface for managing query tickets. Employees can pick up tasks from their department's receiver box, upload attachments, complete tasks, and create child queries.

## Features

### 1. Task Management
- **View Available Tasks**: See all queries in department's receiver box
- **View My Tasks**: See assigned tasks in progress
- **View Completed Tasks**: History of completed tasks (last 20)

### 2. Task Assignment
- **Pick Up Task**: Assign a task from receiver box to yourself
  - Validates task is in RECEIVER_BOX
  - Changes location to TASK_BOX
  - Changes status to ASSIGNED
  - Sets current_owner to logged-in user

### 3. File Attachments
- **Upload Files**: Attach files to tasks
- **Automatic Renaming**: Files renamed to `[T_TAG]-[A/B/C].ext` format
  - Example: `QGD-PD-260122-001-A.pdf`, `QGD-PD-260122-001-B.xlsx`
- **Sequence Letters**: Automatically assigned (A, B, C, D...)
- **Original Filename Preserved**: Stored in database for reference

### 4. Task Completion with Child Query
- **Complete Task**: Mark task as completed
- **Create Child Query**: Optionally create a new query when completing
  - Child query placed in SENDER_BOX
  - References parent task ID
  - Ready for workflow system to process
- **Use Case**: Task generates output that becomes input for another department
  - Example: Complete purchase request → Create purchase order for supplier

## URL Structure

```
/workspace/                          → My Tasks Dashboard
/workspace/task/<id>/                → Task Detail View
/workspace/task/<id>/pick-up/        → Pick Up Task Action
/workspace/task/<id>/complete/       → Complete Task Form
```

## Models

### QueryAttachment (in workflows app)
Located in `workflows/models.py` since it's directly related to QueryTicket.

**Fields:**
- `query_ticket`: ForeignKey to QueryTicket
- `file`: FileField with automatic upload path
- `original_filename`: CharField - stores original file name
- `uploaded_by`: ForeignKey to User
- `uploaded_at`: DateTimeField
- `sequence_letter`: CharField - A, B, C, etc.

**File Naming Logic:**
```python
def save(self, *args, **kwargs):
    # Determine next sequence letter (A, B, C...)
    # Rename file to: [T_TAG]-[LETTER].ext
    # Example: QGD-PD-260122-001-A.pdf
```

**Upload Path:**
```
media/query_attachments/[T_TAG]/[filename]
```

## Views

### my_tasks(request)
**Purpose**: Dashboard showing all task categories

**Displays:**
1. Available tasks in department receiver box
2. User's assigned tasks in progress
3. User's completed tasks (last 20)

**Access Control**: Requires login and employee profile

### pick_up_task(request, ticket_id)
**Purpose**: Assign a task to the current user

**Process:**
1. Validates user has employee profile
2. Validates task is in RECEIVER_BOX with RECEIVED status
3. Validates task belongs to user's department
4. Updates: location → TASK_BOX, status → ASSIGNED, current_owner → user
5. Redirects to task detail

**Transaction Safety**: Uses `@transaction.atomic`

### task_detail(request, ticket_id)
**Purpose**: Show task details and manage attachments

**Features:**
- Display task information
- List all attachments with sequence letters
- Upload new attachments (if task is assigned to user)
- View metadata (created, grabbed, completed times)

**Access Control**: Can view if:
- Task is assigned to user, OR
- Task is in user's department receiver box

### complete_task(request, ticket_id)
**Purpose**: Complete a task with optional child query creation

**Form Fields:**
- `completion_notes`: Optional notes
- `create_child_query`: Checkbox to enable child query
- `child_query_type`: Chinese type name (e.g., "报价单")
- `child_target_dept`: Target department code
- `child_title`: Child task title
- `child_content`: Child task content

**Process:**
1. Validates task is assigned to current user
2. Updates task: status → COMPLETED, completed_at → now
3. If creating child query:
   - Generates new t_tag using generate_t_tag()
   - Creates new QueryTicket in SENDER_BOX
   - References parent task in content
4. Redirects to my_tasks

**Transaction Safety**: Uses `@transaction.atomic`

## Forms

### AttachmentUploadForm
Simple form for file uploads.

**Fields:**
- `file`: FileField

### CompleteTaskForm
Complex form with conditional validation.

**Fields:**
- `completion_notes`: Optional textarea
- `create_child_query`: Boolean checkbox
- `child_query_type`: CharField (required if creating child)
- `child_target_dept`: CharField (required if creating child)
- `child_title`: CharField (required if creating child)
- `child_content`: TextField (required if creating child)

**Validation:**
- If `create_child_query` is checked, all child fields are required
- Chinese validation for query type

## Templates

### my_tasks.html
**Sections:**
1. Available Tasks Table
   - Task ID, Title, Source Department, Created Time
   - "Pick Up" button for each task
2. My Assigned Tasks Cards
   - Full task details with attachments
   - "View Details" and "Complete Task" buttons
3. Completed Tasks Table
   - Task ID, Title, Completed Time

### task_detail.html
**Sections:**
1. Task Header with Status/Location badges
2. Task Content
3. Metadata Grid (created, grabbed, completed times)
4. Attachments Table
   - Sequence letter, renamed filename, original filename
   - Uploader and upload time
5. Upload Form (if task assigned to user)
6. Action Buttons

### complete_task.html
**Features:**
- Task Summary at top
- Completion notes textarea
- Child query checkbox
- Collapsible child query section (JavaScript toggle)
- Form validation messages
- Confirm/Cancel buttons

## Workflow Integration

### Child Query Re-Loop
When a task generates output that becomes input for another process:

1. User completes Task A
2. Checks "Create Child Query"
3. Fills in child query details
4. Child Query created in SENDER_BOX of user's department
5. Child Query follows normal workflow:
   - Wait for push_to_hub()
   - Move to BIG_HUB
   - Wait for run_dept_grabber()
   - Move to target department's RECEIVER_BOX
   - Another user picks it up

**Example Flow:**
```
Manufacturing → Purchasing: "Need 100 units of Part X"
  ↓ (Manufacturing picks up, processes)
Purchasing completes with child query
  ↓ (Creates new query in SENDER_BOX)
Purchasing → Supplier: "Order 100 units of Part X"
```

## File Upload Configuration

### Settings (config/settings.py)
```python
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'storage' / 'media'
```

### URL Configuration (config/urls.py)
```python
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

### Storage Structure
```
storage/
  media/
    query_attachments/
      QGD-PD-260122-001/
        QGD-PD-260122-001-A.pdf
        QGD-PD-260122-001-B.xlsx
      WXD-HRTJ-260122-002/
        WXD-HRTJ-260122-002-A.docx
```

## Access Control

All views require:
1. User login (`@login_required`)
2. Employee profile with department assignment
3. Appropriate permissions for the specific task

## UI/UX Features

### Chinese/English Bilingual
All labels and messages in both languages:
- 我的任务 / My Tasks
- 领取 / Pick Up
- 完成任务 / Complete Task

### Color Coding
- Primary Blue (#003071): In-progress tasks
- Red (#BA0C2F): Task IDs and important info
- Green (#28a745): Complete buttons
- Grey (#6c757d): Cancel/back buttons

### Responsive Design
Uses CSS from base.css, forms.css, components.css

## Testing Checklist

1. **View Tasks**
   - Login as employee with department
   - Navigate to /workspace/
   - Verify three sections display

2. **Pick Up Task**
   - Click "Pick Up" on available task
   - Verify task moves to "My Assigned Tasks"
   - Check database: location=TASK_BOX, status=ASSIGNED

3. **Upload Attachment**
   - Open task detail
   - Upload a PDF file
   - Verify renamed to [T_TAG]-A.pdf
   - Upload another file
   - Verify renamed to [T_TAG]-B.[ext]

4. **Complete Task (Simple)**
   - Click "Complete Task"
   - Add completion notes
   - Submit without child query
   - Verify task moves to "Completed Tasks"

5. **Complete Task (With Child)**
   - Click "Complete Task"
   - Check "Create Child Query"
   - Fill in child query details
   - Submit
   - Verify parent task completed
   - Verify child query created in SENDER_BOX
   - Check child query references parent

## Future Enhancements

Potential additions:
- Task comments/discussion thread
- Task reassignment to other users
- Bulk operations (pick up multiple, complete multiple)
- Task priority levels
- Due dates and reminders
- Task search and filtering
- Mobile-optimized views
- Real-time notifications
- Task templates for common types
