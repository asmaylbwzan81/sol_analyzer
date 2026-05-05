import time
import uuid
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
from notifier import send_signal

SYMBOL = "ETH-USDT"
INTERVAL = "1h"
SLEEP = 60

def generate_signal_id():
    return str(uuid.uuid4())[:8].upper()

def main():
    print("🚀 Smart Analyzer Bot Started")
    print(f"📊 Symbol: {SYMBOL} | Interval: {INTERVAL}")
    print("━" * 40)

    while True:
        try:
            prices = get_klines(SYMBOL, INTERVAL)
            candles = get_candles(SYMBOL, INTERVAL)
            price = prices[-1]

            scores = {
                "rsi": rsi_analyze(prices),
                "macd": macd_analyze(prices),
                "ema": ema_analyze(prices),
                "bollinger": bollinger_analyze(prices),
                "volume": volume_analyze(candles),
                "momentum": momentum_analyze(prices),
                "sr": sr_analyze(prices),
                "pattern": pattern_analyze(candles),
                "stochastic": stochastic_analyze(candles),
                "vwap": vwap_analyze(candles),
                "adx": adx_analyze(candles),
                "fibonacci": fib_analyze(prices),
                "news": news_analyze(SYMBOL),
                "memory": memory_analyze(SYMBOL),
            }

            final_score = vote(scores)
            action, direction = decision(final_score)

            sl_long, sl_short, tp_long, tp_short = get_levels(candles)
            sl = sl_long if direction == "LONG" else sl_short
            tp = tp_long if direction == "LONG" else tp_short

            ai_advice = review(scores, final_score, direction, price)

            print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"💰 Price: {price}")
            print(f"⚖️ Score: {round(final_score, 2)}")
            print(f"📌 Action: {action} {direction}")
            print(f"🛑 SL: {sl} | 🎯 TP: {tp}")
            print(f"🤖 AI: {ai_advice}")

            if action == "ENTER":
                signal_id = generate_signal_id()
                save_signal(signal_id, SYMBOL, direction, final_score, price)
                send_signal(signal_id, SYMBOL, direction, final_score, price, ai_advice, scores, sl, tp)
                print(f"✅ Signal Sent! ID: {signal_id}")
            else:
                print("⏭️ No Trade")

            print("━" * 40)

        except Exception as e:
            print(f"❌ Error: {e}")

        time.sleep(SLEEP)

if __name__ == "__main__":
    main()
