import random
import numpy as np

# ══════════════════════════════
# الـ Features المتاحة
# ══════════════════════════════
FEATURES = [
    "returns", "zscore", "zscore_50",
    "std_20", "std_50", "mean_reversion",
    "skewness", "kurtosis",
    "momentum_5", "momentum_10", "momentum_20",
    "momentum_pct", "acceleration",
    "hist_prob_up", "hist_prob_big", "percentile_rank",
    "autocorr_1", "autocorr_5",
    "fourier_strength", "entropy",
    "volatility", "vol_ratio",
    "volume_change", "volume_zscore",
    "price_range", "close_position"
]

OPERATORS = [">", "<"]

RANGES = {
    "returns": (-0.05, 0.05),
    "zscore": (-3.0, 3.0),
    "zscore_50": (-3.0, 3.0),
    "std_20": (0.0001, 0.01),
    "std_50": (0.0001, 0.01),
    "mean_reversion": (-3.0, 3.0),
    "skewness": (-2.0, 2.0),
    "kurtosis": (-1.0, 5.0),
    "momentum_5": (-500, 500),
    "momentum_10": (-1000, 1000),
    "momentum_20": (-2000, 2000),
    "momentum_pct": (-0.05, 0.05),
    "acceleration": (-500, 500),
    "hist_prob_up": (0.3, 0.7),
    "hist_prob_big": (0.1, 0.9),
    "percentile_rank": (0.0, 1.0),
    "autocorr_1": (-1.0, 1.0),
    "autocorr_5": (-1.0, 1.0),
    "fourier_strength":(1.0, 10.0),
    "entropy": (0.5, 3.0),
    "volatility": (0.0001, 0.01),
    "vol_ratio": (0.5, 3.0),
    "volume_change": (-0.5, 2.0),
    "volume_zscore": (-3.0, 3.0),
    "price_range": (0.001, 0.05),
    "close_position": (0.0, 1.0),
}

# ══════════════════════════════
# توليد استراتيجية واحدة
# ══════════════════════════════
def generate_strategy():
    num_conditions = random.choice([2, 3])
    features_used = random.sample(FEATURES, num_conditions)
    conditions = []

    for feature in features_used:
        operator = random.choice(OPERATORS)
        low, high = RANGES[feature]
        threshold = round(random.uniform(low, high), 6)
        conditions.append({
            "feature": feature,
            "operator": operator,
            "threshold": threshold
        })

    return {
        "conditions": conditions,
        "direction": random.choice(["LONG", "SHORT"])
    }

# ══════════════════════════════
# تطبيق الاستراتيجية على صف
# ══════════════════════════════
def apply_strategy(strategy, row):
    for cond in strategy["conditions"]:
        val = row.get(cond["feature"])
        if val is None or np.isnan(val):
            return False
        if cond["operator"] == ">" and not (val > cond["threshold"]):
            return False
        if cond["operator"] == "<" and not (val < cond["threshold"]):
            return False
    return True

# ══════════════════════════════
# توليد N استراتيجية
# ══════════════════════════════
def generate_population(n=1000):
    return [generate_strategy() for _ in range(n)]

# ══════════════════════════════
# طباعة استراتيجية
# ══════════════════════════════
def print_strategy(strategy, index=0):
    print(f"\n📋 استراتيجية {index+1} — {strategy['direction']}")
    for cond in strategy["conditions"]:
        print(f" {cond['feature']} {cond['operator']} {cond['threshold']}")

# ══════════════════════════════
# التشغيل
# ══════════════════════════════
if __name__ == "__main__":
    print("🧬 توليد 1000 استراتيجية...")
    population = generate_population(1000)
    for i, s in enumerate(population[:5]):
        print_strategy(s, i)
    print(f"\n✅ تم توليد {len(population)} استراتيجية جاهزة للاختبار")
