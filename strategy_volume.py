def analyze(candles, period=20):
    if len(candles) < period:
        return 0.5

    volumes = [c["volume"] for c in candles]
    avg_vol = sum(volumes[-period:]) / period
    curr_vol = volumes[-1]
    curr_close = candles[-1]["close"]
    prev_close = candles[-2]["close"]

    is_up = curr_close > prev_close
    high_vol = curr_vol > avg_vol * 1.5

    if is_up and high_vol:
        return 0.85
    elif not is_up and high_vol:
        return 0.15
    elif is_up:
        return 0.60
    else:
        return 0.40
