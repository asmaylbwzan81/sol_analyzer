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
    diff_pct = (price - vwap) / vwap

    if diff_pct > 0.02:
        return 0.25
    elif diff_pct > 0:
        return 0.55
    elif diff_pct < -0.02:
        return 0.75
    else:
        return 0.45
