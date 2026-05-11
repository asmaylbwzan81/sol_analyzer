from strategy_support_resistance import calculate_pivot


def calculate_atr(candles, period=14):
    """ATR للهامش الديناميكي فقط"""
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
    Pivot Points يحدد TP وSL
    ATR للهامش الديناميكي فقط — لا يدخل بحساب TP أو SL أبداً

    LONG:
    - SL = تحت S1 بهامش ATR × 0.3
    - TP = قبل R1 بهامش ATR × 0.3

    SHORT:
    - SL = فوق R1 بهامش ATR × 0.3
    - TP = فوق S1 بهامش ATR × 0.3
    """
    if len(candles) < 2:
        return None, None, None, None

    price = float(candles[-1]["close"])

    # ATR للهامش فقط
    atr = calculate_atr(candles)
    if atr and atr < price * 0.05: # تحقق معقولية ATR
        margin = atr * 0.3
    else:
        margin = price * 0.003 # Fallback 0.3% لو ATR غير معقول

    pivot = calculate_pivot(candles, "daily")

    if pivot:
        r1 = pivot["r1"]
        r2 = pivot["r2"]
        s1 = pivot["s1"]
        s2 = pivot["s2"]

        # ── فلتر المسافة ──
        pivot_range = r1 - s1
        if pivot_range < price * 0.002:
            print(f"⚠️ Pivot Range ضيق ({round(pivot_range,4)}) — تخطي")
            return None, None, None, None

        # ── LONG ──
        # Pivot يحدد المستوى — ATR يحدد الهامش فقط
        sl_long = s1 - margin # تحت S1
        tp_long = r1 - margin # قبل R1

        # لو TP تحت السعر = جرب R2
        if tp_long <= price:
            tp_long = r2 - margin
            print(f"⚠️ R1 تحت السعر — استخدام R2: {round(tp_long,4)}")

        # لو SL فوق السعر = جرب S2
        if sl_long >= price:
            sl_long = s2 - margin
            print(f"⚠️ S1 فوق السعر — استخدام S2: {round(sl_long,4)}")

        # ── SHORT ──
        # Pivot يحدد المستوى — ATR يحدد الهامش فقط
        sl_short = r1 + margin # فوق R1
        tp_short = s1 + margin # فوق S1 (تحت السعر)

        # لو TP فوق السعر = جرب S2
        if tp_short >= price:
            tp_short = s2 + margin
            print(f"⚠️ S1 فوق السعر — استخدام S2: {round(tp_short,4)}")

        # لو SL تحت السعر = جرب R2
        if sl_short <= price:
            sl_short = r2 + margin
            print(f"⚠️ R1 تحت السعر — استخدام R2: {round(sl_short,4)}")

        print(f"📍 Pivot: PP={pivot['pp']} | R1={r1} | S1={s1}")
        print(f"📍 Margin (ATR×0.3): {round(margin,4)}")
        print(f"📍 LONG → SL={round(sl_long,4)} | TP={round(tp_long,4)}")
        print(f"📍 SHORT → SL={round(sl_short,4)} | TP={round(tp_short,4)}")

    else:
        # Fallback لو ما في Pivot
        print("⚠️ Pivot غير متاح — استخدام نسبة ثابتة")
        sl_long = price * 0.990
        sl_short = price * 1.010
        tp_long = price * 1.015
        tp_short = price * 0.985

    return (
        round(sl_long, 4),
        round(sl_short, 4),
        round(tp_long, 4),
        round(tp_short, 4),
    )


def analyze(candles):
    return 0.5

