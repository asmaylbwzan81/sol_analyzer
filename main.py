import time
from datetime import datetime
from data_engine import init_db, fetch_candles, save_candles, count_candles
from features import load_data, extract_features
from strategy_generator import generate_population, print_strategy
from backtester import run_backtest, filter_best

TARGET = 20000

def main():
    print("🚀 Quant Bot Started")
    print("━" * 40)

    # 1️⃣ البيانات
    print("📊 فحص قاعدة البيانات...")
    init_db()
    existing = count_candles()
    if existing < TARGET:
        print(f"📥 جاري جلب البيانات... (موجود: {existing})")
        candles = fetch_candles()
        save_candles(candles)
        print(f"✅ تم الحفظ: {count_candles()} شمعة")
    else:
        print(f"✅ البيانات جاهزة: {existing} شمعة")

    # 2️⃣ Features
    print("\n📐 حساب الـ Features...")
    df = load_data()
    df = extract_features(df)
    print(f"✅ {len(df)} صف جاهز")

    # 3️⃣ توليد الاستراتيجيات
    print("\n🧬 توليد 1000 استراتيجية...")
    population = generate_population(1000)

    # 4️⃣ الاختبار
    print("\n⚙️ بدء الاختبار...")
    results = run_backtest(population, df)
    print(f"✅ {len(results)} استراتيجية لها صفقات كافية")

    # 5️⃣ الأفضل
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
        print("❌ ما في استراتيجية اجتازت المعايير")

    print("\n━" * 40)
    print("✅ النظام جاهز!")

if __name__ == "__main__":
    main()
