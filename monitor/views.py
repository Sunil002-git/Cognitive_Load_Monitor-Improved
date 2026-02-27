from django.http import JsonResponse
from django.shortcuts import render, redirect
from .models import FatigueLog, SessionLog, BurnoutRisk
from django.contrib.auth.forms import UserCreationForm
import json
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth import logout, authenticate, login
from django.contrib import messages
from django.db.models import Avg, Sum
from datetime import date, datetime, timedelta
import joblib, os

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fatigue_model.pkl"
)
ml_model = joblib.load(MODEL_PATH)


@login_required
def dashboard(request):
    # Start session if none active
    active_session = SessionLog.objects.filter(
        user=request.user, session_end__isnull=True
    ).first()
    if not active_session:
        SessionLog.objects.create(user=request.user)

    risk, score = calculate_burnout(request.user)

    return render(request, "dashboard.html", {
        "burnout_risk": risk,
        "burnout_score": round(score, 2)
    })


@login_required
def save_fatigue(request):
    """Receive face-mesh data, run ML prediction, save FatigueLog."""
    if request.method != "POST":
        return JsonResponse({"status": "method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "bad json"}, status=400)

    blink   = float(data.get("blink_rate", 0))
    closure = float(data.get("eye_closure_duration", 0))
    tilt    = float(data.get("head_tilt_angle", 0))

    # Get current session duration
    active_session = SessionLog.objects.filter(
        user=request.user, session_end__isnull=True
    ).first()
    session_minutes = 0
    if active_session:
        session_minutes = (
            (timezone.now() - active_session.session_start).total_seconds() / 60
        )

    # ML prediction
    try:
        prediction = ml_model.predict_proba([[blink, closure, tilt, session_minutes]])
        fatigue_probability = float(prediction[0][1])
    except Exception:
        fatigue_probability = 0.0

    FatigueLog.objects.create(
        user=request.user,
        blink_rate=blink,
        eye_closure_duration=closure,
        head_tilt_angle=tilt,
        fatigue_probability=fatigue_probability
    )

    return JsonResponse({"status": "saved", "fatigue": round(fatigue_probability, 3)})


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


def custom_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, "login.html")


def custom_logout(request):
    if request.user.is_authenticated:
        active_session = SessionLog.objects.filter(
            user=request.user, session_end__isnull=True
        ).first()
        if active_session:
            active_session.session_end = timezone.now()
            duration = (active_session.session_end - active_session.session_start).total_seconds() / 60
            active_session.total_duration_minutes = round(duration, 2)
            active_session.save()
    logout(request)
    return redirect('login')


def calculate_burnout(user):
    today = date.today()
    total_minutes = SessionLog.objects.filter(
        user=user, session_start__date=today
    ).aggregate(total=Sum('total_duration_minutes'))['total'] or 0
    work_hours = total_minutes / 60

    avg_fatigue = FatigueLog.objects.filter(
        user=user, timestamp__date=today
    ).aggregate(avg=Avg('fatigue_probability'))['avg'] or 0

    burnout_score = (avg_fatigue * 0.6) + ((work_hours / 8) * 0.4)

    if burnout_score < 0.4:
        risk = "Low"
    elif burnout_score < 0.7:
        risk = "Medium"
    else:
        risk = "High"

    BurnoutRisk.objects.update_or_create(
        user=user,
        calculated_at__date=today,
        defaults={
            "weekly_avg_fatigue": avg_fatigue,
            "burnout_score": burnout_score,
            "risk_level": risk
        }
    )
    return risk, burnout_score


@login_required
def analytics_data(request):
    user = request.user
    today = datetime.today()
    last_7 = [today - timedelta(days=i) for i in range(6, -1, -1)]

    fatigue_data, work_data, labels = [], [], []
    for day in last_7:
        d = day.date()
        avg_f = FatigueLog.objects.filter(
            user=user, timestamp__date=d
        ).aggregate(avg=Avg('fatigue_probability'))['avg'] or 0
        total_m = SessionLog.objects.filter(
            user=user, session_start__date=d
        ).aggregate(total=Sum('total_duration_minutes'))['total'] or 0

        fatigue_data.append(round(avg_f, 2))
        work_data.append(round(total_m / 60, 2))
        labels.append(d.strftime("%b %d"))

    return JsonResponse({"labels": labels, "fatigue": fatigue_data, "work_hours": work_data})


@login_required
def current_fatigue(request):
    latest = FatigueLog.objects.filter(user=request.user).order_by('-timestamp').first()
    value = latest.fatigue_probability if latest else 0
    return JsonResponse({"fatigue": round(value, 2)})
