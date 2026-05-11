import json

try:
    with open("config.json") as f:
        config = json.load(f)
except:
    config = {}


def calculate_pivot(candles, period="daily"):
    """
    يحسب Pivot Points من الشمعة السابقة
    يومي = آخر شمعة كاملة
    أسبوعي = آخر 7 شمعات
    """
    if len(candles) < 2:
        return None

    if period == "weekly":
        recent = candles[-8:-1]
        if len(recent) < 2:
            return None
        high = max(float(c["high"]) for c in recent)
        low = min(float(c["low"]) for c in recent)
        close = float(recent[-1]["close"])
    else:
        prev = candles[-2]
        high = float(prev["high"])
        low = float(prev["low"])
        close = float(prev["close"])

    pp = (high + low + close) / 3
    r1 = (2 * pp) - low
    r2 = pp + (high - low)
    s1 = (2 * pp) - high
    s2 = pp - (high - low)

    return {
        "pp": round(pp, 6),
        "r1": round(r1, 6),
        "r2": round(r2, 6),
        "s1": round(s1, 6),
        "s2": round(s2, 6),
    }


def get_pivot_levels(candles):
    daily = calculate_pivot(candles, "daily")
    weekly = calculate_pivot(candles, "weekly")

    if not daily:
        return None

    levels = daily.copy()

    if weekly:
        levels["r1_weekly"] = weekly["r1"]
        levels["r2_weekly"] = weekly["r2"]
        levels["s1_weekly"] = weekly["s1"]
        levels["s2_weekly"] = weekly["s2"]

    return levels


def _detect_bounce(candles, direction="up", lookback=3):
    """
    يكتشف ارتداد حقيقي:
    - direction="up": ارتداد صاعد (عند دعم)
    - direction="down": ارتداد هابط (عند مقاومة)
    - lookback: عدد الشمعات للتحقق
    """
    if len(candles) < lookback + 2:
        return False, 0.0

    recent = candles[-(lookback + 1):]

    if direction == "up":
        # ارتداد صاعد: آخر شمعات تغلق صاعدة وحجم متزايد
        bullish_count = 0
        total_vol = 0
        avg_vol = sum(float(c["volume"]) for c in candles[-20:-lookback]) / max(len(candles[-20:-lookback]), 1)

        for i in range(1, len(recent)):
            c = recent[i]
            if float(c["close"]) > float(c["open"]): # شمعة صاعدة
                bullish_count += 1
            total_vol += float(c["volume"])

        avg_bounce_vol = total_vol / lookback
        vol_ratio = avg_bounce_vol / avg_vol if avg_vol > 0 else 1.0

        # ارتداد حقيقي: أغلبية الشمعات صاعدة + حجم مرتفع
        strength = (bullish_count / lookback) * min(vol_ratio, 2.0) / 2.0
        is_bounce = bullish_count >= 2 and vol_ratio >= 1.0

        return is_bounce, round(strength, 2)

    else:
        # ارتداد هابط: آخر شمعات تغلق هابطة
        bearish_count = 0
        total_vol = 0
        avg_vol = sum(float(c["volume"]) for c in candles[-20:-lookback]) / max(len(candles[-20:-lookback]), 1)

        for i in range(1, len(recent)):
            c = recent[i]
            if float(c["close"]) < float(c["open"]): # شمعة هابطة
                bearish_count += 1
            total_vol += float(c["volume"])

        avg_bounce_vol = total_vol / lookback
        vol_ratio = avg_bounce_vol / avg_vol if avg_vol > 0 else 1.0

        strength = (bearish_count / lookback) * min(vol_ratio, 2.0) / 2.0
        is_bounce = bearish_count >= 2 and vol_ratio >= 1.0

        return is_bounce, round(strength, 2)


def analyze(prices, candles=None):
    """
    يحسب score بناءً على:
    1. موقع السعر من Pivot Points
    2. وجود ارتداد حقيقي عند المستوى
    """
    if candles is None or len(candles) < 5:
        # fallback للطريقة القديمة
        period = config.get("sr_period", 20)
        if len(prices) < period:
            return 0.5
        recent = prices[-period:]
        support = min(recent)
        resistance = max(recent)
        price = prices[-1]
        range_size = resistance - support
        if range_size == 0:
            return 0.5
        position = (price - support) / range_size
        return max(0.0, min(1.0, 1.0 - position))

    pivot = calculate_pivot(candles, "daily")
    if not pivot:
        return 0.5

    price = float(candles[-1]["close"])
    pp = pivot["pp"]
    r1 = pivot["r1"]
    r2 = pivot["r2"]
    s1 = pivot["s1"]
    s2 = pivot["s2"]

    range_size = r2 - s2
    if range_size == 0:
        return 0.5

    margin = range_size * 0.03 # هامش 3%

    # ── كشف الارتداد ──
    bounce_up, bounce_up_strength = _detect_bounce(candles, "up", lookback=3)
    bounce_down, bounce_down_strength = _detect_bounce(candles, "down", lookback=3)

    # ── تحديد الموقع والـ score ──

    # عند S2 — دعم قوي جداً
    if price <= s2 + margin:
        if bounce_up:
            return min(0.95, 0.85 + bounce_up_strength * 0.10) # ارتداد حقيقي = أقوى
        return 0.75 # عند دعم بس بدون ارتداد مؤكد

    # عند S1 — دعم جيد
    elif price <= s1 + margin:
        if bounce_up:
            return min(0.90, 0.78 + bounce_up_strength * 0.10) # ارتداد عند S1
        return 0.65 # عند S1 بس بدون ارتداد

    # تحت PP — منطقة محايدة ميل للصعود
    elif price <= pp + margin:
        return 0.58

    # بين PP وR1 — محايد
    elif price <= r1 - margin:
        return 0.45

    # عند R1 — مقاومة
    elif price <= r1 + margin:
        if bounce_down:
            return max(0.15, 0.25 - bounce_down_strength * 0.10) # ارتداد هابط عند R1
        return 0.30 # عند مقاومة بس بدون ارتداد

    # عند R2 — مقاومة قوية
    elif price <= r2 + margin:
        if bounce_down:
            return max(0.05, 0.15 - bounce_down_strength * 0.10)
        return 0.20

    # فوق R2
    else:
        return 0.10

