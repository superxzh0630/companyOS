import os
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
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
    content = models.TextField(verbose_name="Content")
    
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
