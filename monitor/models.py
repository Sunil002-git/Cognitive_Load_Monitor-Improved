from django.db import models
from django.contrib.auth.models import User


class SessionLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_start = models.DateTimeField(auto_now_add=True)
    session_end = models.DateTimeField(null=True, blank=True)
    total_duration_minutes = models.FloatField(default=0)

    def __str__(self):
        return f"{self.user.username} - Session {self.session_start}"


class FatigueLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    blink_rate = models.FloatField()
    eye_closure_duration = models.FloatField(default=0)
    head_tilt_angle = models.FloatField(default=0)
    fatigue_probability = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - Fatigue {self.fatigue_probability}"


class BurnoutRisk(models.Model):
    RISK_CHOICES = [('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High')]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    weekly_avg_fatigue = models.FloatField()
    burnout_score = models.FloatField()
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES)
    calculated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.risk_level} Risk"


class AlertLog(models.Model):
    """Stores fatigue & posture alerts generated during monitoring."""
    ALERT_TYPES = [
        ('fatigue_high',  'High Fatigue'),
        ('fatigue_med',   'Medium Fatigue'),
        ('posture',       'Poor Posture'),
        ('break',         'Break Reminder'),
        ('burnout_high',  'High Burnout Risk'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    message = models.TextField()
    value = models.FloatField(default=0)          # e.g. fatigue prob or tilt angle
    acknowledged = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.alert_type} @ {self.timestamp}"


class UserSettings(models.Model):
    """Per-user configurable thresholds and preferences."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')
    # Thresholds
    fatigue_alert_threshold = models.FloatField(default=0.6)   # 0–1
    posture_tilt_threshold  = models.FloatField(default=15.0)  # degrees
    break_interval_minutes  = models.IntegerField(default=45)
    # Notifications
    enable_posture_alerts   = models.BooleanField(default=True)
    enable_fatigue_alerts   = models.BooleanField(default=True)
    enable_break_reminders  = models.BooleanField(default=True)
    # Profile
    display_name            = models.CharField(max_length=100, blank=True)
    work_hours_per_day      = models.FloatField(default=8.0)

    def __str__(self):
        return f"{self.user.username} Settings"
