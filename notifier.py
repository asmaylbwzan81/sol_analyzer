from upstash_redis import Redis
import os
import json

UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")

def send_signal(signal_id, symbol, direction, score, price, ai_advice, scores, sl, tp):
    try:
        r = Redis(url=UPSTASH_URL, token=UPSTASH_TOKEN)

        emoji = "📈" if direction == "LONG" else "📉"
        confidence = int(score * 100)

        msg = f"""🤖 SMART ANALYZER SIGNAL
━━━━━━━━━━━━━━
🆔 ID: {signal_id}
🪙 Symbol: {symbol}
{emoji} Direction: {direction}
💪 Confidence: {confidence}/100
💰 Entry: {price}
🛑 SL: {sl}
🎯 TP: {tp}

━━━━━━━━━━━━━━
📊 Strategies:
• RSI: {round(scores.get('rsi', 0.5), 2)}
• MACD: {round(scores.get('macd', 0.5), 2)}
• EMA: {round(scores.get('ema', 0.5), 2)}
• Bollinger: {round(scores.get('bollinger', 0.5), 2)}
• Volume: {round(scores.get('volume', 0.5), 2)}
• Momentum: {round(scores.get('momentum', 0.5), 2)}
• S/R: {round(scores.get('sr', 0.5), 2)}
• Pattern: {round(scores.get('pattern', 0.5), 2)}
• Stochastic: {round(scores.get('stochastic', 0.5), 2)}
• VWAP: {round(scores.get('vwap', 0.5), 2)}
• ADX: {round(scores.get('adx', 0.5), 2)}
• Fibonacci: {round(scores.get('fibonacci', 0.5), 2)}
• News: {round(scores.get('news', 0.5), 2)}
• Memory: {round(scores.get('memory', 0.5), 2)}

━━━━━━━━━━━━━━
🤖 AI Review:
{ai_advice}"""

        r.lpush("signals", msg)
        print(f"✅ Signal sent to Redis: {signal_id}")

    except Exception as e:
        print(f"❌ Redis Error: {e}")
