import time
from datetime import datetime
from data_engine import init_db, fetch_candles, save_candles, count_candles
from features import load_data, extract_features
from evolution import evolve
from strategy_generator import print_strategy
from validator import validate

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

    # 3️⃣ التطور اللانهائي ♾️
    round_num = 1
    while True:
        print(f"\n{'═'*40}")
        print(f"🔁 الدورة {round_num}")
        print(f"{'═'*40}")

        best = evolve(df)

        if best:
            s = best["stats"]
            print(f"\n🏆 أفضل الدورة {round_num}:")
            print_strategy(best["strategy"], 0)
            print(f" 📊 Win Rate: {s['win_rate']*100:.1f}%")
            print(f" 💰 Total Profit: {s['total_profit']*100:.2f}%")
            print(f" ⚡ Profit Factor: {s['profit_factor']}")
            print(f" 📉 Drawdown: {s['drawdown']*100:.1f}%")
            print(f" 📈 Sharpe: {s['sharpe']:.2f}")
            print(f" 🔢 Trades: {s['trades']}")

            # شروط القبول
            if (s['win_rate'] > 0.60 and
                s['total_profit'] > 0.40 and
                s['drawdown'] < 0.20):
                print(f"\n🎯 استراتيجية مقبولة! جاري التحقق...")
                validate()

        round_num += 1
        time.sleep(5)

if __name__ == "__main__":
    main()
