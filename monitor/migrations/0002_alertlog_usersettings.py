from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('monitor', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AlertLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_type', models.CharField(choices=[('fatigue_high','High Fatigue'),('fatigue_med','Medium Fatigue'),('posture','Poor Posture'),('break','Break Reminder'),('burnout_high','High Burnout Risk')], max_length=20)),
                ('message', models.TextField()),
                ('value', models.FloatField(default=0)),
                ('acknowledged', models.BooleanField(default=False)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-timestamp']},
        ),
        migrations.CreateModel(
            name='UserSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fatigue_alert_threshold', models.FloatField(default=0.6)),
                ('posture_tilt_threshold', models.FloatField(default=15.0)),
                ('break_interval_minutes', models.IntegerField(default=45)),
                ('enable_posture_alerts', models.BooleanField(default=True)),
                ('enable_fatigue_alerts', models.BooleanField(default=True)),
                ('enable_break_reminders', models.BooleanField(default=True)),
                ('display_name', models.CharField(blank=True, max_length=100)),
                ('work_hours_per_day', models.FloatField(default=8.0)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='settings', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
