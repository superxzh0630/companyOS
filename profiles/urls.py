from django.urls import path
from . import views

app_name = 'profiles'

urlpatterns = [
    path('register/', views.register_employee, name='register'),
]
