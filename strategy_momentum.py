def analyze(prices, period=10):
    if len(prices) < period:
        return 0.5

    momentum = prices[-1] - prices[-period]
    pct = momentum / prices[-period]

    if pct > 0.03:
        return 0.85
    elif pct > 0.01:
        return 0.65
    elif pct < -0.03:
        return 0.15
    elif pct < -0.01:
        return 0.35
    return 0.5
