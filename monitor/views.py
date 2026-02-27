import csv, json, os
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.db.models import Avg, Sum, Count, Max
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone

import joblib

from .models import FatigueLog, SessionLog, BurnoutRisk, AlertLog, UserSettings

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fatigue_model.pkl"
)
ml_model = joblib.load(MODEL_PATH)


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def get_user_settings(user):
    settings, _ = UserSettings.objects.get_or_create(user=user)
    return settings


def calculate_burnout(user):
    today = date.today()
    total_minutes = SessionLog.objects.filter(
        user=user, session_start__date=today
    ).aggregate(total=Sum('total_duration_minutes'))['total'] or 0
    work_hours = total_minutes / 60

    avg_fatigue = FatigueLog.objects.filter(
        user=user, timestamp__date=today
    ).aggregate(avg=Avg('fatigue_probability'))['avg'] or 0

    s = get_user_settings(user)
    burnout_score = (avg_fatigue * 0.6) + ((work_hours / s.work_hours_per_day) * 0.4)

    risk = "Low" if burnout_score < 0.4 else "Medium" if burnout_score < 0.7 else "High"

    BurnoutRisk.objects.update_or_create(
        user=user, calculated_at__date=today,
        defaults={"weekly_avg_fatigue": avg_fatigue, "burnout_score": burnout_score, "risk_level": risk}
    )

    if risk == "High":
        _maybe_create_alert(user, 'burnout_high', f"Burnout risk is HIGH — score {burnout_score:.2f}", burnout_score)

    return risk, burnout_score


def _maybe_create_alert(user, alert_type, message, value):
    """Create alert only if no same-type alert in last 30 min."""
    recent = AlertLog.objects.filter(
        user=user, alert_type=alert_type,
        timestamp__gte=timezone.now() - timedelta(minutes=30)
    ).exists()
    if not recent:
        AlertLog.objects.create(user=user, alert_type=alert_type, message=message, value=value)


# ─── AUTH ─────────────────────────────────────────────────────────────────────

def custom_login(request):
    if request.method == "POST":
        user = authenticate(request, username=request.POST.get("username"), password=request.POST.get("password"))
        if user:
            login(request, user)
            return redirect('/')
        messages.error(request, "Invalid username or password.")
    return render(request, "login.html")


def custom_logout(request):
    if request.user.is_authenticated:
        active = SessionLog.objects.filter(user=request.user, session_end__isnull=True).first()
        if active:
            active.session_end = timezone.now()
            active.total_duration_minutes = round(
                (active.session_end - active.session_start).total_seconds() / 60, 2)
            active.save()
    logout(request)
    return redirect('login')


def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created! Please sign in.")
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, "register.html", {"form": form})


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    active = SessionLog.objects.filter(user=request.user, session_end__isnull=True).first()
    if not active:
        SessionLog.objects.create(user=request.user)

    risk, score = calculate_burnout(request.user)
    s = get_user_settings(request.user)
    unread_alerts = AlertLog.objects.filter(user=request.user, acknowledged=False).count()

    return render(request, "dashboard.html", {
        "burnout_risk": risk,
        "burnout_score": round(score, 2),
        "unread_alerts": unread_alerts,
        "settings": s,
    })


@login_required
def save_fatigue(request):
    if request.method != "POST":
        return JsonResponse({"status": "method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "bad json"}, status=400)

    blink   = float(data.get("blink_rate", 0))
    closure = float(data.get("eye_closure_duration", 0))
    tilt    = float(data.get("head_tilt_angle", 0))

    active = SessionLog.objects.filter(user=request.user, session_end__isnull=True).first()
    session_minutes = 0
    if active:
        session_minutes = (timezone.now() - active.session_start).total_seconds() / 60

    try:
        fatigue_prob = float(ml_model.predict_proba([[blink, closure, tilt, session_minutes]])[0][1])
    except Exception:
        fatigue_prob = 0.0

    FatigueLog.objects.create(
        user=request.user, blink_rate=blink,
        eye_closure_duration=closure, head_tilt_angle=tilt,
        fatigue_probability=fatigue_prob
    )

    s = get_user_settings(request.user)

    # Auto-create alerts based on user thresholds
    if s.enable_fatigue_alerts:
        if fatigue_prob >= s.fatigue_alert_threshold:
            level = 'fatigue_high' if fatigue_prob >= 0.75 else 'fatigue_med'
            _maybe_create_alert(request.user, level,
                f"Fatigue probability at {fatigue_prob:.0%} — consider taking a break.", fatigue_prob)

    if s.enable_posture_alerts and tilt > s.posture_tilt_threshold:
        _maybe_create_alert(request.user, 'posture',
            f"Poor posture detected — head tilt at {tilt:.1f}°.", tilt)

    return JsonResponse({"status": "saved", "fatigue": round(fatigue_prob, 3)})


@login_required
def current_fatigue(request):
    latest = FatigueLog.objects.filter(user=request.user).order_by('-timestamp').first()
    return JsonResponse({"fatigue": round(latest.fatigue_probability, 2) if latest else 0})


# ─── ANALYTICS PAGE ───────────────────────────────────────────────────────────

@login_required
def analytics(request):
    user = request.user
    today = date.today()

    # Summary stats
    total_sessions = SessionLog.objects.filter(user=user).count()
    total_hours = (SessionLog.objects.filter(user=user)
                   .aggregate(t=Sum('total_duration_minutes'))['t'] or 0) / 60
    avg_fatigue_all = FatigueLog.objects.filter(user=user).aggregate(a=Avg('fatigue_probability'))['a'] or 0
    high_risk_days = BurnoutRisk.objects.filter(user=user, risk_level='High').count()

    # Today stats
    today_minutes = (SessionLog.objects.filter(user=user, session_start__date=today)
                     .aggregate(t=Sum('total_duration_minutes'))['t'] or 0)
    today_fatigue = (FatigueLog.objects.filter(user=user, timestamp__date=today)
                     .aggregate(a=Avg('fatigue_probability'))['a'] or 0)

    return render(request, "analytics.html", {
        "total_sessions": total_sessions,
        "total_hours": round(total_hours, 1),
        "avg_fatigue_all": round(avg_fatigue_all * 100, 1),
        "high_risk_days": high_risk_days,
        "today_minutes": round(today_minutes, 0),
        "today_fatigue": round(today_fatigue * 100, 1),
    })


@login_required
def analytics_data(request):
    """JSON endpoint — returns data for chart period."""
    user = request.user
    period = request.GET.get('period', '7')  # '7', '30'
    days = int(period)
    today = datetime.today()
    day_list = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]

    fatigue_data, work_data, labels = [], [], []
    for day in day_list:
        d = day.date()
        avg_f = FatigueLog.objects.filter(user=user, timestamp__date=d).aggregate(avg=Avg('fatigue_probability'))['avg'] or 0
        total_m = SessionLog.objects.filter(user=user, session_start__date=d).aggregate(t=Sum('total_duration_minutes'))['t'] or 0
        fatigue_data.append(round(avg_f, 3))
        work_data.append(round(total_m / 60, 2))
        labels.append(d.strftime("%b %d"))

    # Hourly heatmap for today
    hourly = []
    for h in range(24):
        avg = FatigueLog.objects.filter(
            user=user,
            timestamp__date=today.date(),
            timestamp__hour=h
        ).aggregate(avg=Avg('fatigue_probability'))['avg']
        hourly.append(round(avg, 3) if avg is not None else None)

    return JsonResponse({
        "labels": labels, "fatigue": fatigue_data, "work_hours": work_data, "hourly": hourly
    })


# ─── REPORTS PAGE ─────────────────────────────────────────────────────────────

@login_required
def reports(request):
    user = request.user
    sessions = SessionLog.objects.filter(user=user).order_by('-session_start')[:50]

    session_data = []
    for s in sessions:
        date_str = s.session_start.strftime("%d %b %Y")
        start_str = s.session_start.strftime("%I:%M %p")
        end_str = s.session_end.strftime("%I:%M %p") if s.session_end else "Active"
        avg_f = FatigueLog.objects.filter(
            user=user,
            timestamp__gte=s.session_start,
            timestamp__lte=s.session_end or timezone.now()
        ).aggregate(avg=Avg('fatigue_probability'))['avg']
        risk = BurnoutRisk.objects.filter(user=user, calculated_at__date=s.session_start.date()).first()
        session_data.append({
            "id": s.id,
            "date": date_str,
            "start": start_str,
            "end": end_str,
            "duration": round(s.total_duration_minutes, 1),
            "avg_fatigue": round((avg_f or 0) * 100, 1),
            "risk": risk.risk_level if risk else "—",
        })

    return render(request, "reports.html", {"sessions": session_data})


@login_required
def download_report_csv(request):
    user = request.user
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="neurowatch_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['Date', 'Session Start', 'Session End', 'Duration (min)', 'Avg Fatigue %', 'Burnout Risk'])

    sessions = SessionLog.objects.filter(user=user).order_by('-session_start')
    for s in sessions:
        avg_f = FatigueLog.objects.filter(
            user=user, timestamp__gte=s.session_start,
            timestamp__lte=s.session_end or timezone.now()
        ).aggregate(avg=Avg('fatigue_probability'))['avg']
        risk = BurnoutRisk.objects.filter(user=user, calculated_at__date=s.session_start.date()).first()
        writer.writerow([
            s.session_start.strftime("%Y-%m-%d"),
            s.session_start.strftime("%H:%M"),
            s.session_end.strftime("%H:%M") if s.session_end else "Active",
            round(s.total_duration_minutes, 1),
            round((avg_f or 0) * 100, 1),
            risk.risk_level if risk else "N/A",
        ])

    return response


# ─── ALERTS PAGE ──────────────────────────────────────────────────────────────

@login_required
def alerts(request):
    user = request.user
    all_alerts = AlertLog.objects.filter(user=user)

    # Counts by type
    counts = {
        'total': all_alerts.count(),
        'unread': all_alerts.filter(acknowledged=False).count(),
        'fatigue': all_alerts.filter(alert_type__in=['fatigue_high', 'fatigue_med']).count(),
        'posture': all_alerts.filter(alert_type='posture').count(),
        'break':   all_alerts.filter(alert_type='break').count(),
        'burnout': all_alerts.filter(alert_type='burnout_high').count(),
    }

    return render(request, "alerts.html", {
        "alerts": all_alerts[:100],
        "counts": counts,
    })


@login_required
def acknowledge_alert(request, alert_id):
    AlertLog.objects.filter(user=request.user, id=alert_id).update(acknowledged=True)
    return JsonResponse({"status": "ok"})


@login_required
def acknowledge_all_alerts(request):
    AlertLog.objects.filter(user=request.user, acknowledged=False).update(acknowledged=True)
    return JsonResponse({"status": "ok"})


@login_required
def create_break_alert(request):
    """Called from frontend when break timer fires."""
    if request.method == "POST":
        s = get_user_settings(request.user)
        if s.enable_break_reminders:
            _maybe_create_alert(
                request.user, 'break',
                f"You've been active for {s.break_interval_minutes}+ minutes. Take a break!",
                s.break_interval_minutes
            )
    return JsonResponse({"status": "ok"})


# ─── SETTINGS PAGE ────────────────────────────────────────────────────────────

@login_required
def settings_view(request):
    user = request.user
    s = get_user_settings(user)
    pw_form = PasswordChangeForm(user)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "thresholds":
            s.fatigue_alert_threshold = float(request.POST.get("fatigue_threshold", 0.6))
            s.posture_tilt_threshold  = float(request.POST.get("tilt_threshold", 15))
            s.break_interval_minutes  = int(request.POST.get("break_interval", 45))
            s.work_hours_per_day      = float(request.POST.get("work_hours", 8))
            s.save()
            messages.success(request, "Thresholds updated successfully.")

        elif action == "notifications":
            s.enable_fatigue_alerts  = 'fatigue_alerts' in request.POST
            s.enable_posture_alerts  = 'posture_alerts' in request.POST
            s.enable_break_reminders = 'break_reminders' in request.POST
            s.save()
            messages.success(request, "Notification preferences saved.")

        elif action == "profile":
            s.display_name = request.POST.get("display_name", "")
            s.save()
            messages.success(request, "Profile updated.")

        elif action == "password":
            pw_form = PasswordChangeForm(user, request.POST)
            if pw_form.is_valid():
                pw_form.save()
                update_session_auth_hash(request, pw_form.user)
                messages.success(request, "Password changed successfully.")
            else:
                messages.error(request, "Password change failed. Check the form.")

        return redirect('settings')

    return render(request, "settings.html", {"s": s, "pw_form": pw_form})
