
import time
import uuid
import traceback
from datetime import datetime

from data_engine import get_klines, get_candles
from voting_engine import vote, decision, _get_tier, STRONG_BASE
from strategy_weights import get_all_weights
from strategy_rsi import analyze as rsi_analyze
from strategy_macd import analyze as macd_analyze
from strategy_ema import analyze as ema_analyze
from strategy_bollinger import analyze as bollinger_analyze
from strategy_volume import analyze as volume_analyze
from strategy_momentum import analyze as momentum_analyze
from strategy_support_resistance import analyze as sr_analyze
from strategy_pattern import analyze as pattern_analyze
from strategy_stochastic import analyze as stochastic_analyze
from strategy_vwap import analyze as vwap_analyze
from strategy_adx import analyze as adx_analyze
from strategy_fibonacci import analyze as fib_analyze
from strategy_news import analyze as news_analyze
from strategy_memory import analyze as memory_analyze, save_signal
from strategy_supertrend import analyze as supertrend_analyze
from strategy_atr import get_levels
from ai_reviewer import review
from notifier import send_signal, check_result, send_startup

SYMBOLS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE",
    "BNB", "ADA", "LINK", "AVAX"
]

SLEEP = 600
MIN_RANK = 0.60 # الحد الأدنى للـ rank عشان تُبعث

def quick_rsi(prices, period=14):
    """حساب RSI سريع"""
    if len(prices) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, period + 1):
        diff = prices[-i] - prices[-i-1]
        if diff > 0: gains.append(diff)
        else: losses.append(abs(diff))
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)

def quick_adx(candles, period=14):
    """حساب ADX سريع"""
    try:
        if len(candles) < period + 1:
            return 0
        trs = []
        for i in range(1, len(candles)):
            h, l, pc = candles[i]["high"], candles[i]["low"], candles[i-1]["close"]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr = sum(trs[-period:]) / period
        if atr == 0: return 0
        return round(min(sum(trs[-period:]) / (atr * period) * 25, 100), 1)
    except:
        return 0

def quick_vol_ratio(candles, period=20):
    """نسبة الحجم الحالي مقارنة بالمتوسط"""
    try:
        if len(candles) < period + 1:
            return 1.0
        avg_vol = sum(c["volume"] for c in candles[-period-1:-1]) / period
        if avg_vol == 0: return 1.0
        return round(candles[-1]["volume"] / avg_vol, 2)
    except:
        return 1.0

def should_analyze(prices, candles):
    """فلتر سريع — هل في سبب حقيقي للتحليل؟"""
    rsi = quick_rsi(prices)
    adx = quick_adx(candles)
    vol_ratio = quick_vol_ratio(candles)
    reason = []
    if rsi < 35: reason.append(f"RSI oversold {rsi}")
    if rsi > 65: reason.append(f"RSI overbought {rsi}")
    if adx > 25: reason.append(f"ADX strong {adx}")
    if vol_ratio > 1.5: reason.append(f"Volume spike {vol_ratio}x")
    if reason:
        print(f"✅ فلتر اجتاز: {' | '.join(reason)}")
        return True
    print(f"⏭️ فلتر: RSI={rsi} ADX={adx} Vol={vol_ratio}x — تخطي")
    return False

def generate_signal_id():
    return str(uuid.uuid4())[:8].upper()

def calc_rank(final_score, combined):
    """
    rank = (score × 0.7) + (strong_agree_count / 5 × 0.3)
    """
    weights = get_all_weights()
    strong_agree = sum(
        1 for k, v in combined.items()
        if _get_tier(k, weights.get(k, 1.0)) == "strong"
        and (v >= 0.65 or v <= 0.35)
    )
    rank = (final_score * 0.7) + (strong_agree / 5 * 0.3)

    # للـ SHORT نعكس الـ score عشان الحساب يكون صح
    if final_score <= 0.40:
        inverted = 1.0 - final_score
        rank = (inverted * 0.7) + (strong_agree / 5 * 0.3)

    return round(rank, 4), strong_agree

def get_scores(symbol, interval):
    try:
        prices = get_klines(symbol, interval)
        candles = get_candles(symbol, interval)
        scores = {
            "rsi": rsi_analyze(prices),
            "macd": macd_analyze(prices),
            "ema": ema_analyze(prices),
            "bollinger": bollinger_analyze(prices),
            "volume": volume_analyze(candles),
            "momentum": momentum_analyze(prices),
            "support_resistance": sr_analyze(prices),
            "pattern": pattern_analyze(candles),
            "stochastic": stochastic_analyze(candles),
            "vwap": vwap_analyze(candles),
            "adx": adx_analyze(candles),
            "fibonacci": fib_analyze(prices),
            "news": news_analyze(symbol),
            "memory": memory_analyze(symbol),
            "supertrend": supertrend_analyze(candles),
        }
        return scores, candles, prices[-1]
    except Exception as e:
        print(f"❌ Error {symbol} {interval}: {e}")
        traceback.print_exc()
        return None, None, None

def analyze_symbol(symbol):
    """يحلل العملة ويرجع بيانات الإشارة أو None"""
    try:
        scores_1d, _, _ = get_scores(symbol, "1d")
        scores_4h, _, _ = get_scores(symbol, "4h")
        scores_1h, candles_1h, price = get_scores(symbol, "1h")
        prices_1h = [c["close"] for c in candles_1h] if candles_1h else []

        if not scores_1h or not scores_4h or not scores_1d:
            return None

        # ── فلتر سريع قبل التحليل الكامل ──
        if not should_analyze(prices_1h, candles_1h):
            return None

        combined = {}
        for key in scores_1h:
            combined[key] = (
                scores_1d[key] * 0.5 +
                scores_4h[key] * 0.3 +
                scores_1h[key] * 0.2
            )

        final_score = vote(combined)
        action, direction = decision(final_score, combined)

        sl_long, sl_short, tp_long, tp_short = get_levels(candles_1h)

        if direction == "LONG":
            sl, tp = sl_long, tp_long
        elif direction == "SHORT":
            sl, tp = sl_short, tp_short
        else:
            sl, tp = None, None

        verdict, ai_advice = review(combined, final_score, direction, price)

        print(f"\n🪙 {symbol}")
        print(f"💰 Price: {price} | ⚖️ Score: {round(final_score, 2)}")
        print(f"📌 Action: {action} {direction}")
        print(f"🛑 SL: {sl} | 🎯 TP: {tp}")
        print(f"🤖 AI Verdict: {verdict}")
        print(f"💬 AI Advice: {ai_advice}")

        if action == "ENTER" and verdict == "APPROVE":
            rank, strong_agree = calc_rank(final_score, combined)
            print(f"🏆 Rank: {rank} | Strong Agree: {strong_agree}")
            return {
                "symbol": symbol,
                "direction": direction,
                "score": final_score,
                "rank": rank,
                "price": price,
                "sl": sl,
                "tp": tp,
                "ai_advice": ai_advice,
                "combined": combined,
            }
        elif action == "ENTER" and verdict == "REJECT":
            print(f"🚫 AI رفض الإشارة! السبب: {ai_advice}")
        else:
            print("⏭️ No Trade")

    except Exception as e:
        print(f"❌ Error {symbol}: {e}")
        traceback.print_exc()

    return None

def main():
    print("🚀 Smart Analyzer Bot Started")
    print(f"📊 Symbols: {len(SYMBOLS)}")
    print("━" * 40)
    send_startup()

    while True:
        print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        check_result()

        # ── جمع كل الإشارات ──
        candidates = []
        for symbol in SYMBOLS:
            result = analyze_symbol(symbol)
            if result:
                candidates.append(result)
            time.sleep(2)

        # ── اختيار الأقوى ──
        if candidates:
            # فلتر rank >= MIN_RANK
            qualified = [c for c in candidates if c["rank"] >= MIN_RANK]

            if qualified:
                # الأقوى rank
                best = max(qualified, key=lambda x: x["rank"])

                signal_id = generate_signal_id()
                save_signal(signal_id, best["symbol"], best["direction"], best["score"], best["price"])
                send_signal(
                    signal_id,
                    best["symbol"],
                    best["direction"],
                    best["score"],
                    best["price"],
                    best["ai_advice"],
                    best["combined"],
                    best["sl"],
                    best["tp"]
                )
                print(f"\n🏆 أفضل إشارة: {best['symbol']} {best['direction']} | Rank: {best['rank']}")
                print(f"✅ Signal Sent! ID: {signal_id}")
                print(f"📊 المرشحون: {len(candidates)} | المؤهلون: {len(qualified)}")
            else:
                print(f"\n⏭️ كل الإشارات تحت الحد الأدنى ({MIN_RANK}) — لا شيء يُبعث")
                print(f"📊 المرشحون: {len(candidates)}")
        else:
            print("\n⏭️ لا توجد إشارات هذه الدورة")

        print("━" * 40)
        time.sleep(SLEEP)

if __name__ == "__main__":
    main()
