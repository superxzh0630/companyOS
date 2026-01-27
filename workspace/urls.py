"""
URL configuration for workspace app.
"""
from django.urls import path
from . import views

app_name = 'workspace'

urlpatterns = [
    path('', views.my_tasks, name='my_tasks'),
    path('task/<int:ticket_id>/', views.task_detail, name='task_detail'),
    path('task/<int:ticket_id>/pick-up/', views.pick_up_task, name='pick_up_task'),
    path('task/<int:ticket_id>/complete/', views.complete_task, name='complete_task'),
]
