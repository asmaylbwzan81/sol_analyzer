def analyze(prices, period=10):
    if len(prices) < period:
        return 0.5

    momentum = prices[-1] - prices[-period]
    pct = momentum / prices[-period]

    if pct > 0.05:
        return 0.95 # زخم صاعد قوي جداً
    elif pct > 0.03:
        return 0.85 # زخم صاعد قوي
    elif pct > 0.02:
        return 0.75 # زخم صاعد واضح
    elif pct > 0.01:
        return 0.65 # زخم صاعد خفيف
    elif pct > 0.0:
        return 0.55 # زخم صاعد ضعيف
    elif pct > -0.01:
        return 0.45 # زخم نازل ضعيف
    elif pct > -0.02:
        return 0.35 # زخم نازل خفيف
    elif pct > -0.03:
        return 0.25 # زخم نازل واضح
    elif pct > -0.05:
        return 0.15 # زخم نازل قوي
    else:
        return 0.05 # زخم نازل قوي جداً

