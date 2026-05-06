def analyze(prices, period=50):
    if len(prices) < period:
        return 0.5

    recent = prices[-period:]
    high = max(recent)
    low = min(recent)
    price = prices[-1]

    diff = high - low
    if diff == 0:
        return 0.5

    levels = {
        "0.236": high - diff * 0.236,
        "0.382": high - diff * 0.382,
        "0.500": high - diff * 0.500,
        "0.618": high - diff * 0.618,
        "0.786": high - diff * 0.786,
    }

    tolerance = diff * 0.02

    # إذا السعر عند مستوى فيبوناتشي
    for name, level in levels.items():
        if abs(price - level) < tolerance:
            position = (price - low) / diff
            if name == "0.786":
                return 0.90 if position < 0.5 else 0.10 # دعم/مقاومة قوي جداً
            elif name == "0.618":
                return 0.80 if position < 0.5 else 0.20 # دعم/مقاومة قوي
            elif name == "0.500":
                return 0.60 if position < 0.5 else 0.40 # منتصف
            elif name == "0.382":
                return 0.70 if position < 0.5 else 0.30 # دعم/مقاومة متوسط
            elif name == "0.236":
                return 0.65 if position < 0.5 else 0.35 # دعم/مقاومة خفيف

    # السعر بين المستويات
    position = (price - low) / diff

    if position < 0.10:
        return 0.95 # قريب جداً من القاع
    elif position < 0.25:
        return 0.75 # في الربع السفلي
    elif position < 0.40:
        return 0.62 # تحت المنتصف
    elif position < 0.60:
        return 0.50 # في المنتصف
    elif position < 0.75:
        return 0.38 # فوق المنتصف
    elif position < 0.90:
        return 0.25 # في الربع العلوي
    else:
        return 0.05 # قريب جداً من القمة

