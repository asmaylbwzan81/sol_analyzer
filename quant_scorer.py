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


def compute_confidence(row, macro_htf, macro_daily):
    base_score = calculate_market_score(row) # 0.0 → 1.0
    long_bias, short_bias = calculate_bias(macro_htf, macro_daily)

    z = safe(row.get("1m_zscore_20", 0))

    if z > 0:
        adjusted_score = base_score * short_bias
    else:
        adjusted_score = base_score * long_bias

    # ✅ إصلاح: بدل direction_strength نستخدم boost بسيط
    zscore_abs = abs(safe(row.get("1m_zscore_20", 0)))
    momentum_abs = abs(safe(row.get("1m_momentum_10", 0)))
    direction_boost = 1.0 + (
        normalize(zscore_abs, 0, 3) * 0.3 +
        normalize(momentum_abs, 0, 0.03) * 0.2
    )
    adjusted_score *= direction_boost

    confidence = float(np.clip(adjusted_score * 100, 0, 100))
    return round(confidence, 1)


if __name__ == "__main__":
    print("🚀 Signal Scorer Ready")

