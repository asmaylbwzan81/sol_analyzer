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
        # آخر 7 شمعات
        recent = candles[-8:-1]
        if len(recent) < 2:
            return None
        high = max(float(c["high"]) for c in recent)
        low = min(float(c["low"]) for c in recent)
        close = float(recent[-1]["close"])
    else:
        # الشمعة اليومية السابقة
        prev = candles[-2]
        high = float(prev["high"])
        low = float(prev["low"])
        close = float(prev["close"])

    # حساب Pivot Point الرئيسي
    pp = (high + low + close) / 3

    # مستويات المقاومة
    r1 = (2 * pp) - low
    r2 = pp + (high - low)

    # مستويات الدعم
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
    """
    يرجع أفضل مستويات دعم ومقاومة
    يدمج اليومي والأسبوعي
    """
    daily = calculate_pivot(candles, "daily")
    weekly = calculate_pivot(candles, "weekly")

    if not daily:
        return None

    # استخدام اليومي كأساس
    levels = daily.copy()

    # لو عندنا أسبوعي، نضيف مستويات إضافية
    if weekly:
        levels["r1_weekly"] = weekly["r1"]
        levels["r2_weekly"] = weekly["r2"]
        levels["s1_weekly"] = weekly["s1"]
        levels["s2_weekly"] = weekly["s2"]

    return levels


def analyze(prices, candles=None):
    """
    يحسب score بناءً على موقع السعر من Pivot Points
    قريب من دعم → score عالي (LONG)
    قريب من مقاومة → score منخفض (SHORT)
    """
    if candles is None or len(candles) < 3:
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

    # ── تحديد الموقع والـ score ──
    # قريب من S2 = دعم قوي جداً = LONG قوي
    # قريب من R2 = مقاومة قوية = SHORT قوي

    margin = range_size * 0.03 # 3% هامش

    if price <= s2 + margin:
        return 0.95 # عند دعم قوي جداً → LONG
    elif price <= s1 + margin:
        return 0.80 # عند دعم جيد → LONG
    elif price <= pp + margin:
        return 0.60 # تحت Pivot → ميل للصعود
    elif price <= r1 - margin:
        return 0.45 # بين PP وR1 → محايد
    elif price <= r1 + margin:
        return 0.30 # عند مقاومة → احذر من LONG
    elif price <= r2 - margin:
        return 0.25 # قريب من R2 → SHORT
    else:
        return 0.10 # فوق R2 → مقاومة قوية جداً → SHORT

