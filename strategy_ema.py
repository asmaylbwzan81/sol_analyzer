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

    score = 0.5

    if price > ema20:
        score += 0.15
    else:
        score -= 0.15

    if price > ema50:
        score += 0.15
    else:
        score -= 0.15

    if ema20 > ema50:
        score += 0.1
    else:
        score -= 0.1

    return max(0.0, min(1.0, score))
