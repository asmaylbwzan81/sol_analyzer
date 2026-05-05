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
from notifier import send_signal

SYMBOLS = [
    "BTC", "ETH", "SOL", "XRP", "DOGE",
    "BNB", "ADA", "LINK", "TON", "AVAX"
]

INTERVALS = ["1d", "4h", "1h"]
SLEEP = 600

def generate_signal_id():
    return str(uuid.uuid4())[:8].upper()

def analyze_symbol(symbol, interval):
    try:
        prices = get_klines(symbol, interval)
        candles = get_candles(symbol, interval)
        price = prices[-1]

        rsi_s = rsi_analyze(prices)
        macd_s = macd_analyze(prices)
        ema_s = ema_analyze(prices)
        boll_s = bollinger_analyze(prices)
        vol_s = volume_analyze(candles)
        mom_s = momentum_analyze(prices)
        sr_s = sr_analyze(prices)
        pat_s = pattern_analyze(candles)
        stoch_s = stochastic_analyze(candles)
        vwap_s = vwap_analyze(candles)
        adx_s = adx_analyze(candles)
        fib_s = fib_analyze(prices)
        news_s = news_analyze(symbol)
        mem_s = memory_analyze(symbol)

        print(f"DEBUG {symbol} {interval}: rsi={rsi_s} macd={macd_s} ema={ema_s} boll={boll_s}")
        print(f"DEBUG {symbol} {interval}: vol={vol_s} mom={mom_s} sr={sr_s} pat={pat_s}")
        print(f"DEBUG {symbol} {interval}: stoch={stoch_s} vwap={vwap_s} adx={adx_s} fib={fib_s}")
        print(f"DEBUG {symbol} {interval}: news={news_s} mem={mem_s}")

        scores = {
            "rsi": rsi_s,
            "macd": macd_s,
            "ema": ema_s,
            "bollinger": boll_s,
            "volume": vol_s,
            "momentum": mom_s,
            "sr": sr_s,
            "pattern": pat_s,
            "stochastic": stoch_s,
            "vwap": vwap_s,
            "adx": adx_s,
            "fibonacci": fib_s,
            "news": news_s,
            "memory": mem_s,
        }

        final_score = vote(scores)
        print(f"DEBUG final_score={final_score} type={type(final_score)}")

        action, direction = decision(final_score)
        print(f"DEBUG action={action} direction={direction}")

        sl_long, sl_short, tp_long, tp_short = get_levels(candles)
        sl = sl_long if str(direction) == "LONG" else sl_short
        tp = tp_long if str(direction) == "LONG" else tp_short

        ai_advice = review(scores, final_score, direction, price)

        print(f"\n🪙 {symbol} | ⏱ {interval}")
        print(f"💰 Price: {price} | ⚖️ Score: {round(final_score, 2)}")
        print(f"📌 Action: {action} {direction}")
        print(f"🛑 SL: {sl} | 🎯 TP: {tp}")

        if action == "ENTER":
            signal_id = generate_signal_id()
            save_signal(signal_id, symbol, direction, final_score, price)
            send_signal(signal_id, symbol, direction, final_score, price, ai_advice, scores, sl, tp)
            print(f"✅ Signal Sent! ID: {signal_id}")
        else:
            print("⏭️ No Trade")

    except Exception as e:
        print(f"❌ Error {symbol} {interval}: {e}")
        traceback.print_exc()

def main():
    print("🚀 Smart Analyzer Bot Started")
    print(f"📊 Symbols: {len(SYMBOLS)} | Intervals: {INTERVALS}")
    print("━" * 40)

    while True:
        print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        for symbol in SYMBOLS:
            for interval in INTERVALS:
                analyze_symbol(symbol, interval)
                time.sleep(1)
        print("━" * 40)
        time.sleep(SLEEP)

if __name__ == "__main__":
    main()
