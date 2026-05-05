def analyze(prices, period=20):
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

    if position < 0.15:
        return 0.85
    elif position < 0.35:
        return 0.65
    elif position > 0.85:
        return 0.15
    elif position > 0.65:
        return 0.35
    return 0.5
