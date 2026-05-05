def analyze(candles, period=14):
    if len(candles) < period:
        return 0.5

    recent = candles[-period:]
    highest = max(c["high"] for c in recent)
    lowest = min(c["low"] for c in recent)
    close = candles[-1]["close"]

    if highest == lowest:
        return 0.5

    k = ((close - lowest) / (highest - lowest)) * 100

    if k < 20:
        return 0.85
    elif k < 35:
        return 0.65
    elif k > 80:
        return 0.15
    elif k > 65:
        return 0.35
    return 0.5
