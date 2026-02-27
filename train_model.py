import numpy as np
from sklearn.linear_model import LogisticRegression
import joblib

# Features:
# blink_rate, eye_closure_duration, head_tilt_angle, session_minutes

X = []
y = []

# Generate synthetic training data
for _ in range(1000):
    blink = np.random.uniform(2, 25)
    closure = np.random.uniform(0, 3)
    tilt = np.random.uniform(0, 30)
    session = np.random.uniform(10, 480)

    fatigue_score = 0

    if blink < 8:
        fatigue_score += 1
    if closure > 1.5:
        fatigue_score += 1
    if tilt > 15:
        fatigue_score += 1
    if session > 240:
        fatigue_score += 1

    X.append([blink, closure, tilt, session])
    y.append(1 if fatigue_score >= 2 else 0)

model = LogisticRegression()
model.fit(X, y)

joblib.dump(model, "fatigue_model.pkl")

print("Model trained and saved.")