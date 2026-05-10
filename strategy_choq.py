import json
import math

try:
    with open("config.json") as f:
        config = json.load(f)
except:
    config = {}


def analyze(candles, period=None):
    """
    Choppiness Index — يحدد هل السوق في ترند أو تذبذب
    CHOP < 38.2 = ترند قوي ✅
    CHOP > 61.8 = سوق متذبذب ❌
    """
    period = period or config.get("chop_period", 14)

    if len(candles) < period + 1:
        return 0.5

    # حساب ATR لكل شمعة
    trs = []
    for i in range(1, len(candles)):
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        prev_close = float(candles[i-1]["close"])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    # مجموع ATR للـ period الأخيرة
    atr_sum = sum(trs[-period:])

    # أعلى وأدنى سعر خلال الـ period
    recent = candles[-period:]
    highest_high = max(float(c["high"]) for c in recent)
    lowest_low = min(float(c["low"]) for c in recent)

    price_range = highest_high - lowest_low

    if price_range == 0 or atr_sum == 0:
        return 0.5

    # حساب CHOP
    chop = 100 * math.log10(atr_sum / price_range) / math.log10(period)

    # تحديد الاتجاه من آخر شمعتين
    last_close = float(candles[-1]["close"])
    prev_close = float(candles[-2]["close"])
    trend_up = last_close > prev_close

    # تحويل CHOP لسكور 0-1
    if chop < 38.2:
        # ترند قوي جداً
        if trend_up:
            return 0.95
        else:
            return 0.05
    elif chop < 45:
        # ترند جيد
        if trend_up:
            return 0.85
        else:
            return 0.15
    elif chop < 50:
        # ترند متوسط
        if trend_up:
            return 0.75
        else:
            return 0.25
    elif chop < 55:
        # ترند ضعيف
        if trend_up:
            return 0.65
        else:
            return 0.35
    elif chop < 61.8:
        # قريب من التذبذب
        return 0.50
    else:
        # سوق متذبذب — لا ترند
        return 0.50

