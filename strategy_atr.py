from strategy_support_resistance import calculate_pivot


def get_levels(candles):
    """
    يحدد SL وTP بناءً على Pivot Points فقط
    بدون ATR — هامش ثابت 0.3% من السعر

    LONG:
    - SL = تحت S1 بهامش 0.3%
    - TP = قبل R1 بهامش 0.3%

    SHORT:
    - SL = فوق R1 بهامش 0.3%
    - TP = فوق S1 بهامش 0.3%
    """
    if len(candles) < 2:
        return None, None, None, None

    price = float(candles[-1]["close"])
    margin = price * 0.003 # 0.3% من السعر

    pivot = calculate_pivot(candles, "daily")

    if pivot:
        r1 = pivot["r1"]
        s1 = pivot["s1"]

        # ── LONG ──
        sl_long = s1 - margin
        tp_long = r1 - margin

        # تحقق: لو TP أصغر من السعر = مشكلة
        if tp_long <= price:
            # جرب R2
            r2 = pivot["r2"]
            tp_long = r2 - margin
            print(f"⚠️ R1 تحت السعر — استخدام R2: {round(tp_long,4)}")

        # تحقق: لو SL أكبر من السعر = مشكلة
        if sl_long >= price:
            s2 = pivot["s2"]
            sl_long = s2 - margin
            print(f"⚠️ S1 فوق السعر — استخدام S2: {round(sl_long,4)}")

        # ── SHORT ──
        sl_short = r1 + margin
        tp_short = s1 + margin

        # تحقق: لو TP أكبر من السعر = مشكلة
        if tp_short >= price:
            s2 = pivot["s2"]
            tp_short = s2 + margin
            print(f"⚠️ S1 فوق السعر — استخدام S2: {round(tp_short,4)}")

        # تحقق: لو SL أصغر من السعر = مشكلة
        if sl_short <= price:
            r2 = pivot["r2"]
            sl_short = r2 + margin
            print(f"⚠️ R1 تحت السعر — استخدام R2: {round(sl_short,4)}")

        print(f"📍 Pivot: PP={pivot['pp']} | R1={r1} | S1={s1}")
        print(f"📍 LONG → SL={round(sl_long,4)} | TP={round(tp_long,4)}")
        print(f"📍 SHORT → SL={round(sl_short,4)} | TP={round(tp_short,4)}")

    else:
        # Fallback بسيط لو ما في Pivot
        print("⚠️ Pivot غير متاح — استخدام نسبة ثابتة")
        sl_long = price * 0.990 # -1%
        sl_short = price * 1.010 # +1%
        tp_long = price * 1.015 # +1.5%
        tp_short = price * 0.985 # -1.5%

    return (
        round(sl_long, 4),
        round(sl_short, 4),
        round(tp_long, 4),
        round(tp_short, 4),
    )


def analyze(candles):
    return 0.5

