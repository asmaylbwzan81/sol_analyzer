"""
backtest.py
===========
يشغل النظام الطبقي الجديد على بيانات تاريخية
بـ 3 إطارات زمنية (1d + 4h + 1h) مثل main.py الحقيقي
"""

import requests
import time
from strategy_weights import update_weights, init_db, get_stats
from layer_decision import layer_decision

BINGX_BASE = "https://open-api.bingx.com"

SYMBOLS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "LINK", "AVAX"]
FUTURE_CANDLES = 6

# ─────────────────────────────────────────────
# جلب البيانات التاريخية
# ─────────────────────────────────────────────
def get_historical(symbol, interval="1h", limit=1000):
    try:
        url = f"{BINGX_BASE}/openApi/swap/v2/quote/klines"
        params = {"symbol": f"{symbol}-USDT", "interval": interval, "limit": limit}
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
        print(f"❌ خطأ جلب {symbol} {interval}: {e}")
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
            "news": 0.5,
            "memory": 0.5,
            "supertrend": supertrend(candles),
        }
    except Exception as e:
        print(f"❌ خطأ الاستراتيجيات: {e}")
        return {}

# ─────────────────────────────────────────────
# دمج 3 إطارات (نفس main.py)
# ─────────────────────────────────────────────
def combine_timeframes(scores_1d, scores_4h, scores_1h):
    combined = {}
    for key in scores_1h:
        combined[key] = (
            scores_1d.get(key, 0.5) * 0.5 +
            scores_4h.get(key, 0.5) * 0.3 +
            scores_1h.get(key, 0.5) * 0.2
        )
    return combined

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
    except:
        pass
    return None

# ─────────────────────────────────────────────
# Backtest لكل عملة
# ─────────────────────────────────────────────
def backtest_symbol(symbol):
    print(f"\n{'═'*50}")
    print(f"📊 {symbol} — جلب البيانات (3 إطارات)...")

    candles_1h = get_historical(symbol, "1h", 1000)
    candles_4h = get_historical(symbol, "4h", 500)
    candles_1d = get_historical(symbol, "1d", 200)

    if len(candles_1h) < 50:
        print(f"⚠️ بيانات قليلة لـ {symbol}")
        return 0, 0

    wins = losses = skips = 0
    skip_reasons = {
        "trend": 0, "liquidity": 0, "momentum": 0,
        "structure": 0, "volatility": 0, "confidence": 0,
    }

    for i in range(50, len(candles_1h) - FUTURE_CANDLES):
        w_1h = candles_1h[:i+1]
        i_4h = min(int(i / 4), len(candles_4h) - 1)
        i_1d = min(int(i / 24), len(candles_1d) - 1)
        w_4h = candles_4h[:i_4h+1]
        w_1d = candles_1d[:i_1d+1]

        if len(w_4h) < 50 or len(w_1d) < 50:
            continue

        scores_1h = run_strategies(w_1h)
        scores_4h = run_strategies(w_4h)
        scores_1d = run_strategies(w_1d)

        if not scores_1h or not scores_4h or not scores_1d:
            continue

        # ══ دمج 3 إطارات مثل main.py ══
        combined = combine_timeframes(scores_1d, scores_4h, scores_1h)

        # ══ النظام الطبقي ══
        result_data = layer_decision(combined)
        action = result_data["action"]
        direction = result_data["direction"]

        if action == "SKIP":
            skips += 1
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

        result = get_result(candles_1h, i, direction, FUTURE_CANDLES)
        if not result:
            continue

        if direction == "LONG":
            strategies_used = [k for k, v in scores_1h.items() if v >= 0.62]
        else:
            strategies_used = [k for k, v in scores_1h.items() if v <= 0.38]

        if strategies_used:
            update_weights(strategies_used, result)

        if result == "WIN": wins += 1
        else: losses += 1

    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0
    print(f"✅ صفقات: {total} | WIN: {wins} | LOSS: {losses} | Win Rate: {win_rate:.1f}%")
    print(f"⏭️ تخطي: {skips} | Trend={skip_reasons['trend']} Liq={skip_reasons['liquidity']} Mom={skip_reasons['momentum']} Str={skip_reasons['structure']} Vol={skip_reasons['volatility']} Conf={skip_reasons['confidence']}")
    return wins, losses

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    print("🚀 Backtest سمارت — 3 إطارات زمنية")
    print("━" * 50)

    init_db()

    total_wins = total_losses = 0

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
            print("🏆 ممتاز! النظام جاهز")
        elif wr >= 50:
            print("⚠️ معقول، يحتاج تحسين")
        else:
            print("❌ يحتاج مراجعة")

    print("\n🏆 أوزان الاستراتيجيات:")
    print(f"{'Strategy':<25} {'Weight':>7} {'Wins':>5} {'Losses':>7} {'Win%':>6}")
    print("-" * 55)
    for s in get_stats():
        wr = f"{s['win_rate']}%" if s['win_rate'] is not None else "N/A"
        print(f"{s['strategy_name']:<25} {s['weight']:>7.2f} {s['wins']:>5} {s['losses']:>7} {wr:>6}")

    # ── توصيات ──────────────────────────────
    print("\n" + "═" * 50)
    print("💡 التوصيات:")
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
        print(f"\n🔴 مؤشرات ضعيفة (< 45%):")
        for name, wr in weak_strategies:
            print(f" • {name}: {wr}%")

    if strong_strategies:
        print(f"\n🟢 مؤشرات قوية (>= 65%):")
        for name, wr in strong_strategies:
            print(f" • {name}: {wr}%")

    print("\n📋 توصيات عامة:")
    if total > 0:
        wr = total_wins / total * 100
        if wr < 50:
            print(" • رفع MIN_CONFIDENCE إلى 0.80")
            print(" • تشديد شرط الهيكل 2/3")
            print(" • مراجعة مؤشرات الاتجاه")
        elif wr < 60:
            print(" • رفع MIN_CONFIDENCE إلى 0.78")
            print(" • مراقبة المؤشرات الضعيفة")
        else:
            print(" • النظام جيد — راقب أسبوع وأعد الفحص")

    print("═" * 50)

if __name__ == "__main__":
    main()

