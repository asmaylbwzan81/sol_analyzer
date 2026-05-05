def analyze(candles, period=14):
    if len(candles) < period + 1:
        return 0.5

    trs, plus_dms, minus_dms = [], [], []

    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i-1]["close"]
        prev_high = candles[i-1]["high"]
        prev_low = candles[i-1]["low"]

        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        plus_dm = max(high - prev_high, 0) if (high - prev_high) > (prev_low - low) else 0
        minus_dm = max(prev_low - low, 0) if (prev_low - low) > (high - prev_high) else 0

        trs.append(tr)
        plus_dms.append(plus_dm)
        minus_dms.append(minus_dm)

    atr = sum(trs[-period:]) / period
    if atr == 0:
        return 0.5

    plus_di = (sum(plus_dms[-period:]) / period) / atr * 100
    minus_di = (sum(minus_dms[-period:]) / period) / atr * 100

    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
    adx = dx

    if adx > 25:
        if plus_di > minus_di:
            return 0.80
        else:
            return 0.20
    return 0.5
