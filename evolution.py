import random
import numpy as np
from strategy_generator import generate_strategy, generate_population, FEATURES, RANGES, OPERATORS
from backtester import run_backtest, TOTAL_FEE
from redis_store import save_best, load_best

# ══════════════════════════════
# إعدادات
# ══════════════════════════════
POPULATION_SIZE = 300
GENERATIONS = 50
TOP_KEEP = 30
TARGET_TRADES = 200 # هدف عدد الصفقات اليومي

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
        # نحافظ على نفس الفريم
        prefix = cond["feature"].split("_")[0] + "_"
        same_prefix = [f for f in FEATURES if f.startswith(prefix)]
        new_feature = random.choice(same_prefix)
        low, high = RANGES[new_feature]
        cond["feature"] = new_feature
        cond["operator"] = random.choice(OPERATORS)
        cond["threshold"] = round(random.uniform(low, high), 6)

    return new


# ══════════════════════════════
# Crossover
# ══════════════════════════════
def crossover(s1, s2):
    # نحافظ على توزيع الفريمات
    conditions = []
    for prefix in ["1m_", "5m_", "15m_"]:
        c1 = [c for c in s1["conditions"] if c["feature"].startswith(prefix)]
        c2 = [c for c in s2["conditions"] if c["feature"].startswith(prefix)]
        pool = c1 + c2
        if pool:
            conditions.append(random.choice(pool))

    # شرط إضافي عشوائي
    extra_pool = s1["conditions"] + s2["conditions"]
    conditions.append(random.choice(extra_pool))

    return {
        "conditions": conditions,
        "direction": random.choice([s1["direction"], s2["direction"]])
    }


# ══════════════════════════════
# Score - يكافئ كثرة الصفقات والربح الحقيقي
# ══════════════════════════════
def score_result(r):
    s = r["stats"]

    # مكافأة كثرة الصفقات (هدف 200 صفقة)
    trade_bonus = min(s["trades"] / TARGET_TRADES, 1.0)

    # التأكد إن متوسط الربح يغطي الفي
    fee_penalty = 1.0 if s["avg_profit"] > TOTAL_FEE else 0.3

    return (
        s["win_rate"] * 3 +
        s["sharpe"] * 2 +
        s["profit_factor"] * 1 -
        s["drawdown"] * 2
    ) * trade_bonus * fee_penalty


def calc_score(stats):
    trade_bonus = min(stats.get("trades", 0) / TARGET_TRADES, 1.0)
    fee_penalty = 1.0 if stats.get("avg_profit", 0) > TOTAL_FEE else 0.3
    return (
        stats.get("win_rate", 0) * 3 +
        stats.get("sharpe", 0) * 2 -
        stats.get("drawdown", 1) * 2
    ) * trade_bonus * fee_penalty


# ══════════════════════════════
# التطور
# ══════════════════════════════
def evolve(df, generations=GENERATIONS):
    print(f"🧬 بدء التطور — {generations} جيل")
    print("━" * 40)

    saved = load_best()
    if saved:
        saved_score = calc_score(saved["stats"])
        print(f"📂 تحميل من Redis — Score={saved_score:.2f}")
        population = [saved["strategy"]]
        while len(population) < POPULATION_SIZE:
            population.append(generate_strategy())
    else:
        saved_score = -999
        print("🎲 بدء عشوائي...")
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
              f"AvgProfit={s['avg_profit']*100:.3f}% | "
              f"Score={gen_score:.2f}")

        if gen_score > best_score:
            best_score = gen_score
            best_ever = best_gen
            print(f" ⭐ أفضل حتى الآن!")

            if gen_score > saved_score:
                save_best(best_ever["strategy"], best_ever["stats"])
                saved_score = gen_score
                print(f" 💾 أفضل من المحفوظ — تم التحديث ✅")
            else:
                print(f" ℹ️ المحفوظ في Redis أفضل — لا تغيير")

        # ══════════════════════════════
        # الجيل التالي
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

        # 20% عشوائي جديد
        while len(new_population) < POPULATION_SIZE:
            new_population.append(generate_strategy())

        population = new_population

    return best_ever

