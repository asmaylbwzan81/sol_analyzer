def analyze(prices, period=20):
    if len(prices) < period:
        return 0.5

    recent = prices[-period:]
    avg = sum(recent) / period
    std = (sum((p - avg) ** 2 for p in recent) / period) ** 0.5

    upper = avg + 2 * std
    lower = avg - 2 * std
    price = prices[-1]

    # نسبة موقع السعر داخل النطاق
    band_range = upper - lower
    if band_range == 0:
        return 0.5

    position = (price - lower) / band_range # 0.0 = أسفل النطاق, 1.0 = أعلى النطاق

    if price < lower:
        return 0.95 # تحت النطاق السفلي → LONG قوي جداً
    elif position < 0.15:
        return 0.85 # قريب جداً من السفلي → LONG قوي
    elif position < 0.30:
        return 0.70 # في الربع السفلي → LONG محتمل
    elif position < 0.45:
        return 0.60 # تحت المتوسط قليلاً
    elif position < 0.55:
        return 0.50 # حول المتوسط → محايد
    elif position < 0.70:
        return 0.40 # فوق المتوسط قليلاً
    elif position < 0.85:
        return 0.30 # في الربع العلوي → SHORT محتمل
    elif position < 1.0:
        return 0.15 # قريب جداً من العلوي → SHORT قوي
    else:
        return 0.05 # فوق النطاق العلوي → SHORT قوي جداً
