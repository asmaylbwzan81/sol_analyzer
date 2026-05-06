def analyze(candles, period=10, multiplier=3.0):
    """
    Supertrend Indicator
    - period: فترة ATR (افتراضي 10)
    - multiplier: مضاعف ATR (افتراضي 3.0)
    """
    if len(candles) < period + 1:
        return 0.5

    # ── حساب ATR ──
    trs = []
    for i in range(1, len(candles)):
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        prev_close = float(candles[i-1]["close"])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    atr = sum(trs[-period:]) / period

    # ── حساب الخطوط ──
    price = float(candles[-1]["close"])
    high = float(candles[-1]["high"])
    low = float(candles[-1]["low"])
    hl2 = (high + low) / 2

    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)

    # ── تحديد الاتجاه ──
    prev_close = float(candles[-2]["close"])
    prev_hl2 = (float(candles[-2]["high"]) + float(candles[-2]["low"])) / 2
    prev_upper = prev_hl2 + (multiplier * atr)
    prev_lower = prev_hl2 - (multiplier * atr)

    # السعر فوق الخط السفلي = صاعد
    # السعر تحت الخط العلوي = نازل
    if price > lower_band:
        trend = "UP"
    else:
        trend = "DOWN"

    # ── حساب قوة الإشارة ──
    # بعد السعر عن خط Supertrend
    if trend == "UP":
        distance = (price - lower_band) / price * 100
        if distance > 3.0:
            return 0.95 # صعود قوي جداً
        elif distance > 2.0:
            return 0.85 # صعود قوي
        elif distance > 1.0:
            return 0.75 # صعود واضح
        elif distance > 0.5:
            return 0.65 # صعود خفيف
        else:
            return 0.55 # بداية صعود
    else:
        distance = (upper_band - price) / price * 100
        if distance > 3.0:
            return 0.05 # نزول قوي جداً
        elif distance > 2.0:
            return 0.15 # نزول قوي
        elif distance > 1.0:
            return 0.25 # نزول واضح
        elif distance > 0.5:
            return 0.35 # نزول خفيف
        else:
            return 0.45 # بداية نزول

