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

def analyze(prices, fast=None, slow=None):
    fast = fast or config.get("macd_fast", 12)
    slow = slow or config.get("macd_slow", 26)

    if len(prices) < slow:
        return 0.5

    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    macd = ema_fast - ema_slow

    price = prices[-1]
    macd_pct = (macd / price) * 100

    if macd_pct > 2.0:
        return 0.95
    elif macd_pct > 1.0:
        return 0.85
    elif macd_pct > 0.5:
        return 0.75
    elif macd_pct > 0.2:
        return 0.65
    elif macd_pct > 0.0:
        return 0.55
    elif macd_pct > -0.2:
        return 0.45
    elif macd_pct > -0.5:
        return 0.35
    elif macd_pct > -1.0:
        return 0.25
    elif macd_pct > -2.0:
        return 0.15
    else:
        return 0.05

