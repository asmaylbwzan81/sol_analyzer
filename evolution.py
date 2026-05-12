import random
import numpy as np
from strategy_generator import generate_strategy, generate_population, FEATURES, RANGES, OPERATORS
from backtester import run_backtest

# ══════════════════════════════
# إعدادات
# ══════════════════════════════
POPULATION_SIZE = 300
GENERATIONS = 50
TOP_KEEP = 30
MUTATION_RATE = 0.3

# ══════════════════════════════
# Mutation
# ══════════════════════════════
def mutate(strategy):
    new = {
        "conditions": [c.copy() for c in strategy["conditions"]],
        "direction": strategy["direction"]
    }
    cond = random.choice(new["conditions"])
    change = random.choice(["threshold", "threshold", "operator", "feature"])

    if change == "threshold":
        low, high = RANGES[cond["feature"]]
        current = cond["threshold"]
        delta = (high - low) * 0.1
        cond["threshold"] = round(
            max(low, min(high, current + random.uniform(-delta, delta))), 6
        )

    elif change == "operator":
        cond["operator"] = ">" if cond["operator"] == "<" else "<"

    elif change == "feature":
        new_feature = random.choice(FEATURES)
        low, high = RANGES[new_feature]
        cond["feature"] = new_feature
        cond["operator"] = random.choice(OPERATORS)
        cond["threshold"] = round(random.uniform(low, high), 6)

    return new

# ══════════════════════════════
# Crossover
# ══════════════════════════════
def crossover(s1, s2):
    conds1 = s1["conditions"]
    conds2 = s2["conditions"]
    combined = conds1 + conds2
    random.shuffle(combined)
    num = random.choice([2, 3])
    return {
        "conditions": combined[:num],
        "direction": random.choice([s1["direction"], s2["direction"]])
    }

# ══════════════════════════════
# Score
# ══════════════════════════════
def score_result(r):
    s = r["stats"]
    return (
        s["win_rate"] * 3 +
        s["sharpe"] * 2 +
        s["profit_factor"] -
        s["drawdown"] * 2
    )

# ══════════════════════════════
# التطور
# ══════════════════════════════
def evolve(df, generations=GENERATIONS):
    print(f"🧬 بدء التطور — {generations} جيل")
    print("━" * 40)

    population = generate_population(POPULATION_SIZE)
    best_ever = None
    best_score = -999

    for gen in range(generations):
        print(f"\n🔄 الجيل {gen+1}/{generations}")

        results = run_backtest(population, df)

        if not results:
            print("⚠️ ما في نتائج — نولد جيل جديد")
            population = generate_population(POPULATION_SIZE)
            continue

        results.sort(key=score_result, reverse=True)
        top = results[:TOP_KEEP]

        best_gen = top[0]
        gen_score = score_result(best_gen)
        s = best_gen["stats"]

        print(f" 🏆 Win={s['win_rate']*100:.1f}% | "
              f"Profit={s['total_profit']*100:.1f}% | "
              f"Drawdown={s['drawdown']*100:.1f}% | "
              f"Sharpe={s['sharpe']:.2f} | "
              f"Trades={s['trades']} | "
              f"Score={gen_score:.2f}")

        if gen_score > best_score:
            best_score = gen_score
            best_ever = best_gen
            print(f" ⭐ أفضل حتى الآن!")

        # الجيل التالي
        new_population = [r["strategy"] for r in top]

        # Mutation 50%
        while len(new_population) < int(POPULATION_SIZE * 0.5):
            parent = random.choice(top)["strategy"]
            new_population.append(mutate(parent))

        # Crossover 30%
        while len(new_population) < int(POPULATION_SIZE * 0.8):
            p1 = random.choice(top)["strategy"]
            p2 = random.choice(top)["strategy"]
            new_population.append(crossover(p1, p2))

        # عشوائي جديد 20%
        while len(new_population) < POPULATION_SIZE:
            new_population.append(generate_strategy())

        population = new_population

    return best_ever
