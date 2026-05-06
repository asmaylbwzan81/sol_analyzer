def analyze(candles):
    if len(candles) < 3:
        return 0.5

    c1 = candles[-3]
    c2 = candles[-2]
    c3 = candles[-1]

    o1, c1v = float(c1["open"]), float(c1["close"])
    o2, c2v = float(c2["open"]), float(c2["close"])
    o3, c3v = float(c3["open"]), float(c3["close"])

    body1 = abs(c1v - o1)
    body2 = abs(c2v - o2)

    # ── أنماط صعود قوية جداً ──
    # Three White Soldiers
    if c1v > o1 and c2v > o2 and c3v > o3 and c2v > c1v and c3v > c2v:
        return 0.95

    # ── أنماط صعود قوية ──
    # Bullish Engulfing
    if c2v < o2 and c3v > o3 and c3v > o2 and o3 < c2v:
        return 0.85

    # Morning Star
    if c1v < o1 and body2 < body1 * 0.3 and c3v > o3:
        return 0.80

    # ── أنماط صعود متوسطة ──
    # Hammer (شمعة مطرقة)
    lower_shadow3 = float(c3["low"])
    upper_shadow3 = float(c3["high"])
    if (c3v > o3 and
        (min(c3v, o3) - lower_shadow3) > body2 * 2 and
        (upper_shadow3 - max(c3v, o3)) < body2 * 0.3):
        return 0.70

    # ── أنماط نزول متوسطة ──
    # Shooting Star
    if (c3v < o3 and
        (upper_shadow3 - max(c3v, o3)) > body2 * 2 and
        (min(c3v, o3) - lower_shadow3) < body2 * 0.3):
        return 0.30

    # ── أنماط نزول قوية ──
    # Evening Star
    if c1v > o1 and body2 < body1 * 0.3 and c3v < o3:
        return 0.20

    # Bearish Engulfing
    if c2v > o2 and c3v < o3 and c3v < o2 and o3 > c2v:
        return 0.15

    # ── أنماط نزول قوية جداً ──
    # Three Black Crows
    if c1v < o1 and c2v < o2 and c3v < o3 and c2v < c1v and c3v < c2v:
        return 0.05

    return 0.5 # لا يوجد نمط واضح

