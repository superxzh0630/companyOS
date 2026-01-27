from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import LoginForm


def login_view(request):
    """Handle user login."""
    if request.user.is_authenticated:
        return redirect('profiles:register')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data['remember_me']
            
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                
                # Set session expiry based on remember_me
                if remember_me:
                    # 2 weeks
                    request.session.set_expiry(1209600)
                else:
                    # Browser session (expires when browser closes)
                    request.session.set_expiry(0)
                
                messages.success(request, f'Welcome back, {user.username}!')
                
                # Redirect to next parameter or default to register page
                next_url = request.GET.get('next', 'profiles:register')
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()
    
    return render(request, 'authentication/login.html', {'form': form})


def logout_view(request):
    """Handle user logout."""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('authentication:login')
