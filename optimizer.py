optimizer.py
============
يجرب كل الإعدادات لكل مؤشر
ويحفظ أفضل إعدادات في config.json
يشتغل مرة وحدة فقط
"""

import requests
import json
import time
import itertools

BINGX_BASE = "https://open-api.bingx.com"
SYMBOLS = ["BTC", "DOGE", "SOL"]
INTERVAL = "4h"
LIMIT = 1000 # ~6 أشهر
FUTURE_CANDLES = 6 # 24 ساعة للأمام
CONFIG_FILE = "config.json"

# ─────────────────────────────────────────────
# جلب البيانات
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
# تحديد النتيجة
# ─────────────────────────────────────────────
def get_result(candles, index, direction, future=6):
    try:
        entry = candles[index]["close"]
        future_index = min(index + future, len(candles) - 1)
        future_price = candles[future_index]["close"]
        if direction == "LONG":
            return "WIN" if future_price > entry else "LOSS"
        else:
            return "WIN" if future_price < entry else "LOSS"
    except:
        return None

# ─────────────────────────────────────────────
# تقييم مؤشر بإعداد معين
# ─────────────────────────────────────────────
def evaluate(candles, analyze_func, **kwargs):
    wins = 0
    losses = 0
    prices = [c["close"] for c in candles]

    for i in range(50, len(candles) - FUTURE_CANDLES):
        window_candles = candles[:i+1]
        window_prices = prices[:i+1]

        try:
            # نمرر الأسعار أو الشمعات حسب المؤشر
            score = analyze_func(window_prices, **kwargs) if kwargs.get("use_prices", True) else analyze_func(window_candles, **kwargs)
        except:
            continue

        if score >= 0.65:
            direction = "LONG"
        elif score <= 0.35:
            direction = "SHORT"
        else:
            continue

        result = get_result(candles, i, direction, FUTURE_CANDLES)
        if result == "WIN":
            wins += 1
        elif result == "LOSS":
            losses += 1

    total = wins + losses
    if total < 5:
        return 0.0
    return round(wins / total * 100, 1)

# ─────────────────────────────────────────────
# Optimizer لكل مؤشر
# ─────────────────────────────────────────────
def optimize_rsi(all_candles):
    print("\n📊 RSI — يجرب الإعدادات...")
    from strategy_rsi import analyze
    best_period, best_wr = 14, 0

    for period in range(5, 31):
        wrs = []
        for candles in all_candles:
            prices = [c["close"] for c in candles]
            wr = evaluate(candles, lambda p, period=period: analyze(p, period=period), use_prices=True)
            wrs.append(wr)
        avg_wr = sum(wrs) / len(wrs)
        if avg_wr > best_wr:
            best_wr = avg_wr
            best_period = period

    print(f"✅ RSI | أفضل period={best_period} | Win Rate: {best_wr:.1f}%")
    return {"rsi_period": best_period, "rsi_winrate": best_wr}


def optimize_bollinger(all_candles):
    print("\n📊 Bollinger — يجرب الإعدادات...")
    from strategy_bollinger import analyze
    best_period, best_wr = 20, 0

    for period in range(10, 31):
        wrs = []
        for candles in all_candles:
            prices = [c["close"] for c in candles]
            wr = evaluate(candles, lambda p, period=period: analyze(p, period=period), use_prices=True)
            wrs.append(wr)
        avg_wr = sum(wrs) / len(wrs)
        if avg_wr > best_wr:
            best_wr = avg_wr
            best_period = period

    print(f"✅ Bollinger | أفضل period={best_period} | Win Rate: {best_wr:.1f}%")
    return {"bollinger_period": best_period, "bollinger_winrate": best_wr}


def optimize_adx(all_candles):
    print("\n📊 ADX — يجرب الإعدادات...")
    from strategy_adx import analyze
    best_period, best_wr = 14, 0

    for period in range(5, 31):
        wrs = []
        for candles in all_candles:
            try:
                wr = evaluate(candles, lambda c, period=period: analyze(c, period=period), use_prices=False)
                wrs.append(wr)
            except: pass
        if not wrs: continue
        avg_wr = sum(wrs) / len(wrs)
        if avg_wr > best_wr:
            best_wr = avg_wr
            best_period = period

    print(f"✅ ADX | أفضل period={best_period} | Win Rate: {best_wr:.1f}%")
    return {"adx_period": best_period, "adx_winrate": best_wr}


def optimize_stochastic(all_candles):
    print("\n📊 Stochastic — يجرب الإعدادات...")
    from strategy_stochastic import analyze
    best_period, best_wr = 14, 0

    for period in range(5, 31):
        wrs = []
        for candles in all_candles:
            try:
                wr = evaluate(candles, lambda c, period=period: analyze(c, period=period), use_prices=False)
                wrs.append(wr)
            except: pass
        if not wrs: continue
        avg_wr = sum(wrs) / len(wrs)
        if avg_wr > best_wr:
            best_wr = avg_wr
            best_period = period

    print(f"✅ Stochastic | أفضل period={best_period} | Win Rate: {best_wr:.1f}%")
    return {"stochastic_period": best_period, "stochastic_winrate": best_wr}


def optimize_supertrend(all_candles):
    print("\n📊 Supertrend — يجرب الإعدادات...")
    from strategy_supertrend import analyze
    best_period, best_mult, best_wr = 10, 3.0, 0

    for period in range(5, 21):
        for mult in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]:
            wrs = []
            for candles in all_candles:
                try:
                    wr = evaluate(candles, lambda c, p=period, m=mult: analyze(c, period=p, multiplier=m), use_prices=False)
                    wrs.append(wr)
                except: pass
            if not wrs: continue
            avg_wr = sum(wrs) / len(wrs)
            if avg_wr > best_wr:
                best_wr = avg_wr
                best_period = period
                best_mult = mult

    print(f"✅ Supertrend | أفضل period={best_period}, mult={best_mult} | Win Rate: {best_wr:.1f}%")
    return {"supertrend_period": best_period, "supertrend_mult": best_mult, "supertrend_winrate": best_wr}


def optimize_fibonacci(all_candles):
    print("\n📊 Fibonacci — يجرب الإعدادات...")
    from strategy_fibonacci import analyze
    best_period, best_wr = 50, 0

    for period in range(20, 101, 5):
        wrs = []
        for candles in all_candles:
            prices = [c["close"] for c in candles]
            wr = evaluate(candles, lambda p, period=period: analyze(p, period=period), use_prices=True)
            wrs.append(wr)
        avg_wr = sum(wrs) / len(wrs)
        if avg_wr > best_wr:
            best_wr = avg_wr
            best_period = period

    print(f"✅ Fibonacci | أفضل period={best_period} | Win Rate: {best_wr:.1f}%")
    return {"fibonacci_period": best_period, "fibonacci_winrate": best_wr}


def optimize_momentum(all_candles):
    print("\n📊 Momentum — يجرب الإعدادات...")
    from strategy_momentum import analyze
    best_period, best_wr = 10, 0

    for period in range(5, 26):
        wrs = []
        for candles in all_candles:
            prices = [c["close"] for c in candles]
            wr = evaluate(candles, lambda p, period=period: analyze(p, period=period), use_prices=True)
            wrs.append(wr)
        avg_wr = sum(wrs) / len(wrs)
        if avg_wr > best_wr:
            best_wr = avg_wr
            best_period = period

    print(f"✅ Momentum | أفضل period={best_period} | Win Rate: {best_wr:.1f}%")
    return {"momentum_period": best_period, "momentum_winrate": best_wr}


def optimize_sr(all_candles):
    print("\n📊 Support/Resistance — يجرب الإعدادات...")
    from strategy_support_resistance import analyze
    best_period, best_wr = 20, 0

    for period in range(10, 51, 5):
        wrs = []
        for candles in all_candles:
            prices = [c["close"] for c in candles]
            wr = evaluate(candles, lambda p, period=period: analyze(p, period=period), use_prices=True)
            wrs.append(wr)
        avg_wr = sum(wrs) / len(wrs)
        if avg_wr > best_wr:
            best_wr = avg_wr
            best_period = period

    print(f"✅ Support/Resistance | أفضل period={best_period} | Win Rate: {best_wr:.1f}%")
    return {"sr_period": best_period, "sr_winrate": best_wr}


def optimize_macd(all_candles):
    print("\n📊 MACD — يجرب الإعدادات...")
    from strategy_macd import analyze, ema
    best_fast, best_slow, best_wr = 12, 26, 0

    for fast in range(5, 16):
        for slow in range(20, 36):
            if fast >= slow: continue
            wrs = []
            for candles in all_candles:
                prices = [c["close"] for c in candles]
                try:
                    def macd_analyze(p, f=fast, s=slow):
                        if len(p) < s: return 0.5
                        ema_f = ema(p, f)
                        ema_s = ema(p, s)
                        macd_val = ema_f - ema_s
                        price = p[-1]
                        macd_pct = (macd_val / price) * 100
                        if macd_pct > 2.0: return 0.95
                        elif macd_pct > 1.0: return 0.85
                        elif macd_pct > 0.5: return 0.75
                        elif macd_pct > 0.2: return 0.65
                        elif macd_pct > 0.0: return 0.55
                        elif macd_pct > -0.2: return 0.45
                        elif macd_pct > -0.5: return 0.35
                        elif macd_pct > -1.0: return 0.25
                        elif macd_pct > -2.0: return 0.15
                        else: return 0.05
                    wr = evaluate(candles, lambda p, f=fast, s=slow: macd_analyze(p, f, s), use_prices=True)
                    wrs.append(wr)
                except: pass
            if not wrs: continue
            avg_wr = sum(wrs) / len(wrs)
            if avg_wr > best_wr:
                best_wr = avg_wr
                best_fast = fast
                best_slow = slow

    print(f"✅ MACD | أفضل fast={best_fast}, slow={best_slow} | Win Rate: {best_wr:.1f}%")
    return {"macd_fast": best_fast, "macd_slow": best_slow, "macd_winrate": best_wr}


def optimize_ema(all_candles):
    print("\n📊 EMA — يجرب الإعدادات...")
    from strategy_ema import analyze, ema
    best_short, best_long, best_wr = 20, 50, 0

    for short in range(10, 31):
        for long in range(30, 71, 5):
            if short >= long: continue
            wrs = []
            for candles in all_candles:
                prices = [c["close"] for c in candles]
                try:
                    def ema_analyze(p, s=short, l=long):
                        if len(p) < l: return 0.5
                        ema_s = ema(p[-s:], s)
                        ema_l = ema(p[-l:], l)
                        price = p[-1]
                        pct_s = (price - ema_s) / ema_s * 100
                        pct_l = (price - ema_l) / ema_l * 100
                        score = 0.5
                        if pct_s > 3.0: score += 0.20
                        elif pct_s > 1.5: score += 0.15
                        elif pct_s > 0.5: score += 0.10
                        elif pct_s > 0.0: score += 0.05
                        elif pct_s > -0.5: score -= 0.05
                        elif pct_s > -1.5: score -= 0.10
                        elif pct_s > -3.0: score -= 0.15
                        else: score -= 0.20
                        if pct_l > 3.0: score += 0.20
                        elif pct_l > 1.5: score += 0.15
                        elif pct_l > 0.5: score += 0.10
                        elif pct_l > 0.0: score += 0.05
                        elif pct_l > -0.5: score -= 0.05
                        elif pct_l > -1.5: score -= 0.10
                        elif pct_l > -3.0: score -= 0.15
                        else: score -= 0.20
                        return max(0.0, min(1.0, score))
                    wr = evaluate(candles, lambda p, s=short, l=long: ema_analyze(p, s, l), use_prices=True)
                    wrs.append(wr)
                except: pass
            if not wrs: continue
            avg_wr = sum(wrs) / len(wrs)
            if avg_wr > best_wr:
                best_wr = avg_wr
                best_short = short
                best_long = long

    print(f"✅ EMA | أفضل short={best_short}, long={best_long} | Win Rate: {best_wr:.1f}%")
    return {"ema_short": best_short, "ema_long": best_long, "ema_winrate": best_wr}


# ─────────────────────────────────────────────
# الـ Main
# ─────────────────────────────────────────────
def main():
    print("🚀 Optimizer بدأ...")
    print("━" * 50)

    # جلب البيانات
    all_candles = []
    for symbol in SYMBOLS:
        print(f"📊 جلب بيانات {symbol}...")
        candles = get_historical(symbol, INTERVAL, LIMIT)
        if candles:
            all_candles.append(candles)
            print(f"✅ {symbol} | {len(candles)} شمعة")
        time.sleep(1)

    if not all_candles:
        print("❌ ما في بيانات!")
        return

    # تشغيل الـ Optimizer لكل مؤشر
    config = {}
    config.update(optimize_rsi(all_candles))
    config.update(optimize_bollinger(all_candles))
    config.update(optimize_adx(all_candles))
    config.update(optimize_stochastic(all_candles))
    config.update(optimize_supertrend(all_candles))
    config.update(optimize_fibonacci(all_candles))
    config.update(optimize_momentum(all_candles))
    config.update(optimize_sr(all_candles))
    config.update(optimize_macd(all_candles))
    config.update(optimize_ema(all_candles))

    # حفظ النتائج
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

    print("\n" + "━" * 50)
    print("🏆 أفضل إعدادات المؤشرات:")
    print(f"{'المؤشر':<25} {'الإعداد':<30} {'Win Rate':>8}")
    print("-" * 65)
    print(f"{'RSI':<25} {'period=' + str(config['rsi_period']):<30} {config['rsi_winrate']:>7.1f}%")
    print(f"{'Bollinger':<25} {'period=' + str(config['bollinger_period']):<30} {config['bollinger_winrate']:>7.1f}%")
    print(f"{'ADX':<25} {'period=' + str(config['adx_period']):<30} {config['adx_winrate']:>7.1f}%")
    print(f"{'Stochastic':<25} {'period=' + str(config['stochastic_period']):<30} {config['stochastic_winrate']:>7.1f}%")
    print(f"{'Supertrend':<25} {'period=' + str(config['supertrend_period']) + ', mult=' + str(config['supertrend_mult']):<30} {config['supertrend_winrate']:>7.1f}%")
    print(f"{'Fibonacci':<25} {'period=' + str(config['fibonacci_period']):<30} {config['fibonacci_winrate']:>7.1f}%")
    print(f"{'Momentum':<25} {'period=' + str(config['momentum_period']):<30} {config['momentum_winrate']:>7.1f}%")
    print(f"{'Support/Resistance':<25} {'period=' + str(config['sr_period']):<30} {config['sr_winrate']:>7.1f}%")
    print(f"{'MACD':<25} {'fast=' + str(config['macd_fast']) + ', slow=' + str(config['macd_slow']):<30} {config['macd_winrate']:>7.1f}%")
    print(f"{'EMA':<25} {'short=' + str(config['ema_short']) + ', long=' + str(config['ema_long']):<30} {config['ema_winrate']:>7.1f}%")

    print(f"\n✅ تم حفظ الإعدادات في {CONFIG_FILE} 🧠")
    print("✅ البوت جاهز بأفضل إعدادات!")

if __name__ == "__main__":
    main()

