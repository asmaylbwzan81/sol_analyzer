def ema(prices, period):
    k = 2 / (period + 1)
    e = prices[0]
    for p in prices[1:]:
        e = p * k + e * (1 - k)
    return e


def analyze(prices):
    if len(prices) < 26:
        return 0.5

    ema12 = ema(prices, 12)
    ema26 = ema(prices, 26)
    macd = ema12 - ema26

    # نحسب نسبة MACD مقارنة بالسعر عشان نعرف قوته
    price = prices[-1]
    macd_pct = (macd / price) * 100 # نسبة مئوية

    if macd_pct > 2.0:
        return 0.95 # صعود قوي جداً
    elif macd_pct > 1.0:
        return 0.85 # صعود قوي
    elif macd_pct > 0.5:
        return 0.75 # صعود واضح
    elif macd_pct > 0.2:
        return 0.65 # صعود خفيف
    elif macd_pct > 0.0:
        return 0.55 # صعود ضعيف
    elif macd_pct > -0.2:
        return 0.45 # نزول ضعيف
    elif macd_pct > -0.5:
        return 0.35 # نزول خفيف
    elif macd_pct > -1.0:
        return 0.25 # نزول واضح
    elif macd_pct > -2.0:
        return 0.15 # نزول قوي
    else:
        return 0.05 # نزول قوي جداً

