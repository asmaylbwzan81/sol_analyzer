def analyze(candles, period=20):
    if len(candles) < period:
        return 0.5

    volumes = [c["volume"] for c in candles]
    avg_vol = sum(volumes[-period:]) / period
    curr_vol = volumes[-1]
    curr_close = candles[-1]["close"]
    prev_close = candles[-2]["close"]

    is_up = curr_close > prev_close
    vol_ratio = curr_vol / avg_vol # نسبة الحجم مقارنة بالمتوسط

    if is_up:
        if vol_ratio > 3.0:
            return 0.95 # صعود بحجم ضخم جداً
        elif vol_ratio > 2.0:
            return 0.85 # صعود بحجم ضخم
        elif vol_ratio > 1.5:
            return 0.75 # صعود بحجم عالي
        elif vol_ratio > 1.0:
            return 0.65 # صعود بحجم طبيعي
        else:
            return 0.55 # صعود بحجم ضعيف
    else:
        if vol_ratio > 3.0:
            return 0.05 # نزول بحجم ضخم جداً
        elif vol_ratio > 2.0:
            return 0.15 # نزول بحجم ضخم
        elif vol_ratio > 1.5:
            return 0.25 # نزول بحجم عالي
        elif vol_ratio > 1.0:
            return 0.35 # نزول بحجم طبيعي
        else:
            return 0.45 # نزول بحجم ضعيف

