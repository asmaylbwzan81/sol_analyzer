"""
backtest.py
===========
يشغل الـ 15 استراتيجية على بيانات تاريخية
ويحدث أوزان strategy_weights.py
يشتغل مرة وحدة فقط
"""

import requests
import time
from strategy_weights import update_weights, init_db, get_stats, reset_all_weights

BINGX_BASE = "https://open-api.bingx.com"

SYMBOLS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "LINK", "AVAX"]
INTERVAL = "4h"
LIMIT = 1000 # أقصى عدد شمعات
FUTURE_CANDLES = 6 # نشوف بعد كم شمعة النتيجة

# ─────────────────────────────────────────────
# جلب البيانات التاريخية
# ─────────────────────────────────────────────
def get_historical(symbol, interval="1h", limit=1000):
    try:
        full_symbol = f"{symbol}-USDT"
        url = f"{BINGX_BASE}/openApi/swap/v2/quote/klines"
        params = {"symbol": full_symbol, "interval": interval, "limit": limit}
        data = requests.get(url, params=params, timeout=10).json()
        candles = data.get("data", [])
        return [{
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"]),
            "volume": float(c["volume"])
        } for c in candles]
    except Exception as e:
        print(f"❌ خطأ جلب {symbol}: {e}")
        return []

# ─────────────────────────────────────────────
# تشغيل الاستراتيجيات
# ─────────────────────────────────────────────
def run_strategies(candles):
    try:
        from strategy_rsi import analyze as rsi
        from strategy_macd import analyze as macd
        from strategy_ema import analyze as ema
        from strategy_bollinger import analyze as bollinger
        from strategy_volume import analyze as volume
        from strategy_momentum import analyze as momentum
        from strategy_support_resistance import analyze as sr
        from strategy_pattern import analyze as pattern
        from strategy_stochastic import analyze as stochastic
        from strategy_vwap import analyze as vwap
        from strategy_adx import analyze as adx
        from strategy_fibonacci import analyze as fib
        from strategy_news import analyze as news
        from strategy_memory import analyze as memory
        from strategy_supertrend import analyze as supertrend

        prices = [c["close"] for c in candles]

        scores = {
            "rsi": rsi(prices),
            "macd": macd(prices),
            "ema": ema(prices),
            "bollinger": bollinger(prices),
            "volume": volume(candles),
            "momentum": momentum(prices),
            "support_resistance": sr(prices),
            "pattern": pattern(candles),
            "stochastic": stochastic(candles),
            "vwap": vwap(candles),
            "adx": adx(candles),
            "fibonacci": fib(prices),
            "news": news("BTC"), # محايد للـ backtest
            "memory": memory("BTC"), # محايد للـ backtest
            "supertrend": supertrend(candles),
        }
        return scores
    except Exception as e:
        print(f"❌ خطأ الاستراتيجيات: {e}")
        return {}

# ─────────────────────────────────────────────
# تحديد النتيجة
# ─────────────────────────────────────────────
def get_result(candles, index, direction, future=10):
    try:
        entry = candles[index]["close"]
        future_index = min(index + future, len(candles) - 1)
        future_price = candles[future_index]["close"]

        if direction == "LONG":
            return "WIN" if future_price > entry else "LOSS"
        elif direction == "SHORT":
            return "WIN" if future_price < entry else "LOSS"
        return None
    except:
        return None

# ─────────────────────────────────────────────
# الـ Backtest الرئيسي
# ─────────────────────────────────────────────
def backtest_symbol(symbol):
    print(f"\n📊 {symbol} — جلب البيانات...")
    candles = get_historical(symbol, INTERVAL, LIMIT)

    if len(candles) < 50:
        print(f"⚠️ بيانات قليلة جداً لـ {symbol}")
        return 0, 0

    wins = 0
    losses = 0
    skips = 0

    # نحلل من شمعة 50 لآخر شمعة - FUTURE_CANDLES
    for i in range(50, len(candles) - FUTURE_CANDLES):
        window = candles[:i+1] # البيانات حتى هاي الشمعة

        scores = run_strategies(window)
        if not scores:
            continue

        # حساب السكور
        total_score = sum(scores.values()) / len(scores)

        # تحديد الاتجاه
        if total_score >= 0.60:
            direction = "LONG"
        elif total_score <= 0.40:
            direction = "SHORT"
        else:
            skips += 1
            continue

        # شرط الأغلبية
        total = len(scores)
        bullish = len([v for v in scores.values() if v >= 0.65])
        bearish = len([v for v in scores.values() if v <= 0.35])

        if direction == "LONG" and bullish <= total * 0.5:
            skips += 1
            continue
        if direction == "SHORT" and bearish <= total * 0.5:
            skips += 1
            continue

        # النتيجة
        result = get_result(candles, i, direction, FUTURE_CANDLES)
        if not result:
            continue

        # المؤشرات المشاركة
        if direction == "LONG":
            strategies_used = [k for k, v in scores.items() if v >= 0.65]
        else:
            strategies_used = [k for k, v in scores.items() if v <= 0.35]

        if strategies_used:
            update_weights(strategies_used, result)

        if result == "WIN":
            wins += 1
        else:
            losses += 1

    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    print(f"✅ {symbol} | صفقات: {total_trades} | WIN: {wins} | LOSS: {losses} | Win Rate: {win_rate:.1f}% | Skip: {skips}")
    return wins, losses

# ─────────────────────────────────────────────
# تشغيل كل العملات
# ─────────────────────────────────────────────
def main():
    print("🚀 Backtest بدأ...")
    print("━" * 50)

    init_db()

    total_wins = 0
    total_losses = 0

    for symbol in SYMBOLS:
        w, l = backtest_symbol(symbol)
        total_wins += w
        total_losses += l
        time.sleep(1)

    print("\n" + "━" * 50)
    print("📊 النتيجة الإجمالية:")
    total = total_wins + total_losses
    if total > 0:
        print(f"✅ WIN: {total_wins} | ❌ LOSS: {total_losses} | Win Rate: {total_wins/total*100:.1f}%")

    print("\n🏆 أوزان الاستراتيجيات بعد التدريب:")
    print(f"{'Strategy':<25} {'Weight':>7} {'Wins':>5} {'Losses':>7} {'Win%':>6}")
    print("-" * 55)
    for s in get_stats():
        wr = f"{s['win_rate']}%" if s['win_rate'] is not None else "N/A"
        print(f"{s['strategy_name']:<25} {s['weight']:>7.2f} {s['wins']:>5} {s['losses']:>7} {wr:>6}")

    print("\n✅ تم تحديث الأوزان! البوت جاهز بخبرة تاريخية 🧠")

if __name__ == "__main__":
    main()

