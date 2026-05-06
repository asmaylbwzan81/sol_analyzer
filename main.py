import time
import uuid
import traceback
from datetime import datetime

from data_engine import get_klines, get_candles
from voting_engine import vote, decision
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
from strategy_atr import get_levels
from ai_reviewer import review
from notifier import send_signal, check_result

SYMBOLS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE",
    "BNB", "ADA", "LINK", "AVAX"
]

INTERVALS = ["1d", "4h", "1h"]
SLEEP = 600

def generate_signal_id():
    return str(uuid.uuid4())[:8].upper()

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
            "sr": sr_analyze(prices),
            "pattern": pattern_analyze(candles),
            "stochastic":stochastic_analyze(candles),
            "vwap": vwap_analyze(candles),
            "adx": adx_analyze(candles),
            "fibonacci": fib_analyze(prices),
            "news": news_analyze(symbol),
            "memory": memory_analyze(symbol),
        }
        return scores, candles, prices[-1]
    except Exception as e:
        print(f"❌ Error {symbol} {interval}: {e}")
        traceback.print_exc()
        return None, None, None

def analyze_symbol(symbol):
    try:
        scores_1d, _, _ = get_scores(symbol, "1d")
        scores_4h, _, _ = get_scores(symbol, "4h")
        scores_1h, candles, price = get_scores(symbol, "1h")

        if not scores_1h or not scores_4h or not scores_1d:
            return

        combined = {}
        for key in scores_1h:
            combined[key] = (
                scores_1d[key] * 0.5 +
                scores_4h[key] * 0.3 +
                scores_1h[key] * 0.2
            )

        final_score = vote(combined)
        action, direction = decision(final_score)

        sl_long, sl_short, tp_long, tp_short = get_levels(candles)

        if str(direction) == "LONG":
            sl, tp = sl_long, tp_long
        elif str(direction) == "SHORT":
            sl, tp = sl_short, tp_short
        else:
            sl, tp = None, None

        # ← Groq يراجع ويعطي APPROVE أو REJECT
        verdict, ai_advice = review(combined, final_score, direction, price)

        print(f"\n🪙 {symbol}")
        print(f"💰 Price: {price} | ⚖️ Score: {round(final_score, 2)}")
        print(f"📌 Action: {action} {direction}")
        print(f"🛑 SL: {sl} | 🎯 TP: {tp}")
        print(f"🤖 AI Verdict: {verdict}")
        print(f"💬 AI Advice: {ai_advice}")

        if action == "ENTER" and verdict == "APPROVE":
            signal_id = generate_signal_id()
            save_signal(signal_id, symbol, direction, final_score, price)
            send_signal(signal_id, symbol, direction, final_score, price, ai_advice, combined, sl, tp)
            print(f"✅ Signal Sent! ID: {signal_id}")
        elif action == "ENTER" and verdict == "REJECT":
            print(f"🚫 AI رفض الإشارة! السبب: {ai_advice}")
        else:
            print("⏭️ No Trade")

    except Exception as e:
        print(f"❌ Error {symbol}: {e}")
        traceback.print_exc()

def main():
    print("🚀 Smart Analyzer Bot Started")
    print(f"📊 Symbols: {len(SYMBOLS)}")
    print("━" * 40)

    while True:
        print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        check_result()

        for symbol in SYMBOLS:
            analyze_symbol(symbol)
            time.sleep(2)
        print("━" * 40)
        time.sleep(SLEEP)

if __name__ == "__main__":
    main()

