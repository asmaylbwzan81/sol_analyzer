def analyze(prices, period=20):
    if len(prices) < period:
        return 0.5

    recent = prices[-period:]
    avg = sum(recent) / period
    std = (sum((p - avg) ** 2 for p in recent) / period) ** 0.5

    upper = avg + 2 * std
    lower = avg - 2 * std
    price = prices[-1]

    if price < lower:
        return 0.85
    elif price > upper:
        return 0.15
    elif price < avg:
        return 0.55
    else:
        return 0.45
