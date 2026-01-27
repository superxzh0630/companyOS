"""
URL configuration for dashboard app.
"""
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Smart Router - decides where to send user
    path('router/', views.dashboard_router, name='router'),
    
    # Admin Department Selector
    path('select-department/', views.admin_dept_selector, name='admin_dept_selector'),
    
    # Global Hub Dashboard
    path('hub/', views.global_hub_dashboard, name='global_hub'),
    path('api/hub/', views.global_hub_api, name='global_hub_api'),
    
    # Department Dashboard
    path('dept/', views.department_dashboard, name='department_self'),
    path('dept/<str:dept_code>/', views.department_dashboard, name='department'),
    path('api/dept/<str:dept_code>/', views.department_api, name='department_api'),
    
    # Admin Monitor
    path('admin-monitor/', views.admin_monitor, name='admin_monitor'),
    path('api/admin-monitor/', views.admin_monitor_api, name='admin_monitor_api'),
]
