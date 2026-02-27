from django.urls import path
from . import views

urlpatterns = [
    path('',                    views.dashboard,            name='dashboard'),
    path('save-fatigue/',       views.save_fatigue,         name='save_fatigue'),
    path('current-fatigue/',    views.current_fatigue,      name='current_fatigue'),
    path('register/',           views.register,             name='register'),

    # Analytics
    path('analytics/',          views.analytics,            name='analytics'),
    path('analytics-data/',     views.analytics_data,       name='analytics_data'),

    # Reports
    path('reports/',            views.reports,              name='reports'),
    path('reports/download/',   views.download_report_csv,  name='download_report_csv'),

    # Alerts
    path('alerts/',             views.alerts,               name='alerts'),
    path('alerts/acknowledge/<int:alert_id>/', views.acknowledge_alert, name='acknowledge_alert'),
    path('alerts/acknowledge-all/',            views.acknowledge_all_alerts, name='acknowledge_all'),
    path('alerts/break/',       views.create_break_alert,   name='create_break_alert'),

    # Settings
    path('settings/',           views.settings_view,        name='settings'),
]
