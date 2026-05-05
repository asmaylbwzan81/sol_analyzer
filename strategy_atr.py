def calculate_atr(candles, period=14):
    if len(candles) < period + 1:
        return None

    trs = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i-1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    return sum(trs[-period:]) / period

def get_levels(candles):
    atr = calculate_atr(candles)
    if not atr:
        return None, None, None, None

    price = candles[-1]["close"]

    sl_long = round(price - atr * 1.0, 4)
    sl_short = round(price + atr * 1.0, 4)
    tp_long = round(price + atr * 1.5, 4)
    tp_short = round(price - atr * 1.5, 4)

    return sl_long, sl_short, tp_long, tp_short

def analyze(candles):
    return 0.5
