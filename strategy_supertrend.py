import json

try:
    with open("config.json") as f:
        config = json.load(f)
except:
    config = {}

def analyze(candles, period=None, multiplier=None):
    period = period or config.get("supertrend_period", 10)
    multiplier = multiplier or config.get("supertrend_mult", 3.0)

    if len(candles) < period + 1:
        return 0.5

    # حساب ATR
    trs = []
    for i in range(1, len(candles)):
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        prev_close = float(candles[i-1]["close"])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    atr = sum(trs[-period:]) / period

    # حساب الخطوط
    price = float(candles[-1]["close"])
    high = float(candles[-1]["high"])
    low = float(candles[-1]["low"])
    hl2 = (high + low) / 2

    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)

    # تحديد الاتجاه
    prev_close = float(candles[-2]["close"])
    prev_hl2 = (float(candles[-2]["high"]) + float(candles[-2]["low"])) / 2
    prev_upper = prev_hl2 + (multiplier * atr)
    prev_lower = prev_hl2 - (multiplier * atr)

    if price > lower_band:
        trend = "UP"
    else:
        trend = "DOWN"

    # حساب قوة الإشارة
    if trend == "UP":
        distance = (price - lower_band) / price * 100
        if distance > 3.0:
            return 0.95
        elif distance > 2.0:
            return 0.85
        elif distance > 1.0:
            return 0.75
        elif distance > 0.5:
            return 0.65
        else:
            return 0.55
    else:
        distance = (upper_band - price) / price * 100
        if distance > 3.0:
            return 0.05
        elif distance > 2.0:
            return 0.15
        elif distance > 1.0:
            return 0.25
        elif distance > 0.5:
            return 0.35
        else:
            return 0.45

