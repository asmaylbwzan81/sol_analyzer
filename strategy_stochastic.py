import json

try:
    with open("config.json") as f:
        config = json.load(f)
except:
    config = {}

def analyze(candles, period=None):
    period = period or config.get("stochastic_period", 14)

    if len(candles) < period:
        return 0.5

    recent = candles[-period:]
    highest = max(c["high"] for c in recent)
    lowest = min(c["low"] for c in recent)
    close = candles[-1]["close"]

    if highest == lowest:
        return 0.5

    k = ((close - lowest) / (highest - lowest)) * 100

    if k < 10:
        return 0.95
    elif k < 20:
        return 0.85
    elif k < 30:
        return 0.75
    elif k < 40:
        return 0.65
    elif k < 50:
        return 0.55
    elif k < 60:
        return 0.45
    elif k < 70:
        return 0.35
    elif k < 80:
        return 0.25
    elif k < 90:
        return 0.15
    else:
        return 0.05

