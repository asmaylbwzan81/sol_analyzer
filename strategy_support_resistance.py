import json

try:
    with open("config.json") as f:
        config = json.load(f)
except:
    config = {}

def analyze(prices, period=None):
    period = period or config.get("sr_period", 20)

    if len(prices) < period:
        return 0.5

    recent = prices[-period:]
    support = min(recent)
    resistance = max(recent)
    price = prices[-1]

    range_size = resistance - support
    if range_size == 0:
        return 0.5

    position = (price - support) / range_size

    if position < 0.05:
        return 0.95
    elif position < 0.15:
        return 0.85
    elif position < 0.25:
        return 0.75
    elif position < 0.35:
        return 0.65
    elif position < 0.45:
        return 0.58
    elif position < 0.55:
        return 0.50
    elif position < 0.65:
        return 0.42
    elif position < 0.75:
        return 0.35
    elif position < 0.85:
        return 0.25
    elif position < 0.95:
        return 0.15
    else:
        return 0.05

