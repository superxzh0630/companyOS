from django.db import models
from django.contrib.auth.models import User


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
        related_name="employee_profile",
        null=True,
        blank=True,
        verbose_name="User Account"
    )
    name = models.CharField(max_length=200, verbose_name="Name")
    age = models.IntegerField(verbose_name="Age")
    employee_id = models.CharField(max_length=50, unique=True, verbose_name="Employee ID")
    email = models.EmailField(unique=True, verbose_name="Email Address")
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="employees",
        verbose_name="Company"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
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
    
    def __str__(self):
        return f"{self.name} ({self.employee_id})"
