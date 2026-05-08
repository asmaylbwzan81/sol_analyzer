from strategy_weights import weighted_score, get_all_weights, init_db

init_db()

# ── تصنيف ابتدائي حسب Win Rate ──────────────
STRONG_BASE = {"rsi", "bollinger", "stochastic", "fibonacci", "support_resistance"}
MEDIUM_BASE = {"adx", "supertrend"}
WEAK_BASE = {"momentum", "macd", "ema"}

# ── مضاعف الوزن حسب الطبقة ──────────────────
TIER_MULTIPLIER = {
    "strong": 1.5, # القوي صوته أثقل
    "medium": 1.0, # المتوسط طبيعي
    "weak": 0.4, # الضعيف صوته خفيف
}

def _get_tier(name: str, weight: float) -> str:
    """الطبقة تتغير حسب الوزن الحالي — عقاب وترقية ديناميكي"""
    if name in STRONG_BASE:
        if weight >= 0.9: return "strong"
        elif weight >= 0.6: return "medium"
        else: return "weak"
    elif name in MEDIUM_BASE:
        if weight >= 1.2: return "strong"
        elif weight >= 0.6: return "medium"
        else: return "weak"
    else: # WEAK_BASE
        if weight >= 1.5: return "strong"
        elif weight >= 1.0: return "medium"
        else: return "weak"

def vote(scores: dict) -> float:
    """
    Weighted score مع مضاعف الطبقة:
    القوي وزنه × 1.5 | المتوسط × 1.0 | الضعيف × 0.4
    """
    if not scores:
        return 0.5

    weights = get_all_weights()
    total_weighted = 0.0
    total_weight = 0.0

    for name, signal in scores.items():
        base_w = weights.get(name.lower(), 1.0)
        tier = _get_tier(name.lower(), base_w)
        final_w = base_w * TIER_MULTIPLIER[tier]

        total_weighted += signal * final_w
        total_weight += final_w

    if total_weight == 0:
        return 0.5
    return round(total_weighted / total_weight, 4)

def decision(score: float, scores: dict = None):
    if scores:
        weights = get_all_weights()

        # ── عدّ الموافقين من كل طبقة ──
        strong_agree = sum(
            1 for k, v in scores.items()
            if _get_tier(k, weights.get(k, 1.0)) == "strong"
            and (v >= 0.65 or v <= 0.35)
        )
        medium_agree = sum(
            1 for k, v in scores.items()
            if _get_tier(k, weights.get(k, 1.0)) == "medium"
            and (v >= 0.65 or v <= 0.35)
        )

        # ── شرط الدخول: 2 قوي + 2 متوسط ──
        if strong_agree < 2 or medium_agree < 2:
            return "SKIP", "NEUTRAL"

        # ── تحديد الاتجاه ──
        bullish = len([v for v in scores.values() if v >= 0.65])
        bearish = len([v for v in scores.values() if v <= 0.35])
        total = len(scores)

        if score >= 0.60 and bullish > total * 0.5:
            return "ENTER", "LONG"
        elif score <= 0.40 and bearish > total * 0.5:
            return "ENTER", "SHORT"
        return "SKIP", "NEUTRAL"

    # ── fallback بدون scores ──
    if score >= 0.60:
        return "ENTER", "LONG"
    elif score <= 0.40:
        return "ENTER", "SHORT"
    return "SKIP", "NEUTRAL"
