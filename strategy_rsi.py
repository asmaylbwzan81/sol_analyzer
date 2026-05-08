import json

try:
    with open("config.json") as f:
        config = json.load(f)
except:
    config = {}

def analyze(prices, period=None):
    period = period or config.get("rsi_period", 14)

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

    if rsi < 20:
        return 0.95
    elif rsi < 30:
        return 0.85
    elif rsi < 40:
        return 0.70
    elif rsi < 45:
        return 0.60
    elif rsi < 55:
        return 0.50
    elif rsi < 60:
        return 0.40
    elif rsi < 70:
        return 0.30
    elif rsi < 80:
        return 0.15
    else:
        return 0.05

