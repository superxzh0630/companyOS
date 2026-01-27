from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import EmployeeProfileForm
from .models import EmployeeProfile


@login_required
def register_employee(request):
    """Handle employee registration form submission."""
    
    if request.method == 'POST':
        form = EmployeeProfileForm(request.POST)
        
        if form.is_valid():
            # Save the employee profile to PostgreSQL
            employee = form.save()
            
            # Success message
            success_message = f"Employee {employee.name} (ID: {employee.employee_id}) registered successfully!"
            
            # Render the form again with success message
            return render(request, 'profiles/register.html', {
                'form': EmployeeProfileForm(),  # Fresh form
                'success_message': success_message
            })
    else:
        form = EmployeeProfileForm()
    
    return render(request, 'profiles/register.html', {'form': form})
