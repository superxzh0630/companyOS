from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def index(request):
    """Home page view. Requires authentication."""
    return render(request, 'index.html')
