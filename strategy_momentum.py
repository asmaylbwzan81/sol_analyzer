import json

try:
    with open("config.json") as f:
        config = json.load(f)
except:
    config = {}

def analyze(prices, period=None):
    period = period or config.get("momentum_period", 10)

    if len(prices) < period:
        return 0.5

    momentum = prices[-1] - prices[-period]
    pct = momentum / prices[-period]

    if pct > 0.05:
        return 0.95
    elif pct > 0.03:
        return 0.85
    elif pct > 0.02:
        return 0.75
    elif pct > 0.01:
        return 0.65
    elif pct > 0.0:
        return 0.55
    elif pct > -0.01:
        return 0.45
    elif pct > -0.02:
        return 0.35
    elif pct > -0.03:
        return 0.25
    elif pct > -0.05:
        return 0.15
    else:
        return 0.05

