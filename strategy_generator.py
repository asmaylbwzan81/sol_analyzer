import random
import numpy as np
from features import ALL_FEATURES, BASE_FEATURES

# ══════════════════════════════
# Features
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

RANGES = {}
for prefix in ["1m_", "5m_", "15m_"]:
    for feature, range_val in BASE_RANGES.items():
        RANGES[f"{prefix}{feature}"] = range_val

STRATEGY_TYPES = [
    "mean_reversion",
    "momentum",
    "breakout",
    "volatility_burst",
    "momentum_exhaustion",
]

def generate_condition(prefix=None):
    if prefix:
        available = [f for f in FEATURES if f.startswith(prefix)]
    else:
        available = FEATURES
    feature = random.choice(available)
    operator = random.choice(OPERATORS)
    low, high = RANGES.get(feature, (0, 1))
    threshold = round(random.uniform(low, high), 6)
    return {"feature": feature, "operator": operator, "threshold": threshold}

def generate_typed_strategy(strategy_type):
    conditions = []

    if strategy_type == "mean_reversion":
        z = round(random.uniform(-2.5, 2.5), 6)
        conditions.append({"feature": "1m_zscore", "operator": ">" if z > 0 else "<", "threshold": abs(z)})
        conditions.append({"feature": "1m_mean_reversion", "operator": "<", "threshold": round(random.uniform(-1.0, 0.0), 6)})
        conditions.append(generate_condition("5m_"))
        direction = "SHORT" if z > 0 else "LONG"

    elif strategy_type == "momentum":
        op = random.choice([">", "<"])
        conditions.append({"feature": "1m_momentum_pct", "operator": op, "threshold": round(random.uniform(0.001, 0.003), 6)})
        conditions.append({"feature": "5m_momentum_pct", "operator": op, "threshold": round(random.uniform(0.001, 0.005), 6)})
        conditions.append(generate_condition("15m_"))
        direction = "LONG" if op == ">" else "SHORT"

    elif strategy_type == "breakout":
        op = random.choice([">", "<"])
        conditions.append({"feature": "1m_percentile_rank", "operator": op, "threshold": round(random.uniform(0.7, 0.95), 6)})
        conditions.append({"feature": "1m_volume_zscore", "operator": ">", "threshold": round(random.uniform(0.5, 2.0), 6)})
        conditions.append(generate_condition("5m_"))
        direction = "LONG" if op == ">" else "SHORT"

    elif strategy_type == "volatility_burst":
        conditions.append({"feature": "1m_vol_ratio", "operator": ">", "threshold": round(random.uniform(1.5, 2.5), 6)})
        conditions.append({"feature": "1m_entropy", "operator": ">", "threshold": round(random.uniform(1.5, 2.5), 6)})
        conditions.append(generate_condition("1m_"))
        direction = random.choice(["LONG", "SHORT"])

    elif strategy_type == "momentum_exhaustion":
        conditions.append({"feature": "1m_acceleration", "operator": "<", "threshold": round(random.uniform(-200, 0), 6)})
        conditions.append({"feature": "1m_momentum_pct", "operator": ">", "threshold": round(random.uniform(0.01, 0.03), 6)})
        conditions.append(generate_condition("5m_"))
        direction = "SHORT"

    else:
        return generate_random_strategy()

    conditions.append(generate_condition())

    return {
        "conditions": conditions,
        "direction": direction,
        "type": strategy_type,
        "profile": {
            "edge_type": strategy_type,
            "regime_preference": get_regime_preference(strategy_type),
            "volatility_sensitivity": get_vol_sensitivity(strategy_type),
        }
    }

def get_regime_preference(strategy_type):
    return {
        "mean_reversion": "ranging",
        "momentum": "trending",
        "breakout": "low_volatility",
        "volatility_burst": "high_volatility",
        "momentum_exhaustion": "trending",
    }.get(strategy_type, "any")

def get_vol_sensitivity(strategy_type):
    return {
        "mean_reversion": "low",
        "momentum": "medium",
        "breakout": "medium",
        "volatility_burst": "high",
        "momentum_exhaustion": "low",
    }.get(strategy_type, "medium")

def generate_random_strategy():
    conditions = []
    for prefix in ["1m_", "5m_", "15m_"]:
        conditions.append(generate_condition(prefix))
    conditions.append(generate_condition())
    return {
        "conditions": conditions,
        "direction": random.choice(["LONG", "SHORT"]),
        "type": "random",
        "profile": {
            "edge_type": "random",
            "regime_preference": "any",
            "volatility_sensitivity": "medium",
        }
    }

def generate_strategy():
    if random.random() < 0.60:
        return generate_typed_strategy(random.choice(STRATEGY_TYPES))
    return generate_random_strategy()

def apply_strategy(strategy, row):
    for cond in strategy["conditions"]:
        val = row.get(cond["feature"])
        if val is None or (isinstance(val, float) and np.isnan(val)):
            continue
        if cond["operator"] == ">" and not (val > cond["threshold"]):
            return False
        if cond["operator"] == "<" and not (val < cond["threshold"]):
            return False
    return True

def strategy_confidence(strategy, row):
    scores = []
    for cond in strategy["conditions"]:
        val = row.get(cond["feature"])
        if val is None or (isinstance(val, float) and np.isnan(val)):
            scores.append(0.0)
            continue
        low, high = RANGES.get(cond["feature"], (0, 1))
        rng = high - low + 1e-10
        if cond["operator"] == ">" and val > cond["threshold"]:
            scores.append(min(1.0, (val - cond["threshold"]) / rng))
        elif cond["operator"] == "<" and val < cond["threshold"]:
            scores.append(min(1.0, (cond["threshold"] - val) / rng))
        else:
            scores.append(0.0)
    confidence = float(np.mean(scores)) if scores else 0.0
    passed = sum(1 for s in scores if s > 0)
    return confidence, passed == len(strategy["conditions"])

def generate_population(n=300):
    population = []
    per_type = n // (len(STRATEGY_TYPES) + 1)
    for strategy_type in STRATEGY_TYPES:
        for _ in range(per_type):
            population.append(generate_typed_strategy(strategy_type))
    while len(population) < n:
        population.append(generate_random_strategy())
    random.shuffle(population)
    return population

def print_strategy(strategy, index=0):
    stype = strategy.get("type", "unknown")
    direction = strategy["direction"]
    print(f"\n📋 استراتيجية {index+1} — {direction} [{stype}]")
    for cond in strategy["conditions"]:
        print(f" {cond['feature']} {cond['operator']} {cond['threshold']}")
    if "profile" in strategy:
        p = strategy["profile"]
        print(f" 🎯 Regime: {p['regime_preference']} | Vol: {p['volatility_sensitivity']}")
