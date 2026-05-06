def analyze(prices, period=20):
    if len(prices) < period:
        return 0.5

    recent = prices[-period:]
    support = min(recent)
    resistance = max(recent)
    price = prices[-1]

    range_size = resistance - support
    if range_size == 0:
        return 0.5

    position = (price - support) / range_size # 0.0 = عند الدعم, 1.0 = عند المقاومة

    if position < 0.05:
        return 0.95 # عند الدعم تماماً → LONG قوي جداً
    elif position < 0.15:
        return 0.85 # قريب جداً من الدعم → LONG قوي
    elif position < 0.25:
        return 0.75 # في منطقة الدعم → LONG محتمل
    elif position < 0.35:
        return 0.65 # تحت المنتصف قليلاً
    elif position < 0.45:
        return 0.58 # قريب من المنتصف تحت
    elif position < 0.55:
        return 0.50 # في المنتصف → محايد
    elif position < 0.65:
        return 0.42 # قريب من المنتصف فوق
    elif position < 0.75:
        return 0.35 # فوق المنتصف قليلاً
    elif position < 0.85:
        return 0.25 # في منطقة المقاومة → SHORT محتمل
    elif position < 0.95:
        return 0.15 # قريب جداً من المقاومة → SHORT قوي
    else:
        return 0.05 # عند المقاومة تماماً → SHORT قوي جداً

