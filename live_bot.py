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
SIGNAL_COOLDOWN = 900 # 15 دقيقة بين كل إشارة لنفس العملة

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

async def get_best_live_strategy_async(symbol, market_regime):
    regime_upper = str(market_regime).upper()
    coin_clean = symbol.replace('-USDT', '')
    
    slots_keys = [
        f"strategy_best_1:{coin_clean}:{regime_upper}",
        f"strategy_best_2:{coin_clean}:{regime_upper}",
        f"strategy_best_3:{coin_clean}:{regime_upper}"
    ]
    
    strategies = []
    for key in slots_keys:
        raw_data = await redis_client.get(key)
        if raw_data:
            if isinstance(raw_data, str):
                strategies.append(json.loads(raw_data))
            else:
                strategies.append(raw_data)
                
    if not strategies:
        return {
            "params": {"entropy_max": 4.0, "fourier_min": 5.0, "z_trigger": 1.5},
            "tp_pct": 0.0045,
            "sl_pct": 0.0025
        }
        
    strategies.sort(key=lambda x: (x.get("live_score", 100.0), x.get("fitness", 0.0)), reverse=True)
    return strategies[0]

async def is_in_signal_cooldown(symbol) -> bool:
    """تحقق إذا العملة في فترة Cooldown للإشارات"""
    try:
        key = f"last_signal:{symbol}"
        last_time = await redis_client.get(key)
        if last_time:
            elapsed = int(time.time()) - int(str(last_time))
            if elapsed < SIGNAL_COOLDOWN:
                return True
    except:
        pass
    return False

async def set_signal_cooldown(symbol):
    """حفظ وقت آخر إشارة للعملة"""
    try:
        key = f"last_signal:{symbol}"
        await redis_client.set(key, str(int(time.time())))
    except:
        pass

async def process_symbol(session, symbol):
    try:
        # تحقق من Cooldown قبل أي عملية
        if await is_in_signal_cooldown(symbol):
            return

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
        current_regime = str(last_row["1m_regime"]).strip().lower()
        current_zscore = float(last_row["1m_zscore_20"])
        current_entropy = float(last_row["1m_entropy"])
        current_fourier = float(last_row["1m_fourier"])
        current_returns = float(last_row["1m_returns"])

        strategy_data = await get_best_live_strategy_async(symbol, current_regime)
        
        params = strategy_data["params"]
        tp_pct = float(strategy_data["tp_pct"])
        sl_pct = float(strategy_data["sl_pct"])

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

            await redis_client.set(f"signal:pending:{symbol}", json.dumps(signal_payload))
            await set_signal_cooldown(symbol) # حفظ Cooldown بعد الإرسال
            print(f" 🎯 إشارة: {symbol} -> {signal_direction} | السعر: {current_close} | {current_regime.upper()}")

    except Exception as e:
        print(f" ❌ خطأ معالجة {symbol}: {e}")

async def main():
    print("=" * 65)
    print("🤖 ASYNC LIVE MONITOR BOT - EVOLUTIONARY OMNI VERSION")
    print("=" * 65)

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

