from strategy_weights import weighted_score, get_all_weights, init_db

init_db()

# ── تصنيف ابتدائي حسب Win Rate ──────────────
STRONG_BASE = {"rsi", "bollinger", "stochastic", "fibonacci", "support_resistance"}
MEDIUM_BASE = {"adx", "supertrend"}
WEAK_BASE = {"momentum", "macd", "ema"}

# ── مضاعف الوزن حسب الطبقة ──────────────────
TIER_MULTIPLIER = {
    "strong": 1.5,
    "medium": 1.0,
    "weak": 0.4,
}

def _get_tier(name: str, weight: float) -> str:
    if name in STRONG_BASE:
        if weight >= 0.9: return "strong"
        elif weight >= 0.6: return "medium"
        else: return "weak"
    elif name in MEDIUM_BASE:
        if weight >= 1.2: return "strong"
        elif weight >= 0.6: return "medium"
        else: return "weak"
    else:
        if weight >= 1.5: return "strong"
        elif weight >= 1.0: return "medium"
        else: return "weak"

def vote(scores: dict) -> float:
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

        # ── شرط الدخول: 2 قوي + 2 متوسط فقط ──
        if strong_agree < 2 or medium_agree < 2:
            return "SKIP", "NEUTRAL"

        if score >= 0.60:
            return "ENTER", "LONG"
        elif score <= 0.40:
            return "ENTER", "SHORT"
        return "SKIP", "NEUTRAL"

    if score >= 0.60:
        return "ENTER", "LONG"
    elif score <= 0.40:
        return "ENTER", "SHORT"
    return "SKIP", "NEUTRAL"
