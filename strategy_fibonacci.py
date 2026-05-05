def analyze(prices, period=50):
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
            if position < 0.5:
                return 0.75
            else:
                return 0.30

    position = (price - low) / diff
    if position < 0.3:
        return 0.70
    elif position > 0.7:
        return 0.30
    return 0.5
