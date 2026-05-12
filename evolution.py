import random
import numpy as np
from strategy_generator import generate_strategy, generate_population, FEATURES, RANGES, OPERATORS
from backtester import run_backtest, filter_best

# ══════════════════════════════
# إعدادات
# ══════════════════════════════
POPULATION_SIZE = 200
GENERATIONS = 20
TOP_KEEP = 20
MUTATION_RATE = 0.3

# ══════════════════════════════
# Mutation — يعدل شرط عشوائي
# ══════════════════════════════
def mutate(strategy):
    new = {
        "conditions": [c.copy() for c in strategy["conditions"]],
        "direction": strategy["direction"]
    }
    # اختار شرط عشوائي وعدّله
    cond = random.choice(new["conditions"])
    change = random.choice(["threshold", "operator", "feature"])

    if change == "threshold":
        low, high = RANGES[cond["feature"]]
        cond["threshold"] = round(random.uniform(low, high), 6)

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
# Crossover — يدمج استراتيجيتين
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
# تقييم بسيط بدون فلترة صارمة
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
# دورة التطور الكاملة
# ══════════════════════════════
def evolve(df, generations=GENERATIONS):
    print(f"🧬 بدء التطور — {generations} جيل")
    print("━" * 40)

    # الجيل الأول عشوائي
    population = generate_population(POPULATION_SIZE)
    best_ever = None
    best_score = -999

    for gen in range(generations):
        print(f"\n🔄 الجيل {gen + 1}/{generations}")

        # اختبار
        results = run_backtest(population, df)

        if not results:
            print("⚠️ ما في نتائج — نولد جيل جديد")
            population = generate_population(POPULATION_SIZE)
            continue

        # ترتيب حسب Score
        results.sort(key=score_result, reverse=True)
        top = results[:TOP_KEEP]

        # أفضل نتيجة
        best_gen = top[0]
        gen_score = score_result(best_gen)
        s = best_gen["stats"]

        print(f" 🏆 أفضل الجيل: Win={s['win_rate']*100:.1f}% | "
              f"Profit={s['total_profit']*100:.1f}% | "
              f"Sharpe={s['sharpe']:.2f} | "
              f"Score={gen_score:.2f}")

        if gen_score > best_score:
            best_score = gen_score
            best_ever = best_gen
            print(f" ⭐ جيل أفضل!")

        # توليد الجيل التالي
        new_population = [r["strategy"] for r in top]

        # Mutation
        while len(new_population) < POPULATION_SIZE * 0.6:
            parent = random.choice(top)["strategy"]
            new_population.append(mutate(parent))

        # Crossover
        while len(new_population) < POPULATION_SIZE:
            p1 = random.choice(top)["strategy"]
            p2 = random.choice(top)["strategy"]
            new_population.append(crossover(p1, p2))

        population = new_population

    return best_ever

# ══════════════════════════════
# التشغيل
# ══════════════════════════════
if __name__ == "__main__":
    from features import load_data, extract_features
    from strategy_generator import print_strategy

    print("📊 تحميل البيانات...")
    df = load_data()
    df = extract_features(df)
    print(f"✅ {len(df)} صف جاهز")

    best = evolve(df)

    if best:
        print("\n" + "═" * 40)
        print("🏆 أفضل استراتيجية وجدها التطور:")
        print_strategy(best["strategy"], 0)
        s = best["stats"]
        print(f" 📊 Win Rate: {s['win_rate']*100:.1f}%")
        print(f" 💰 Total Profit: {s['total_profit']*100:.2f}%")
        print(f" ⚡ Profit Factor: {s['profit_factor']}")
        print(f" 📉 Drawdown: {s['drawdown']*100:.1f}%")
        print(f" 📈 Sharpe: {s['sharpe']:.2f}")
        print(f" 🔢 Trades: {s['trades']}")
