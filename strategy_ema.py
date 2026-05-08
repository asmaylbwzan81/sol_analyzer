import json

try:
    with open("config.json") as f:
        config = json.load(f)
except:
    config = {}

def ema(prices, period):
    k = 2 / (period + 1)
    e = prices[0]
    for p in prices[1:]:
        e = p * k + e * (1 - k)
    return e

def analyze(prices, short=None, long=None):
    short = short or config.get("ema_short", 20)
    long = long or config.get("ema_long", 50)

    if len(prices) < long:
        return 0.5

    price = prices[-1]
    ema_short = ema(prices[-short:], short)
    ema_long = ema(prices[-long:], long)

    pct_short = (price - ema_short) / ema_short * 100
    pct_long = (price - ema_long) / ema_long * 100

    score = 0.5

    if pct_short > 3.0:
        score += 0.20
    elif pct_short > 1.5:
        score += 0.15
    elif pct_short > 0.5:
        score += 0.10
    elif pct_short > 0.0:
        score += 0.05
    elif pct_short > -0.5:
        score -= 0.05
    elif pct_short > -1.5:
        score -= 0.10
    elif pct_short > -3.0:
        score -= 0.15
    else:
        score -= 0.20

    if pct_long > 3.0:
        score += 0.20
    elif pct_long > 1.5:
        score += 0.15
    elif pct_long > 0.5:
        score += 0.10
    elif pct_long > 0.0:
        score += 0.05
    elif pct_long > -0.5:
        score -= 0.05
    elif pct_long > -1.5:
        score -= 0.10
    elif pct_long > -3.0:
        score -= 0.15
    else:
        score -= 0.20

    return max(0.0, min(1.0, score))

