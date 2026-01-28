"""
URL configuration for workspace app.
"""
from django.urls import path
from . import views

app_name = 'workspace'

urlpatterns = [
    # Main workspace views
    path('', views.my_tasks, name='my_tasks'),
    
    # User-specific workspace with Pinyin/username in URL
    path('workspace-<str:username>/', views.user_workspace, name='user_workspace'),
    
    # Task management
    path('task/<int:ticket_id>/', views.task_detail, name='task_detail'),
    path('task/<int:ticket_id>/pick-up/', views.pick_up_task, name='pick_up_task'),
    path('task/<int:ticket_id>/complete/', views.complete_task, name='complete_task'),
    
    # Query Type Selection & Dynamic Ticket Creation
    path('create/', views.select_query_type, name='select_query_type'),
    path('create/<int:query_type_id>/', views.create_ticket_view, name='create_ticket'),
]
