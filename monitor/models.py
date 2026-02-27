from django.db import models
from django.contrib.auth.models import User

# Session Log
class SessionLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_start = models.DateTimeField(auto_now_add=True)
    session_end = models.DateTimeField(null=True, blank= True)
    total_duration_minutes = models.FloatField(default=0)

    def __str__(self):
        return f"{self.user.username} - Session {self.session_start}"

# Fatigue Log (Real-Time AI Data)

class FatigueLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    blink_rate = models.FloatField()
    eye_closure_duration = models.FloatField(default=0)
    head_tilt_angle = models.FloatField(default=0)
    fatigue_probability = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - Fatigue{self.fatigue_probability}"

# Burnout Risk Model

class BurnoutRisk(models.Model):
    RISK_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    weekly_avg_fatigue = models.FloatField()
    burnout_score = models.FloatField()
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES)
    calculated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.risk_level} Risk"