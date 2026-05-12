import numpy as np
import pandas as pd

# ══════════════════════════════
# إعدادات
# ══════════════════════════════
SL_PCT = 0.015 # 1.5% Stop Loss
TP_PCT = 0.030 # 3.0% Take Profit
MIN_TRADES = 30 # أقل عدد صفقات مقبول

# ══════════════════════════════
# اختبار استراتيجية واحدة
# ══════════════════════════════
def backtest_strategy(strategy, df):
    from strategy_generator import apply_strategy

    trades = []
    rows = df.to_dict("records")

    for i in range(len(rows) - 1):
        row = rows[i]
        signal = apply_strategy(strategy, row)

        if not signal:
            continue

        entry = rows[i + 1]["close"]
        direction = strategy["direction"]

        if direction == "LONG":
            sl = entry * (1 - SL_PCT)
            tp = entry * (1 + TP_PCT)
        else:
            sl = entry * (1 + SL_PCT)
            tp = entry * (1 - TP_PCT)

        # نبحث عن النتيجة في الشموع التالية
        result = None
        for j in range(i + 2, min(i + 50, len(rows))):
            high = rows[j]["high"]
            low = rows[j]["low"]

            if direction == "LONG":
                if low <= sl:
                    result = -SL_PCT
                    break
                if high >= tp:
                    result = TP_PCT
                    break
            else:
                if high >= sl:
                    result = -SL_PCT
                    break
                if low <= tp:
                    result = TP_PCT
                    break

        if result is not None:
            trades.append(result)

    return calc_stats(trades)

# ══════════════════════════════
# حساب الإحصاء
# ══════════════════════════════
def calc_stats(trades):
    if len(trades) < MIN_TRADES:
        return None

    trades = np.array(trades)
    wins = trades[trades > 0]
    losses = trades[trades < 0]

    win_rate = len(wins) / len(trades)
    total_profit = trades.sum()
    profit_factor = wins.sum() / (abs(losses.sum()) + 1e-10)

    # Drawdown
    cumulative = np.cumsum(trades)
    peak = np.maximum.accumulate(cumulative)
    drawdown = ((peak - cumulative) / (np.abs(peak) + 1e-10)).max()

    # Sharpe
    sharpe = trades.mean() / (trades.std() + 1e-10) * np.sqrt(len(trades))

    return {
        "trades": len(trades),
        "win_rate": round(win_rate, 4),
        "total_profit": round(total_profit, 4),
        "profit_factor": round(profit_factor, 4),
        "drawdown": round(drawdown, 4),
        "sharpe": round(sharpe, 4),
    }

# ══════════════════════════════
# اختبار كل الاستراتيجيات
# ══════════════════════════════
def run_backtest(population, df):
    results = []

    for i, strategy in enumerate(population):
        if i % 100 == 0:
            print(f"⚙️ اختبار {i}/{len(population)}...")

        stats = backtest_strategy(strategy, df)
        if stats:
            results.append({
                "strategy": strategy,
                "stats": stats
            })

    return results

# ══════════════════════════════
# فلترة الأفضل
# ══════════════════════════════
def filter_best(results, top_n=10):
    qualified = [
        r for r in results
        if r["stats"]["win_rate"] > 0.55
        and r["stats"]["drawdown"] < 0.20
        and r["stats"]["profit_factor"] > 1.5
    ]

    qualified.sort(
        key=lambda x: x["stats"]["sharpe"],
        reverse=True
    )

    return qualified[:top_n]

# ══════════════════════════════
# التشغيل
# ══════════════════════════════
if __name__ == "__main__":
    from features import load_data, extract_features
    from strategy_generator import generate_population, print_strategy

    print("📊 تحميل البيانات...")
    df = load_data()
    df = extract_features(df)
    print(f"✅ {len(df)} صف جاهز")

    print("\n🧬 توليد 1000 استراتيجية...")
    population = generate_population(1000)

    print("\n⚙️ بدء الاختبار...")
    results = run_backtest(population, df)
    print(f"✅ نتائج: {len(results)} استراتيجية لها صفقات كافية")

    print("\n🏆 أفضل الاستراتيجيات:")
    best = filter_best(results)

    if best:
        for i, r in enumerate(best):
            print(f"\n{'='*40}")
            print_strategy(r["strategy"], i)
            s = r["stats"]
            print(f" 📊 Win Rate: {s['win_rate']*100:.1f}%")
            print(f" 💰 Total Profit: {s['total_profit']*100:.2f}%")
            print(f" ⚡ Profit Factor: {s['profit_factor']}")
            print(f" 📉 Drawdown: {s['drawdown']*100:.1f}%")
            print(f" 📈 Sharpe: {s['sharpe']:.2f}")
            print(f" 🔢 Trades: {s['trades']}")
    else:
        print("❌ ما في استراتيجية اجتازت المعايير — سنطور في الجيل القادم")
