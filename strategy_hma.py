import json

try:
    with open("config.json") as f:
        config = json.load(f)
except:
    config = {}


def wma(prices, period):
    """Weighted Moving Average — أساس حساب HMA"""
    if len(prices) < period:
        return prices[-1]
    weights = list(range(1, period + 1))
    total = sum(weights)
    subset = prices[-period:]
    return sum(p * w for p, w in zip(subset, weights)) / total


def hma(prices, period):
    """
    Hull Moving Average — أسرع وأقل lagging من EMA
    HMA = WMA(2 × WMA(n/2) − WMA(n), √n)
    """
    if len(prices) < period:
        return prices[-1]

    half = max(1, period // 2)
    sqrt_period = max(1, int(period ** 0.5))

    wma_half = wma(prices, half)
    wma_full = wma(prices, period)

    # بناء سلسلة مؤقتة
    diff = 2 * wma_half - wma_full

    # نحتاج sqrt_period قيم للحساب الأخير
    diffs = []
    for i in range(sqrt_period):
        idx = -(sqrt_period - i)
        sub = prices[:idx] if idx != 0 else prices
        if len(sub) < period:
            diffs.append(diff)
            continue
        h = max(1, len(sub) // 2)
        d = 2 * wma(sub, h) - wma(sub, period)
        diffs.append(d)

    return wma(diffs, sqrt_period)


def analyze(prices, short=None, long=None):
    short = short or config.get("hma_short", 20)
    long = long or config.get("hma_long", 50)

    if len(prices) < long:
        return 0.5

    price = prices[-1]
    hma_short = hma(prices[-short * 2:], short)
    hma_long = hma(prices[-long * 2:], long)

    pct_short = (price - hma_short) / hma_short * 100
    pct_long = (price - hma_long) / hma_long * 100

    score = 0.5

    if pct_short > 3.0:
        score += 0.20
    elif pct_short > 1.5:
        score += 0.15
    elif pct_short > 0.5:
        score += 0.10
    elif pct_short > 0.0:
        score += 0.05
    elif pct_short > -0.5:
        score -= 0.05
    elif pct_short > -1.5:
        score -= 0.10
    elif pct_short > -3.0:
        score -= 0.15
    else:
        score -= 0.20

    if pct_long > 3.0:
        score += 0.20
    elif pct_long > 1.5:
        score += 0.15
    elif pct_long > 0.5:
        score += 0.10
    elif pct_long > 0.0:
        score += 0.05
    elif pct_long > -0.5:
        score -= 0.05
    elif pct_long > -1.5:
        score -= 0.10
    elif pct_long > -3.0:
        score -= 0.15
    else:
        score -= 0.20

    return max(0.0, min(1.0, score))

