def analyze(prices, period=14):
    if len(prices) < period + 1:
        return 0.5

    gains, losses = [], []
    for i in range(1, period + 1):
        diff = prices[-i] - prices[-i-1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))

    avg_gain = sum(gains) / period if gains else 0.001
    avg_loss = sum(losses) / period if losses else 0.001

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    if rsi < 30:
        return 0.85
    elif rsi < 40:
        return 0.65
    elif rsi > 70:
        return 0.15
    elif rsi > 60:
        return 0.35
    return 0.5
