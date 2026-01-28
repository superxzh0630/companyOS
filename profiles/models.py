from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Company(models.Model):
    """Model to store company locations."""
    
    name = models.CharField(max_length=100, unique=True, verbose_name="Company Name")
    city_code = models.CharField(max_length=10, unique=True, verbose_name="City Code")
    city_name = models.CharField(max_length=50, verbose_name="City Name")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "companies"
        verbose_name = "Company"
        verbose_name_plural = "Companies"
        ordering = ["name"]
    
    def __str__(self):
        return f"{self.name} - {self.city_name}"


class Department(models.Model):
    """Model to store company departments."""
    
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="departments",
        verbose_name="Company"
    )
    name = models.CharField(max_length=100, verbose_name="Department Name")
    display_name = models.CharField(max_length=100, verbose_name="Display Name")
    code = models.CharField(max_length=20, unique=True, verbose_name="Department Code")
    description = models.TextField(blank=True, verbose_name="Description")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "departments"
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        ordering = ["company", "display_name"]
        unique_together = [["company", "display_name"]]
    
    def __str__(self):
        return f"{self.display_name} ({self.company.name})"


class EmployeeProfile(models.Model):
    """Model to store employee profile information."""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employeeprofile",
        null=True,
        blank=True,
        verbose_name="User Account"
    )
    name = models.CharField(max_length=200, verbose_name="Name", blank=True)
    age = models.IntegerField(verbose_name="Age", null=True, blank=True)
    employee_id = models.CharField(max_length=50, unique=True, verbose_name="Employee ID", null=True, blank=True)
    email = models.EmailField(verbose_name="Email Address", blank=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="company_employees",
        verbose_name="Company"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name="Department"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "employee_profiles"
        verbose_name = "Employee Profile"
        verbose_name_plural = "Employee Profiles"
        ordering = ["-created_at"]
    
    def full_name_cn(self):
        """
        Return full name in Chinese order (Last Name + First Name).
        Falls back to username if names are empty.
        """
        if self.user:
            last_name = self.user.last_name or ""
            first_name = self.user.first_name or ""
            full_name = f"{last_name}{first_name}".strip()
            if full_name:
                return full_name
            return self.user.username
        return self.name or "Unknown"
    
    def __str__(self):
        if self.employee_id:
            return f"{self.name or self.full_name_cn()} ({self.employee_id})"
        return self.full_name_cn()


# ============================================================================
# Signals - Auto-create EmployeeProfile when User is created
# ============================================================================

@receiver(post_save, sender=User)
def create_employee_profile(sender, instance, created, **kwargs):
    """
    Automatically create an empty EmployeeProfile when a User is created.
    This ensures Admin-created users immediately have a profile ready.
    """
    if created:
        # Only create if profile doesn't already exist
        if not hasattr(instance, 'employeeprofile'):
            EmployeeProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_employee_profile(sender, instance, **kwargs):
    """
    Save the EmployeeProfile when the User is saved.
    """
    if hasattr(instance, 'employeeprofile'):
        instance.employeeprofile.save()
