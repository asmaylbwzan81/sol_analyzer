import json

try:
    with open("config.json") as f:
        config = json.load(f)
except:
    config = {}

def analyze(candles, tenkan=None, kijun=None, senkou_b=None):
    t = tenkan or config.get("ichi_tenkan", 9)
    k = kijun or config.get("ichi_kijun", 26)
    s = senkou_b or config.get("ichi_senkou_b", 52)

    if len(candles) < s + 1:
        return 0.5

    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]

    tenkan_val = (max(highs[-t:]) + min(lows[-t:])) / 2
    kijun_val = (max(highs[-k:]) + min(lows[-k:])) / 2
    senkou_a = (tenkan_val + kijun_val) / 2
    senkou_b_val = (max(highs[-s:]) + min(lows[-s:])) / 2

    cloud_top = max(senkou_a, senkou_b_val)
    cloud_bot = min(senkou_a, senkou_b_val)

    price = closes[-1]
    chikou = closes[-1]
    past_price = closes[-k] if len(closes) > k else closes[0]

    score = 0.5

    # 1. السعر فوق/تحت السحابة (أهم إشارة) ±0.20
    if price > cloud_top:
        score += 0.20
    elif price < cloud_bot:
        score -= 0.20
    else:
        score -= 0.05 # داخل السحابة = ضبابي

    # 2. Tenkan فوق Kijun ±0.10
    if tenkan_val > kijun_val:
        score += 0.10
    else:
        score -= 0.10

    # 3. السعر فوق Kijun ±0.08
    if price > kijun_val:
        score += 0.08
    else:
        score -= 0.08

    # 4. السعر فوق Tenkan ±0.05
    if price > tenkan_val:
        score += 0.05
    else:
        score -= 0.05

    # 5. Chikou فوق سعر الماضي ±0.07
    if chikou > past_price:
        score += 0.07
    else:
        score -= 0.07

    return round(max(0.0, min(1.0, score)), 4)
