def analyze(candles):
    if len(candles) < 2:
        return 0.5

    total_volume = sum(c["volume"] for c in candles)
    if total_volume == 0:
        return 0.5

    vwap = sum(
        ((c["high"] + c["low"] + c["close"]) / 3) * c["volume"]
        for c in candles
    ) / total_volume

    price = candles[-1]["close"]
    diff_pct = (price - vwap) / vwap # موجب = فوق VWAP, سالب = تحت VWAP

    # فوق VWAP = صعود، تحت VWAP = نزول
    if diff_pct > 0.05:
        return 0.95 # فوق VWAP بكثير → LONG قوي جداً
    elif diff_pct > 0.03:
        return 0.85 # فوق VWAP بوضوح → LONG قوي
    elif diff_pct > 0.02:
        return 0.75 # فوق VWAP → LONG محتمل
    elif diff_pct > 0.01:
        return 0.65 # فوق VWAP قليلاً
    elif diff_pct > 0.0:
        return 0.55 # فوق VWAP بشكل ضعيف
    elif diff_pct > -0.01:
        return 0.45 # تحت VWAP بشكل ضعيف
    elif diff_pct > -0.02:
        return 0.35 # تحت VWAP قليلاً
    elif diff_pct > -0.03:
        return 0.25 # تحت VWAP → SHORT محتمل
    elif diff_pct > -0.05:
        return 0.15 # تحت VWAP بوضوح → SHORT قوي
    else:
        return 0.05 # تحت VWAP بكثير → SHORT قوي جداً

