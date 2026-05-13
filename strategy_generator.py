import random
import numpy as np
from features import ALL_FEATURES, BASE_FEATURES

# ══════════════════════════════
# الـ Features المتاحة (78 feature من 3 فريمات)
# ══════════════════════════════
FEATURES = ALL_FEATURES

OPERATORS = [">", "<"]

# ══════════════════════════════
# نطاقات القيم لكل feature
# ══════════════════════════════
BASE_RANGES = {
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
    "fourier_strength": (1.0, 10.0),
    "entropy": (0.5, 3.0),
    "volatility": (0.0001, 0.01),
    "vol_ratio": (0.5, 3.0),
    "volume_change": (-0.5, 2.0),
    "volume_zscore": (-3.0, 3.0),
    "price_range": (0.001, 0.05),
    "close_position": (0.0, 1.0),
}

# نبني RANGES للـ 3 فريمات
RANGES = {}
for prefix in ["1m_", "5m_", "15m_"]:
    for feature, range_val in BASE_RANGES.items():
        RANGES[f"{prefix}{feature}"] = range_val


# ══════════════════════════════
# توليد استراتيجية واحدة
# ══════════════════════════════
def generate_strategy():
    """
    يولد استراتيجية بـ 3 شروط:
    - شرط من 1m (دخول دقيق)
    - شرط من 5m (تأكيد)
    - شرط من 15m (اتجاه عام)
    """
    conditions = []

    # شرط من كل فريم
    for prefix in ["1m_", "5m_", "15m_"]:
        prefix_features = [f for f in FEATURES if f.startswith(prefix)]
        feature = random.choice(prefix_features)
        operator = random.choice(OPERATORS)
        low, high = RANGES[feature]
        threshold = round(random.uniform(low, high), 6)
        conditions.append({
            "feature": feature,
            "operator": operator,
            "threshold": threshold
        })

    # شرط إضافي عشوائي من أي فريم
    extra_feature = random.choice(FEATURES)
    low, high = RANGES[extra_feature]
    conditions.append({
        "feature": extra_feature,
        "operator": random.choice(OPERATORS),
        "threshold": round(random.uniform(low, high), 6)
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
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return False
        if cond["operator"] == ">" and not (val > cond["threshold"]):
            return False
        if cond["operator"] == "<" and not (val < cond["threshold"]):
            return False
    return True


# ══════════════════════════════
# توليد N استراتيجية
# ══════════════════════════════
def generate_population(n=300):
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
    print("🧬 توليد 300 استراتيجية...")
    population = generate_population(300)

    print("\n📋 أمثلة (أول 3):")
    for i, s in enumerate(population[:3]):
        print_strategy(s, i)

    print(f"\n✅ تم توليد {len(population)} استراتيجية")
    print(f"📊 عدد الـ Features المتاحة: {len(FEATURES)}")
    print(f" 1m: {len([f for f in FEATURES if f.startswith('1m_')])} feature")
    print(f" 5m: {len([f for f in FEATURES if f.startswith('5m_')])} feature")
    print(f" 15m: {len([f for f in FEATURES if f.startswith('15m_')])} feature")

