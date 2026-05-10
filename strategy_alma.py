import json
import math

try:
    with open("config.json") as f:
        config = json.load(f)
except:
    config = {}


def alma(prices, period=None, sigma=None, offset=None):
    """
    Arnaud Legoux Moving Average
    أسرع من EMA وأقل إشارات كاذبة
    """
    period = period or 20
    sigma = sigma or 6.0
    offset = offset or 0.85

    if len(prices) < period:
        return prices[-1]

    m = offset * (period - 1)
    s = period / sigma
    weights = [math.exp(-((i - m) ** 2) / (2 * s * s)) for i in range(period)]
    total = sum(weights)

    subset = prices[-period:]
    return sum(p * w for p, w in zip(subset, weights)) / total


def analyze(candles, period=None, sigma=None, offset=None):
    period = period or config.get("alma_period", 20)
    sigma = sigma or config.get("alma_sigma", 6.0)
    offset = offset or config.get("alma_offset", 0.85)

    if len(candles) < period + 1:
        return 0.5

    prices = [float(c["close"]) for c in candles]
    price = prices[-1]

    # ALMA الحالي والسابق
    alma_now = alma(prices, period, sigma, offset)
    alma_prev = alma(prices[:-1], period, sigma, offset)

    # اتجاه ALMA
    if alma_now > alma_prev:
        trend = "UP"
    else:
        trend = "DOWN"

    # المسافة بين السعر وALMA
    distance = (price - alma_now) / alma_now * 100

    if trend == "UP":
        if distance > 3.0:
            return 0.95
        elif distance > 2.0:
            return 0.85
        elif distance > 1.0:
            return 0.75
        elif distance > 0.5:
            return 0.65
        elif distance > 0.0:
            return 0.55
        else:
            return 0.45
    else:
        if distance < -3.0:
            return 0.05
        elif distance < -2.0:
            return 0.15
        elif distance < -1.0:
            return 0.25
        elif distance < -0.5:
            return 0.35
        elif distance < 0.0:
            return 0.45
        else:
            return 0.55

