from django.urls import path
from . import views
from django.contrib import admin

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('save-fatigue/', views.save_fatigue, name='save_fatigue'),
    path('register/', views.register, name='register'),
    path('analytics-data/', views.analytics_data, name='analytics_data'),
    path('current-fatigue/', views.current_fatigue, name='current_fatigue'),
]