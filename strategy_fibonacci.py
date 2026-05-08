import json

try:
    with open("config.json") as f:
        config = json.load(f)
except:
    config = {}

def analyze(prices, period=None):
    period = period or config.get("fibonacci_period", 50)

    if len(prices) < period:
        return 0.5

    recent = prices[-period:]
    high = max(recent)
    low = min(recent)
    price = prices[-1]

    diff = high - low
    if diff == 0:
        return 0.5

    levels = {
        "0.236": high - diff * 0.236,
        "0.382": high - diff * 0.382,
        "0.500": high - diff * 0.500,
        "0.618": high - diff * 0.618,
        "0.786": high - diff * 0.786,
    }

    tolerance = diff * 0.02

    for name, level in levels.items():
        if abs(price - level) < tolerance:
            position = (price - low) / diff
            if name == "0.786":
                return 0.90 if position < 0.5 else 0.10
            elif name == "0.618":
                return 0.80 if position < 0.5 else 0.20
            elif name == "0.500":
                return 0.60 if position < 0.5 else 0.40
            elif name == "0.382":
                return 0.70 if position < 0.5 else 0.30
            elif name == "0.236":
                return 0.65 if position < 0.5 else 0.35

    position = (price - low) / diff

    if position < 0.10:
        return 0.95
    elif position < 0.25:
        return 0.75
    elif position < 0.40:
        return 0.62
    elif position < 0.60:
        return 0.50
    elif position < 0.75:
        return 0.38
    elif position < 0.90:
        return 0.25
    else:
        return 0.05

