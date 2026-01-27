"""
Manual test instructions for workflow services.

To test the services through Django admin:

1. Start the Django server:
   python manage.py runserver

2. Go to the admin panel:
   http://localhost:8000/admin/

3. Create SystemConfig (if not exists):
   - Go to System configs
   - Click "Add system config"
   - Set hub_capacity_limit: 100
   - Set dept_receiving_box_limit: 50
   - Save

4. Create a test query ticket:
   - Open Django shell: python manage.py shell
   - Run:
     from workflows.models import QueryTicket, SystemConfig
     from profiles.models import Department
     
     dept = Department.objects.first()  # or create one
     
     ticket = QueryTicket.objects.create(
         t_tag="TEST-PD-260122-001",
         title="Test Purchase Query",
         content="Need to buy 100 units of Part X",
         status=QueryTicket.Status.PENDING,
         location=QueryTicket.Location.SENDER_BOX,
         source_dept=dept,
         target_dept_code='PD'
     )
     print(f"Created ticket: {ticket.t_tag} in {ticket.location}")

5. Test Push to Hub:
   - Go to admin panel: Query tickets
   - Select the ticket in SENDER_BOX
   - From "Action" dropdown, select "推送到大枢纽 (Push selected queries to Big Hub)"
   - Click "Go"
   - You should see success message and ticket location changes to BIG_HUB

6. Test Department Grabber:
   - Select a ticket in BIG_HUB
   - From "Action" dropdown, select "运行部门抓取器 (Run department grabber for selected departments)"
   - Click "Go"
   - You should see success message and ticket location changes to RECEIVER_BOX

Key Features:
- push_to_hub: Moves queries from SENDER_BOX → BIG_HUB (checks capacity)
- run_dept_grabber: Grabs oldest PENDING query from BIG_HUB → RECEIVER_BOX (checks capacity)
- Both functions are transaction-safe and check capacity limits
- Admin actions provide user-friendly testing interface
"""
