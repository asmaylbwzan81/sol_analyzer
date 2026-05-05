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

    if macd > 0:
        return 0.75
    elif macd < 0:
        return 0.25
    return 0.5
