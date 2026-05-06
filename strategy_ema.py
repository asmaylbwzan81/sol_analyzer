def ema(prices, period):
    k = 2 / (period + 1)
    e = prices[0]
    for p in prices[1:]:
        e = p * k + e * (1 - k)
    return e


def analyze(prices):
    if len(prices) < 50:
        return 0.5

    price = prices[-1]
    ema20 = ema(prices[-20:], 20)
    ema50 = ema(prices[-50:], 50)

    # نسبة السعر فوق/تحت المتوسطات
    pct20 = (price - ema20) / ema20 * 100
    pct50 = (price - ema50) / ema50 * 100

    score = 0.5

    # علاقة السعر مع EMA20
    if pct20 > 3.0:
        score += 0.20
    elif pct20 > 1.5:
        score += 0.15
    elif pct20 > 0.5:
        score += 0.10
    elif pct20 > 0.0:
        score += 0.05
    elif pct20 > -0.5:
        score -= 0.05
    elif pct20 > -1.5:
        score -= 0.10
    elif pct20 > -3.0:
        score -= 0.15
    else:
        score -= 0.20

    # علاقة السعر مع EMA50
    if pct50 > 3.0:
        score += 0.20
    elif pct50 > 1.5:
        score += 0.15
    elif pct50 > 0.5:
        score += 0.10
    elif pct50 > 0.0:
        score += 0.05
    elif pct50 > -0.5:
        score -= 0.05
    elif pct50 > -1.5:
        score -= 0.10
    elif pct50 > -3.0:
        score -= 0.15
    else:
        score -= 0.20

    # علاقة EMA20 مع EMA50 (الاتجاه العام)
    if ema20 > ema50:
        score += 0.10 # اتجاه صاعد
    else:
        score -= 0.10 # اتجاه نازل

    return round(max(0.0, min(1.0, score)), 2)

