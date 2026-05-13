import time
import threading
import traceback
from datetime import datetime
from data_engine import init_all_timeframes, load_all_timeframes, count_candles
from features import extract_all_features
from evolution import evolve
from strategy_generator import print_strategy
from redis_store import load_best
from news_filter import should_trade

# ══════════════════════════════
# إعدادات
# ══════════════════════════════
SYMBOL = "BTC-USDT"
MAX_OPEN_TRADES = 5
CAPITAL_PER_TRADE = 10
LEVERAGE = 3
EVOLVE_INTERVAL = 3600
TARGET_CANDLES = {
    "1m": 50000,
    "5m": 20000,
    "15m": 10000,
}

# ══════════════════════════════
# حالة النظام
# ══════════════════════════════
open_trades = []
best_strategy = None
lock = threading.Lock()


# ══════════════════════════════
# تحميل البيانات
# ══════════════════════════════
def prepare_data():
    print("📊 فحص قاعدة البيانات...")
    init_all_timeframes(SYMBOL)

    for interval, target in TARGET_CANDLES.items():
        count = count_candles(SYMBOL, interval)
        print(f" ✅ {interval}: {count} شمعة")

    print("\n📐 تحميل الفريمات...")
    dfs = load_all_timeframes(SYMBOL)

    print("⚙️ استخراج الـ Features...")
    df_features = extract_all_features(dfs)
    print(f"✅ {len(df_features)} صف | {len(df_features.columns)} feature")

    return df_features


# ══════════════════════════════
# حلقة التطور
# ══════════════════════════════
def evolution_loop(df):
    global best_strategy

    round_num = 1
    while True:
        try:
            print(f"\n{'═'*40}")
            print(f"🧬 دورة التطور {round_num} — {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'═'*40}")

            best = evolve(df)

            if best:
                s = best["stats"]
                with lock:
                    best_strategy = best["strategy"]

                print(f"\n🏆 أفضل الدورة {round_num}:")
                print_strategy(best["strategy"], 0)
                print(f" 📊 Win Rate: {s['win_rate']*100:.1f}%")
                print(f" 💰 Total Profit: {s['total_profit']*100:.2f}%")
                print(f" 📉 Drawdown: {s['drawdown']*100:.1f}%")
                print(f" 📈 Sharpe: {s['sharpe']:.2f}")
                print(f" 🔢 Trades: {s['trades']}")
                print(f" 💵 Avg Profit: {s['avg_profit']*100:.3f}%")
            else:
                print("⚠️ ما لاقى استراتيجية بهالدورة")

            round_num += 1
            print(f"\n⏳ انتظار {EVOLVE_INTERVAL//60} دقيقة للدورة القادمة...")
            time.sleep(EVOLVE_INTERVAL)

        except Exception as e:
            print(f"❌ خطأ بـ evolution_loop: {e}")
            traceback.print_exc()
            print("🔄 إعادة المحاولة بعد دقيقة...")
            time.sleep(60)


# ══════════════════════════════
# حلقة التداول
# ══════════════════════════════
def trading_loop():
    global open_trades, best_strategy

    print("\n⚡ حلقة التداول بدأت...")

    while True:
        try:
            trade_ok, reason = should_trade("bitcoin")
            if not trade_ok:
                print(f"🚫 {reason}")
                time.sleep(60)
                continue

            with lock:
                strategy = best_strategy

            if strategy is None:
                saved = load_best()
                if saved:
                    strategy = saved["strategy"]
                    with lock:
                        best_strategy = strategy
                    print("📂 استراتيجية محملة من Redis")
                else:
                    print("⏳ انتظار الاستراتيجية الأولى...")
                    time.sleep(30)
                    continue

            with lock:
                current_open = len(open_trades)

            if current_open >= MAX_OPEN_TRADES:
                time.sleep(5)
                continue

            from data_engine import load_all_timeframes
            from features import extract_all_features
            from strategy_generator import apply_strategy

            dfs = load_all_timeframes(SYMBOL)
            df = extract_all_features(dfs)

            if df.empty:
                time.sleep(10)
                continue

            last_row = df.iloc[-1].to_dict()
            signal = apply_strategy(strategy, last_row)

            if signal:
                direction = strategy["direction"]
                print(f"\n🚀 إشارة {direction} | {datetime.now().strftime('%H:%M:%S')}")
                print(f" 💵 ${CAPITAL_PER_TRADE} × {LEVERAGE}x = ${CAPITAL_PER_TRADE * LEVERAGE}")

                with lock:
                    open_trades.append({
                        "direction": direction,
                        "time": datetime.now(),
                        "capital": CAPITAL_PER_TRADE
                    })
                    print(f" 📊 صفقات مفتوحة: {len(open_trades)}/{MAX_OPEN_TRADES}")

            time.sleep(10)

        except Exception as e:
            print(f"❌ خطأ بـ trading_loop: {e}")
            traceback.print_exc()
            time.sleep(30)


# ══════════════════════════════
# Main
# ══════════════════════════════
def main():
    print("🚀 Quant Bot Started — نظام Simons")
    print("━" * 40)
    print(f" 💵 رأس المال/صفقة: ${CAPITAL_PER_TRADE}")
    print(f" ⚡ Leverage: {LEVERAGE}x")
    print(f" 📊 صفقات متزامنة: {MAX_OPEN_TRADES}")
    print(f" 💰 قوة شراء/صفقة: ${CAPITAL_PER_TRADE * LEVERAGE}")
    print("━" * 40)

    df = prepare_data()

    evolution_thread = threading.Thread(
        target=evolution_loop,
        args=(df,),
        daemon=True
    )
    evolution_thread.start()
    print("\n🧬 Thread التطور بدأ...")

    trading_thread = threading.Thread(
        target=trading_loop,
        daemon=True
    )
    trading_thread.start()
    print("⚡ Thread التداول بدأ...")

    print("\n✅ النظام شغال — Ctrl+C للإيقاف")
    try:
        while True:
            time.sleep(60)
            with lock:
                print(f"\n📊 [{datetime.now().strftime('%H:%M:%S')}] "
                      f"صفقات مفتوحة: {len(open_trades)}/{MAX_OPEN_TRADES}")
    except KeyboardInterrupt:
        print("\n🛑 النظام أوقف")


if __name__ == "__main__":
    main()

