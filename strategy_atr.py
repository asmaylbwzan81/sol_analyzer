from strategy_support_resistance import calculate_pivot


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
    يحدد SL وTP بناءً على Pivot Points

    LONG:
    - SL = تحت S1 بهامش ATR * 0.3
    - TP = قبل R1 بهامش ATR * 0.3 (أي TP < R1)

    SHORT:
    - SL = فوق R1 بهامش ATR * 0.3
    - TP = فوق S1 بهامش ATR * 0.3 (أي TP > S1)
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

        # هامش = ATR * 0.3 لكن لا يقل عن 0.1% من السعر
        margin = max(atr * 0.3, price * 0.001)

        # ── LONG ──
        # SL تحت S1
        sl_long = s1 - margin

        # TP قبل R1 — يعني TP أصغر من R1
        tp_long = r1 - margin

        # تحقق: لو TP أصغر من السعر الحالي نستخدم ATR
        if tp_long <= price:
            tp_long = price + atr * 1.5
            print(f"⚠️ TP Pivot أصغر من السعر — استخدام ATR: {round(tp_long,4)}")

        # تحقق: لو SL أكبر من السعر الحالي نستخدم ATR
        if sl_long >= price:
            sl_long = price - atr * 1.0
            print(f"⚠️ SL Pivot أكبر من السعر — استخدام ATR: {round(sl_long,4)}")

        # ── SHORT ──
        # SL فوق R1
        sl_short = r1 + margin

        # TP فوق S1 — يعني TP أكبر من S1
        tp_short = s1 + margin

        # تحقق: لو TP أكبر من السعر الحالي نستخدم ATR
        if tp_short >= price:
            tp_short = price - atr * 1.5
            print(f"⚠️ TP Short Pivot أكبر من السعر — استخدام ATR: {round(tp_short,4)}")

        # تحقق: لو SL أصغر من السعر الحالي نستخدم ATR
        if sl_short <= price:
            sl_short = price + atr * 1.0
            print(f"⚠️ SL Short Pivot أصغر من السعر — استخدام ATR: {round(sl_short,4)}")

        print(f"📍 Pivot: PP={pivot['pp']} | R1={r1} | S1={s1}")
        print(f"📍 LONG → SL={round(sl_long,4)} | TP={round(tp_long,4)} (R1={r1})")
        print(f"📍 SHORT → SL={round(sl_short,4)} | TP={round(tp_short,4)} (S1={s1})")

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

