"""
backtest.py
===========
يشغل النظام الطبقي الجديد على بيانات تاريخية
ويحدث أوزان strategy_weights.py
"""

import requests
import time
from strategy_weights import update_weights, init_db, get_stats
from layer_decision import layer_decision

BINGX_BASE = "https://open-api.bingx.com"

SYMBOLS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "LINK", "AVAX"]
INTERVAL = "4h"
LIMIT = 1000
FUTURE_CANDLES = 6

# ─────────────────────────────────────────────
# جلب البيانات التاريخية
# ─────────────────────────────────────────────
def get_historical(symbol, interval="4h", limit=1000):
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
def run_strategies(candles, symbol="BTC"):
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

        return {
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
            "news": 0.5, # محايد في الـ backtest
            "memory": 0.5, # محايد في الـ backtest
            "supertrend": supertrend(candles),
        }
    except Exception as e:
        print(f"❌ خطأ الاستراتيجيات: {e}")
        return {}

# ─────────────────────────────────────────────
# تحديد النتيجة
# ─────────────────────────────────────────────
def get_result(candles, index, direction, future=6):
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
    print(f"\n{'═'*50}")
    print(f"📊 {symbol} — جلب البيانات...")
    candles = get_historical(symbol, INTERVAL, LIMIT)

    if len(candles) < 50:
        print(f"⚠️ بيانات قليلة جداً لـ {symbol}")
        return 0, 0

    wins = 0
    losses = 0
    skips = 0

    # إحصائيات الرفض لكل طبقة
    skip_reasons = {
        "trend": 0,
        "liquidity": 0,
        "momentum": 0,
        "structure": 0,
        "volatility":0,
        "confidence":0,
    }

    for i in range(50, len(candles) - FUTURE_CANDLES):
        window = candles[:i+1]
        scores = run_strategies(window, symbol)
        if not scores:
            continue

        # ══ النظام الطبقي الجديد ══
        result_data = layer_decision(scores)
        action = result_data["action"]
        direction = result_data["direction"]

        if action == "SKIP":
            skips += 1
            # تسجيل سبب الرفض
            reason = result_data.get("reason", "")
            if "Trend" in reason: skip_reasons["trend"] += 1
            elif "Liquidity" in reason: skip_reasons["liquidity"] += 1
            elif "Momentum" in reason: skip_reasons["momentum"] += 1
            elif "Structure" in reason: skip_reasons["structure"] += 1
            elif "Volatility" in reason: skip_reasons["volatility"] += 1
            elif "ثقة" in reason: skip_reasons["confidence"] += 1
            continue

        if direction not in ("LONG", "SHORT"):
            skips += 1
            continue

        # النتيجة
        result = get_result(candles, i, direction, FUTURE_CANDLES)
        if not result:
            continue

        # تحديث الأوزان
        if direction == "LONG":
            strategies_used = [k for k, v in scores.items() if v >= 0.62]
        else:
            strategies_used = [k for k, v in scores.items() if v <= 0.38]

        if strategies_used:
            update_weights(strategies_used, result)

        if result == "WIN":
            wins += 1
        else:
            losses += 1

    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    print(f"✅ صفقات: {total_trades} | WIN: {wins} | LOSS: {losses} | Win Rate: {win_rate:.1f}%")
    print(f"⏭️ تخطي: {skips} | أسباب: Trend={skip_reasons['trend']} Liq={skip_reasons['liquidity']} Mom={skip_reasons['momentum']} Str={skip_reasons['structure']} Vol={skip_reasons['volatility']} Conf={skip_reasons['confidence']}")

    return wins, losses

# ─────────────────────────────────────────────
# تشغيل كل العملات
# ─────────────────────────────────────────────
def main():
    print("🚀 Backtest بدأ — النظام الطبقي الجديد")
    print("━" * 50)

    init_db()

    total_wins = 0
    total_losses = 0

    for symbol in SYMBOLS:
        w, l = backtest_symbol(symbol)
        total_wins += w
        total_losses += l
        time.sleep(1)

    print("\n" + "═" * 50)
    print("📊 النتيجة الإجمالية:")
    total = total_wins + total_losses
    if total > 0:
        wr = total_wins / total * 100
        print(f"✅ WIN: {total_wins} | ❌ LOSS: {total_losses} | Win Rate: {wr:.1f}%")
        if wr >= 60:
            print("🏆 ممتاز! النظام جاهز للتداول الحقيقي")
        elif wr >= 50:
            print("⚠️ معقول، يحتاج تحسين بسيط")
        else:
            print("❌ النظام يحتاج مراجعة — Win Rate منخفض")

    print("\n🏆 أوزان الاستراتيجيات بعد التدريب:")
    print(f"{'Strategy':<25} {'Weight':>7} {'Wins':>5} {'Losses':>7} {'Win%':>6}")
    print("-" * 55)
    for s in get_stats():
        wr = f"{s['win_rate']}%" if s['win_rate'] is not None else "N/A"
        print(f"{s['strategy_name']:<25} {s['weight']:>7.2f} {s['wins']:>5} {s['losses']:>7} {wr:>6}")

    print("\n✅ تم تحديث الأوزان! البوت جاهز بخبرة تاريخية 🧠")

    # ── تحليل وتوصيات ──────────────────────────
    print("\n" + "═" * 50)
    print("💡 التوصيات بناءً على النتائج:")
    print("─" * 50)

    stats = get_stats()
    weak_strategies = []
    strong_strategies = []

    for s in stats:
        if s['win_rate'] is not None:
            if s['win_rate'] < 45:
                weak_strategies.append((s['strategy_name'], s['win_rate']))
            elif s['win_rate'] >= 65:
                strong_strategies.append((s['strategy_name'], s['win_rate']))

    if weak_strategies:
        print(f"\n🔴 مؤشرات ضعيفة (Win Rate < 45%) — فكر في تقليل وزنها:")
        for name, wr in weak_strategies:
            print(f" • {name}: {wr}%")

    if strong_strategies:
        print(f"\n🟢 مؤشرات قوية (Win Rate >= 65%) — زد اعتمادك عليها:")
        for name, wr in strong_strategies:
            print(f" • {name}: {wr}%")

    print("\n📋 توصيات عامة:")
    total = total_wins + total_losses
    if total > 0:
        wr = total_wins / total * 100
        if wr < 50:
            print(" • رفع MIN_CONFIDENCE من 0.75 إلى 0.80")
            print(" • تشديد شرط الهيكل — require 2/3 بدل 1/3")
            print(" • مراجعة مؤشرات الاتجاه (EMA/ADX/Supertrend)")
        elif wr < 60:
            print(" • رفع MIN_CONFIDENCE من 0.75 إلى 0.78")
            print(" • مراقبة المؤشرات الضعيفة أعلاه")
        else:
            print(" • النظام شغال جيد — راقب النتائج الحية أسبوع")
            print(" • بعد 50 صفقة حية شغّل backtest مجدداً للتحديث")

    print("═" * 50)

if __name__ == "__main__":
    main()

