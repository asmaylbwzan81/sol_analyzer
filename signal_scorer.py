"""
🧠 ADVANCED SIGNAL SCORING ENGINE v3
=========================================================
✅ Full Feature Usage
✅ Confidence 0 -> 100
✅ Short Bias Fix
✅ Momentum Confirmation (relaxed)
✅ Entropy + Volatility Protection
✅ Volume Filter
✅ Dynamic Threshold
✅ Direction Strength Filter
✅ Overtrading Prevention
✅ HTF Conflict Penalty
✅ Trend Boost
✅ Quiet Market Cap
"""

import numpy as np


def safe(x):
    return 0.0 if not np.isfinite(x) else float(x)


def normalize(x, min_val, max_val):
    return float(np.clip((x - min_val) / (max_val - min_val + 1e-9), 0, 1))


def extract_feature_scores(row):
    zscore = safe(row.get("1m_zscore_20", 0))
    momentum = safe(row.get("1m_momentum_10", 0))
    volatility = safe(row.get("1m_volatility_20", 0))
    entropy = safe(row.get("1m_entropy", 1))
    fourier = safe(row.get("1m_fourier", 0))
    autocorr = safe(row.get("1m_autocorr", 0))
    volume = safe(row.get("1m_vol_ratio", 1))
    regime = str(row.get("1m_regime", "ranging")).lower()

    scores = {
        "zscore": normalize(abs(zscore), 0, 3),
        "momentum": normalize(momentum, -0.03, 0.03),
        "volatility": normalize(volatility, 0, 0.05),
        "entropy": 1 - normalize(entropy, 0, 1),
        "fourier": normalize(fourier, 0, 1),
        "autocorr": normalize(autocorr, -1, 1),
        "volume": normalize(volume, 0.5, 3),
    }

    regime_score = 0.5
    if regime == "trending": regime_score = 1.0
    elif regime == "ranging": regime_score = 0.7
    elif regime == "volatile": regime_score = 0.2
    scores["regime"] = regime_score

    return scores


FEATURE_WEIGHTS = {
    "zscore": 0.18,
    "momentum": 0.15,
    "volatility": 0.10,
    "entropy": 0.15,
    "fourier": 0.10,
    "autocorr": 0.10,
    "volume": 0.10,
    "regime": 0.12
}


def calculate_market_score(row):
    scores = extract_feature_scores(row)
    return sum(scores[k] * FEATURE_WEIGHTS.get(k, 0) for k in scores)


def calculate_bias(macro_htf, macro_daily):
    long_bias = 1.0
    short_bias = 1.0

    if macro_htf == "UP":
        long_bias *= 1.15
    elif macro_htf == "DOWN":
        short_bias *= 1.15

    if macro_daily == macro_htf:
        if macro_htf == "UP":
            long_bias *= 1.05
        elif macro_htf == "DOWN":
            short_bias *= 1.05

    return long_bias, short_bias


def determine_direction(row):
    zscore = safe(row.get("1m_zscore_20", 0))
    momentum = safe(row.get("1m_momentum_10", 0))
    volume = safe(row.get("1m_vol_ratio", 1))

    if volume < 0.7:
        return None

    if zscore < -0.5 and momentum > -0.002:
        return "LONG"

    if zscore > 0.5 and momentum < 0.002:
        return "SHORT"

    return None


def compute_confidence(row, macro_htf, macro_daily):
    base_score = calculate_market_score(row)
    long_bias, short_bias = calculate_bias(macro_htf, macro_daily)

    z = safe(row.get("1m_zscore_20", 0))

    if z > 0:
        adjusted_score = base_score * short_bias
    else:
        adjusted_score = base_score * long_bias

    # v3 - تحسين 1: direction strength filter
    zscore_abs = abs(safe(row.get("1m_zscore_20", 0)))
    momentum_abs = abs(safe(row.get("1m_momentum_10", 0)))
    direction_strength = (
        normalize(zscore_abs, 0, 3) * 0.6 +
        normalize(momentum_abs, 0, 0.03) * 0.4
    )
    adjusted_score *= direction_strength

    confidence = float(np.clip(adjusted_score * 100, 0, 100))

    return round(confidence, 1)


def generate_signal(row, macro_htf, macro_daily):
    entropy = safe(row.get("1m_entropy", 1))
    volatility = safe(row.get("1m_volatility_20", 0))
    momentum = safe(row.get("1m_momentum_10", 0))
    price_range = safe(row.get("1m_price_range", 0))
    regime = str(row.get("1m_regime", "ranging")).lower()

    # v2 - تحسين 2: حماية من الفوضى
    if entropy > 0.85:
        return None, 0.0
    if regime == "volatile":
        return None, 0.0

    # v3 - تحسين 2: منع overtrading
    if price_range < 0.0015:
        return None, 0.0

    confidence = compute_confidence(row, macro_htf, macro_daily)

    z = safe(row.get("1m_zscore_20", 0))

    # v3 - تحسين 3: عقوبة عكس HTF
    if z < 0 and macro_htf == "DOWN":
        confidence *= 0.75
    elif z > 0 and macro_htf == "UP":
        confidence *= 0.75

    # v3 - تحسين 4: تعزيز ترند حقيقي
    if regime == "trending" and abs(momentum) > 0.01:
        confidence *= 1.08

    # v3 - تحسين 5: سقف السوق الهادئ
    if volatility < 0.002:
        confidence = min(confidence, 72)

    confidence = round(float(np.clip(confidence, 0, 100)), 1)

    # Dynamic Threshold
    if regime == "trending":
        threshold = 55
    elif regime == "ranging":
        threshold = 65
    else:
        threshold = 75

    if confidence < threshold:
        return None, confidence

    # Direction confirmation
    if z > 0 and momentum < 0.002:
        return "SHORT", confidence
    elif z < 0 and momentum > 0:
        return "LONG", confidence

    return None, confidence


if __name__ == "__main__":
    print("🚀 Advanced Signal Scoring Engine v3 Ready")
    print("✅ Full Feature Usage")
    print("✅ Confidence 0 -> 100")
    print("✅ Direction Strength Filter")
    print("✅ Overtrading Prevention")
    print("✅ HTF Conflict Penalty")
    print("✅ Trend Boost")
    print("✅ Quiet Market Cap")

