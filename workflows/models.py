import os
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from profiles.models import Department


class SystemConfig(models.Model):
    """
    Singleton model for global system configuration.
    Only one instance should exist.
    """
    hub_capacity_limit = models.PositiveIntegerField(
        default=100,
        verbose_name="Hub Capacity Limit",
        help_text="Maximum number of tickets in the big hub"
    )
    dept_receiving_box_limit = models.PositiveIntegerField(
        default=50,
        verbose_name="Department Receiving Box Limit",
        help_text="Maximum number of tickets in each department's receiving box"
    )
    
    class Meta:
        verbose_name = "System Configuration"
        verbose_name_plural = "System Configuration"
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists (Singleton pattern)."""
        if not self.pk and SystemConfig.objects.exists():
            raise ValidationError("Only one SystemConfig instance is allowed.")
        return super().save(*args, **kwargs)
    
    @classmethod
    def get_config(cls):
        """Get or create the singleton config instance."""
        config, created = cls.objects.get_or_create(pk=1)
        return config
    
    def __str__(self):
        return f"System Config (Hub: {self.hub_capacity_limit}, Dept: {self.dept_receiving_box_limit})"


class DailySequence(models.Model):
    """
    Thread-safe daily sequence counter for generating unique ticket IDs.
    Resets every day.
    """
    date = models.DateField(unique=True, verbose_name="Date")
    sequence = models.PositiveIntegerField(default=0, verbose_name="Sequence Number")
    
    class Meta:
        verbose_name = "Daily Sequence"
        verbose_name_plural = "Daily Sequences"
        indexes = [
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"{self.date} - Sequence: {self.sequence}"


# ============================================================================
# Dynamic Query Type Definitions (Admin Configurable)
# ============================================================================

class QueryType(models.Model):
    """
    Blueprint for a query type that Admins can configure.
    Defines what kind of queries exist and which departments can receive them.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Query Type Name",
        help_text="e.g., 'Purchase Request', 'IT Support', 'Leave Application'"
    )
    code = models.SlugField(
        max_length=20,
        unique=True,
        verbose_name="Type Code",
        help_text="Short code for t_tag generation (e.g., 'PR', 'IT', 'LA')"
    )
    allowed_departments = models.ManyToManyField(
        Department,
        related_name='accepted_query_types',
        verbose_name="Allowed Departments",
        help_text="Departments that can receive this type of query"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description",
        help_text="Detailed description of this query type"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Is Active",
        help_text="Inactive query types cannot be used for new tickets"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Query Type"
        verbose_name_plural = "Query Types"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class QueryFieldDefinition(models.Model):
    """
    Dynamic field definition for a QueryType.
    Allows Admin to define custom fields for each query type.
    """
    class FieldType(models.TextChoices):
        TEXT = 'TEXT', 'Text (Single Line)'
        TEXTAREA = 'TEXTAREA', 'Text (Multi Line)'
        INTEGER = 'INTEGER', 'Integer Number'
        DECIMAL = 'DECIMAL', 'Decimal Number'
        DATE = 'DATE', 'Date'
        FILE = 'FILE', 'File Upload'
        BOOLEAN = 'BOOLEAN', 'Yes/No Checkbox'
    
    query_type = models.ForeignKey(
        QueryType,
        on_delete=models.CASCADE,
        related_name='fields',
        verbose_name="Query Type"
    )
    label = models.CharField(
        max_length=100,
        verbose_name="Field Label",
        help_text="Display label (e.g., 'Reason for Purchase')"
    )
    field_key = models.SlugField(
        max_length=50,
        verbose_name="Field Key",
        help_text="Key for JSON storage (e.g., 'reason_purchase'). Use lowercase with underscores."
    )
    field_type = models.CharField(
        max_length=20,
        choices=FieldType.choices,
        default=FieldType.TEXT,
        verbose_name="Field Type"
    )
    required = models.BooleanField(
        default=True,
        verbose_name="Required"
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Display Order",
        help_text="Fields are displayed in ascending order"
    )
    placeholder = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Placeholder Text"
    )
    help_text = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Help Text"
    )
    
    class Meta:
        verbose_name = "Query Field Definition"
        verbose_name_plural = "Query Field Definitions"
        ordering = ['query_type', 'order', 'id']
        unique_together = ['query_type', 'field_key']
    
    def __str__(self):
        return f"{self.query_type.name} - {self.label} ({self.field_key})"


class QueryTicket(models.Model):
    """
    Main query/ticket model for inter-departmental workflows.
    """
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        RECEIVED = 'RECEIVED', 'Received'
        ASSIGNED = 'ASSIGNED', 'Assigned'
        COMPLETED = 'COMPLETED', 'Completed'
    
    class Location(models.TextChoices):
        SENDER_BOX = 'SENDER_BOX', 'Sender Box'
        BIG_HUB = 'BIG_HUB', 'Big Hub'
        RECEIVER_BOX = 'RECEIVER_BOX', 'Receiver Box'
        TASK_BOX = 'TASK_BOX', 'Task Box'
    
    # Global unique identifier
    t_tag = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name="Ticket Tag",
        help_text="Format: TYPE-DEPT-YYMMDD-SEQ (e.g., QGD-PD-260122-001)"
    )
    
    # Content fields
    title = models.CharField(max_length=200, verbose_name="Title")
    content = models.TextField(verbose_name="Content", blank=True)
    
    # Dynamic Query Type (optional for backward compatibility)
    query_type = models.ForeignKey(
        QueryType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='tickets',
        verbose_name="Query Type",
        help_text="Dynamic query type definition"
    )
    
    # JSON storage for dynamic field values (non-file fields)
    content_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Content Data",
        help_text="JSON storage for dynamic form field values"
    )
    
    # Status and location
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Status"
    )
    location = models.CharField(
        max_length=20,
        choices=Location.choices,
        default=Location.SENDER_BOX,
        verbose_name="Location"
    )
    
    # Department and ownership
    source_dept = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='sent_tickets',
        verbose_name="Source Department"
    )
    target_dept = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='received_tickets',
        verbose_name="Target Department"
    )
    current_owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets',
        verbose_name="Current Owner"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    grabbed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Grabbed At",
        help_text="When the ticket was grabbed by current owner (5-min rule)"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Completed At"
    )
    
    class Meta:
        verbose_name = "Query Ticket"
        verbose_name_plural = "Query Tickets"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['t_tag']),
            models.Index(fields=['status', 'location']),
            models.Index(fields=['source_dept', 'status']),
            models.Index(fields=['target_dept', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.t_tag} - {self.title}"


def attachment_upload_path(instance, filename):
    """
    Generate upload path for query attachments.
    Returns: media/query_attachments/[T_TAG]/[filename]
    """
    return f'query_attachments/{instance.query_ticket.t_tag}/{filename}'


class QueryAttachment(models.Model):
    """
    File attachments for query tickets.
    Files are automatically renamed to [T_TAG]-[A/B/C].ext format.
    """
    query_ticket = models.ForeignKey(
        QueryTicket,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name="Query Ticket"
    )
    file = models.FileField(
        upload_to=attachment_upload_path,
        verbose_name="File"
    )
    original_filename = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Original Filename"
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Uploaded By"
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Uploaded At"
    )
    sequence_letter = models.CharField(
        max_length=1,
        blank=True,
        verbose_name="Sequence Letter (A/B/C...)"
    )
    
    class Meta:
        verbose_name = "Query Attachment"
        verbose_name_plural = "Query Attachments"
        ordering = ['sequence_letter', 'uploaded_at']
    
    def save(self, *args, **kwargs):
        """
        Override save to rename file to [T_TAG]-[A/B/C].ext format.
        """
        if self.file and not self.sequence_letter:
            # Store original filename
            if not self.original_filename:
                self.original_filename = os.path.basename(self.file.name)
            
            # Determine next sequence letter
            existing_attachments = QueryAttachment.objects.filter(
                query_ticket=self.query_ticket
            ).order_by('-sequence_letter')
            
            if existing_attachments.exists():
                last_letter = existing_attachments.first().sequence_letter
                next_letter = chr(ord(last_letter) + 1) if last_letter else 'A'
            else:
                next_letter = 'A'
            
            self.sequence_letter = next_letter
            
            # Get file extension
            ext = os.path.splitext(self.original_filename)[1]
            
            # Rename file
            new_filename = f"{self.query_ticket.t_tag}-{next_letter}{ext}"
            
            # Update file name
            old_file = self.file
            self.file.name = f'query_attachments/{self.query_ticket.t_tag}/{new_filename}'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.query_ticket.t_tag}-{self.sequence_letter} ({self.original_filename})"


# ============================================================================
# Dynamic Ticket Attachment (for Dynamic Query Field FILE types)
# ============================================================================

def dynamic_media_path(instance, filename):
    """
    Generate dynamic upload path for ticket attachments.
    Format: media/{DEPT_CODE}/{USERNAME}/{YYYY-MM-DD}/{FILENAME}
    """
    try:
        dept = instance.ticket.current_owner.employeeprofile.department.code
    except (AttributeError, Exception):
        # Fallback to source_dept if owner doesn't have profile
        try:
            dept = instance.ticket.source_dept.code
        except (AttributeError, Exception):
            dept = "GENERAL"
    
    try:
        user = instance.ticket.current_owner.username if instance.ticket.current_owner else "anonymous"
    except (AttributeError, Exception):
        user = "anonymous"
    
    # Use current date if created_at not set yet
    if instance.created_at:
        date_str = instance.created_at.strftime('%Y-%m-%d')
    else:
        date_str = timezone.now().strftime('%Y-%m-%d')
    
    return f'media/{dept}/{user}/{date_str}/{filename}'


class TicketAttachment(models.Model):
    """
    File attachments linked to specific dynamic query fields.
    Stores files in structured path: media/{DEPT}/{USER}/{DATE}/{FILENAME}
    """
    ticket = models.ForeignKey(
        QueryTicket,
        on_delete=models.CASCADE,
        related_name='dynamic_attachments',
        verbose_name="Query Ticket"
    )
    field_definition = models.ForeignKey(
        QueryFieldDefinition,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attachments',
        verbose_name="Field Definition",
        help_text="The dynamic field this file belongs to"
    )
    file = models.FileField(
        upload_to=dynamic_media_path,
        verbose_name="File"
    )
    original_filename = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Original Filename"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )
    
    class Meta:
        verbose_name = "Ticket Attachment"
        verbose_name_plural = "Ticket Attachments"
        ordering = ['created_at']
    
    def save(self, *args, **kwargs):
        """Store original filename before saving."""
        if self.file and not self.original_filename:
            self.original_filename = os.path.basename(self.file.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        field_label = self.field_definition.label if self.field_definition else "General"
        return f"{self.ticket.t_tag} - {field_label} - {self.original_filename}"


# ============================================================================
# Proxy Models for Department-Specific Box Visualization
# ============================================================================

class SenderTicket(QueryTicket):
    """
    Proxy model for visualizing tickets in Sender Box.
    Used in Department admin to show outgoing tickets waiting for Hub.
    """
    class Meta:
        proxy = True
        verbose_name = "Item in Sender Box"
        verbose_name_plural = "📤 Sender Box (Waiting for Hub)"


class ReceiverTicket(QueryTicket):
    """
    Proxy model for visualizing tickets in Receiver Box.
    Used in Department admin to show incoming tickets ready for assignment.
    """
    class Meta:
        proxy = True
        verbose_name = "Item in Receiver Box"
        verbose_name_plural = "📥 Receiver Box (Ready to Assign)"
