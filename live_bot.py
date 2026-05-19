import os
import json
import asyncio
import time
import aiohttp
import pandas as pd
from upstash_redis.asyncio import Redis
from dotenv import load_dotenv

from features import extract_all_features
from news_filter import should_trade

load_dotenv()

SYMBOLS = ["BTC-USDT", "SOL-USDT", "DOGE-USDT", "BNB-USDT", "XRP-USDT"]
BINGX_URL = "https://open-api.bingx.com/openApi/swap/v2/quote/klines"

redis_client = Redis(
    url=os.getenv("UPSTASH_REDIS_REST_URL"),
    token=os.getenv("UPSTASH_REDIS_REST_TOKEN")
)

async def fetch_candles_async(session, symbol, interval, limit=100):
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    try:
        async with session.get(BINGX_URL, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                candles = data.get("data", [])
                if not candles:
                    return pd.DataFrame()

                df = pd.DataFrame([{
                    "timestamp": int(c.get("time", 0)),
                    "open": float(c.get("open", 0)),
                    "high": float(c.get("high", 0)),
                    "low": float(c.get("low", 0)),
                    "close": float(c.get("close", 0)),
                    "volume": float(c.get("volume", 0))
                } for c in candles])

                return df.sort_values("timestamp").reset_index(drop=True)
            return pd.DataFrame()
    except Exception as e:
        print(f" ❌ خطأ جلب {symbol} ({interval}): {e}")
        return pd.DataFrame()

async def process_symbol(session, symbol):
    try:
        redis_key = f"strategy:{symbol.replace('-USDT', '')}"
        strategy_raw = await redis_client.get(redis_key)

        if not strategy_raw:
            return

        if isinstance(strategy_raw, str):
            strategy_data = json.loads(strategy_raw)
        else:
            strategy_data = strategy_raw
           
        params = strategy_data["params"]
        tp_pct = float(strategy_data["tp_pct"])
        sl_pct = float(strategy_data["sl_pct"])

        df_1m, df_5m = await asyncio.gather(
            fetch_candles_async(session, symbol, "1m"),
            fetch_candles_async(session, symbol, "5m")
        )

        if df_1m.empty or df_5m.empty or len(df_1m) < 50:
            return

        df_features = extract_all_features({"1m": df_1m, "5m": df_5m})

        if df_features is None or df_features.empty:
            return

        last_row = df_features.iloc[-1]

        current_close = float(last_row["close"])
        current_regime = str(last_row["1m_regime"])
        current_zscore = float(last_row["1m_zscore_20"])
        current_entropy = float(last_row["1m_entropy"])
        current_fourier = float(last_row["1m_fourier"])
        current_returns = float(last_row["1m_returns"])

        signal_direction = None

        if current_regime == "ranging":
            if current_entropy <= params['entropy_max'] and current_fourier >= params['fourier_min']:
                if current_zscore >= params['z_trigger']:
                    signal_direction = "SELL"
                elif current_zscore <= -params['z_trigger']:
                    signal_direction = "BUY"

        elif current_regime == "trending":
            if current_zscore > 1.0 and current_returns > 0:
                signal_direction = "BUY"
            elif current_zscore < -1.0 and current_returns < 0:
                signal_direction = "SELL"

        if signal_direction:
            ok, reason = should_trade(symbol.split("-")[0].lower())
            if not ok:
                print(f"🚫 {symbol} — {reason}")
                return

            tp_price = current_close * (1 + tp_pct) if signal_direction == "BUY" else current_close * (1 - tp_pct)
            sl_price = current_close * (1 - sl_pct) if signal_direction == "BUY" else current_close * (1 + sl_pct)

            signal_payload = {
                "symbol": symbol,
                "direction": signal_direction,
                "price": round(current_close, 4),
                "tp1": round(tp_price, 4),
                "sl": round(sl_price, 4),
                "timestamp": int(time.time()),
                "status": "pending",
                "confidence": 75,
                "trend": current_regime.upper(),
                "rsi": 50,
                "adx": 25
            }

            await redis_client.set("signal:pending", json.dumps(signal_payload))
            print(f" 🎯 إشارة موثقة: {symbol} -> {signal_direction} | السعر: {current_close}")

    except Exception as e:
        print(f" ❌ خطأ معالجة {symbol}: {e}")

async def main():
    print("🤖 بوت المراقبة الحية غير المتزامن شغال 24/7 على السيرفر...")
    print("━" * 60)

    async with aiohttp.ClientSession() as session:
        while True:
            start_time = time.time()

            tasks = [process_symbol(session, symbol) for symbol in SYMBOLS]
            await asyncio.gather(*tasks)

            elapsed = time.time() - start_time
            sleep_time = max(0, 60 - elapsed)
            await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    asyncio.run(main())

