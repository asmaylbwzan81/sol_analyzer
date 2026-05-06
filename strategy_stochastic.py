def analyze(candles, period=14):
    if len(candles) < period:
        return 0.5

    recent = candles[-period:]
    highest = max(c["high"] for c in recent)
    lowest = min(c["low"] for c in recent)
    close = candles[-1]["close"]

    if highest == lowest:
        return 0.5

    k = ((close - lowest) / (highest - lowest)) * 100

    if k < 10:
        return 0.95 # oversold قوي جداً → LONG قوي جداً
    elif k < 20:
        return 0.85 # oversold قوي → LONG قوي
    elif k < 30:
        return 0.75 # oversold خفيف → LONG محتمل
    elif k < 40:
        return 0.65 # تحت المنتصف
    elif k < 50:
        return 0.55 # قريب من المنتصف تحت
    elif k < 60:
        return 0.45 # قريب من المنتصف فوق
    elif k < 70:
        return 0.35 # فوق المنتصف
    elif k < 80:
        return 0.25 # overbought خفيف → SHORT محتمل
    elif k < 90:
        return 0.15 # overbought قوي → SHORT قوي
    else:
        return 0.05 # overbought قوي جداً → SHORT قوي جداً

