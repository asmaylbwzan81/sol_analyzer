import json

try:
    with open("config.json") as f:
        config = json.load(f)
except:
    config = {}

def analyze(prices, period=None):
    period = period or config.get("bollinger_period", 20)

    if len(prices) < period:
        return 0.5

    recent = prices[-period:]
    avg = sum(recent) / period
    std = (sum((p - avg) ** 2 for p in recent) / period) ** 0.5

    upper = avg + 2 * std
    lower = avg - 2 * std
    price = prices[-1]

    band_range = upper - lower
    if band_range == 0:
        return 0.5

    position = (price - lower) / band_range

    if price < lower:
        return 0.95
    elif position < 0.15:
        return 0.85
    elif position < 0.30:
        return 0.70
    elif position < 0.45:
        return 0.60
    elif position < 0.55:
        return 0.50
    elif position < 0.70:
        return 0.40
    elif position < 0.85:
        return 0.30
    elif position < 1.0:
        return 0.15
    else:
        return 0.05

