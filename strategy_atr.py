أنا

from strategy_support_resistance import calculate_pivot, get_pivot_levels


def calculate_atr(candles, period=14):
    if len(candles) < period + 1:
        return None

    trs = []
    for i in range(1, len(candles)):
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        prev_close = float(candles[i-1]["close"])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    return sum(trs[-period:]) / period


def get_levels(candles):
    """
    يحدد SL وTP بناءً على Pivot Points + ATR

    LONG:
    - SL = تحت S1 (دعم قوي صعب ينكسر)
    - TP = قبل R1 بهامش صغير

    SHORT:
    - SL = فوق R1 (مقاومة قوية صعبة تكسر)
    - TP = فوق S1 بهامش صغير
    """
    atr = calculate_atr(candles)
    if not atr:
        return None, None, None, None

    price = float(candles[-1]["close"])
    atr = float(atr)

    # ── محاولة استخدام Pivot Points ──
    pivot = calculate_pivot(candles, "daily")

    if pivot:
        r1 = pivot["r1"]
        r2 = pivot["r2"]
        s1 = pivot["s1"]
        s2 = pivot["s2"]

        margin = atr * 0.3 # هامش أمان = 30% من ATR

        # ── LONG ──
        # SL تحت S1 — لو S1 بعيد جداً نستخدم ATR كحد أقصى
        sl_long_pivot = s1 - margin
        sl_long_atr = price - atr * 1.5
        sl_long = max(sl_long_pivot, sl_long_atr) # الأقرب للسعر

        # TP قبل R1 — لو R1 قريب جداً نستخدم ATR كحد أدنى
        tp_long_pivot = r1 - margin
        tp_long_atr = price + atr * 1.0
        tp_long = max(tp_long_pivot, tp_long_atr) # الأبعد

        # ── SHORT ──
        # SL فوق R1
        sl_short_pivot = r1 + margin
        sl_short_atr = price + atr * 1.5
        sl_short = min(sl_short_pivot, sl_short_atr) # الأقرب للسعر

        # TP فوق S1
        tp_short_pivot = s1 + margin
        tp_short_atr = price - atr * 1.0
        tp_short = min(tp_short_pivot, tp_short_atr) # الأبعد

        print(f"📍 Pivot: PP={pivot['pp']} | R1={r1} | S1={s1}")
        print(f"📍 LONG → SL={round(sl_long,4)} | TP={round(tp_long,4)}")
        print(f"📍 SHORT → SL={round(sl_short,4)} | TP={round(tp_short,4)}")

    else:
        # Fallback لـ ATR لو ما في Pivot
        print("⚠️ Pivot غير متاح — استخدام ATR")
        sl_long = price - atr * 1.0
        sl_short = price + atr * 1.0
        tp_long = price + atr * 1.5
        tp_short = price - atr * 1.5

    return (
        round(sl_long, 4),
        round(sl_short, 4),
        round(tp_long, 4),
        round(tp_short, 4),
    )


def analyze(candles):
    return 0.5

