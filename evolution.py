import random
import numpy as np
from strategy_generator import (
    generate_strategy,
    generate_population,
    FEATURES,
    RANGES,
    OPERATORS
)
from backtester import run_backtest, TOTAL_FEE
from redis_store import save_best, load_best

# ══════════════════════════════
# Config
# ══════════════════════════════
POPULATION_SIZE = 300
GENERATIONS = 50
TOP_KEEP = 30
TARGET_TRADES = 200


# ══════════════════════════════
# Mutation (FIXED)
# ══════════════════════════════
def mutate(strategy):
    new = {
        "conditions": [c.copy() for c in strategy["conditions"]],
        "direction": strategy["direction"],
        "type": strategy.get("type", "mutated")
    }

    cond = random.choice(new["conditions"])
    change = random.choice(["threshold", "operator", "feature"])

    if change == "threshold":
        low, high = RANGES.get(cond["feature"], (0, 1))
        current = cond["threshold"]
        delta = (high - low) * 0.1

        cond["threshold"] = round(
            max(low, min(high, current + random.uniform(-delta, delta))),
            6
        )

    elif change == "operator":
        cond["operator"] = ">" if cond["operator"] == "<" else "<"

    elif change == "feature":
        prefix = cond["feature"].split("_")[0] + "_"
        same_prefix = [f for f in FEATURES if f.startswith(prefix)]

        if same_prefix:
            new_feature = random.choice(same_prefix)
            low, high = RANGES.get(new_feature, (0, 1))

            cond["feature"] = new_feature
            cond["operator"] = random.choice(OPERATORS)
            cond["threshold"] = round(random.uniform(low, high), 6)

    return new


# ══════════════════════════════
# Crossover (FIXED + safer)
# ══════════════════════════════
def crossover(s1, s2):
    conditions = []

    for prefix in ["1m_", "5m_", "15m_"]:
        pool = [
            c for c in (s1["conditions"] + s2["conditions"])
            if c["feature"].startswith(prefix)
        ]

        if pool:
            conditions.append(random.choice(pool).copy())

    # fallback if empty
    if not conditions:
        conditions = [
            random.choice(s1["conditions"]).copy(),
            random.choice(s2["conditions"]).copy()
        ]

    return {
        "conditions": conditions,
        "direction": random.choice([s1["direction"], s2["direction"]]),
        "type": "crossover"
    }


# ══════════════════════════════
# Score (cleaned + more stable)
# ══════════════════════════════
def calc_score(stats):
    trade_bonus = min(stats.get("trades", 0) / TARGET_TRADES, 1.0)

    fee_penalty = 1.0 if stats.get("avg_profit", 0) > TOTAL_FEE else 0.3

    return (
        stats.get("win_rate", 0) * 3 +
        stats.get("sharpe", 0) * 2 +
        stats.get("profit_factor", 0) * 1 -
        stats.get("drawdown", 0) * 2
    ) * trade_bonus * fee_penalty


# ══════════════════════════════
# Evolution Loop (FIXED stability)
# ══════════════════════════════
def evolve(df, generations=GENERATIONS):
    print(f"🧬 Starting evolution — {generations} generations")
    print("━" * 40)

    saved = load_best()

    if saved:
        saved_score = calc_score(saved["stats"])
        print(f"📂 Loaded best from Redis — Score={saved_score:.2f}")

        population = [saved["strategy"]]
        population += [generate_strategy() for _ in range(POPULATION_SIZE - 1)]
    else:
        saved_score = -999
        print("🎲 Starting random population...")
        population = generate_population(POPULATION_SIZE)

    best_ever = None
    best_score = -999

    for gen in range(generations):
        print(f"\n🔄 Generation {gen+1}/{generations}")

        results = run_backtest(population, df)

        if not results:
            print("⚠️ No results — regenerating population")
            population = generate_population(POPULATION_SIZE)
            continue

        results.sort(key=lambda x: calc_score(x["stats"]), reverse=True)
        top = results[:TOP_KEEP]

        best_gen = top[0]
        gen_score = calc_score(best_gen["stats"])
        s = best_gen["stats"]

        print(
            f" 🏆 Win={s['win_rate']*100:.1f}% | "
            f"Profit={s['total_profit']*100:.1f}% | "
            f"DD={s['drawdown']*100:.1f}% | "
            f"Sharpe={s['sharpe']:.2f} | "
            f"Trades={s['trades']} | "
            f"Avg={s['avg_profit']*100:.3f}% | "
            f"Score={gen_score:.2f}"
        )

        if gen_score > best_score:
            best_score = gen_score
            best_ever = best_gen
            print(" ⭐ New best overall!")

            if gen_score > saved_score:
                save_best(best_ever["strategy"], best_ever["stats"])
                saved_score = gen_score
                print(" 💾 Saved to Redis")
            else:
                print(" ℹ️ Redis best still stronger")

        # ══════════════════════════════
        # Next generation (FIXED ratios)
        # ══════════════════════════════
        new_population = [r["strategy"] for r in top]

        # 50% mutation
        while len(new_population) < int(POPULATION_SIZE * 0.5):
            parent = random.choice(top)["strategy"]
            new_population.append(mutate(parent))

        # 30% crossover
        while len(new_population) < int(POPULATION_SIZE * 0.8):
            p1 = random.choice(top)["strategy"]
            p2 = random.choice(top)["strategy"]
            new_population.append(crossover(p1, p2))

        # 20% fresh random
        while len(new_population) < POPULATION_SIZE:
            new_population.append(generate_strategy())

        population = new_population

    return best_ever
