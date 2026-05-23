import os
import json
import asyncio
import time
import aiohttp
import pandas as pd
import numpy as np
from upstash_redis.asyncio import Redis
from dotenv import load_dotenv

from features import extract_all_features
from news_filter import should_trade

load_dotenv()

SYMBOLS = ["BTC-USDT", "SOL-USDT", "DOGE-USDT", "BNB-USDT", "XRP-USDT"]
BINGX_URL = "https://open-api.bingx.com/openApi/swap/v2/quote/klines"
SIGNAL_COOLDOWN = 900

redis_client = Redis(
    url=os.getenv("UPSTASH_REDIS_REST_URL"),
    token=os.getenv("UPSTASH_REDIS_REST_TOKEN")
)

def get_price_precision(symbol: str) -> int:
    if "BTC" in symbol: return 1
    elif "SOL" in symbol or "BNB" in symbol: return 2
    elif "XRP" in symbol: return 4
    elif "DOGE" in symbol: return 5
    return 4

async def fetch_candles_async(session, symbol, interval, limit=100):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        async with session.get(BINGX_URL, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                candles = data.get("data", [])
                if not candles: return pd.DataFrame()

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
        print(f"❌ خطأ جلب {symbol} ({interval}): {e}")
        return pd.DataFrame()

def get_htf_trend(df_4h: pd.DataFrame) -> str:
    try:
        if df_4h is None or df_4h.empty or len(df_4h) < 20:
            return "NEUTRAL"
        y = df_4h["close"].iloc[-20:].values
        x = np.arange(len(y))
        slope, _ = np.polyfit(x, y, 1)
        normalized_slope = slope / y.mean()
        if normalized_slope > 0.0005: return "UP"
        elif normalized_slope < -0.0005: return "DOWN"
        return "NEUTRAL"
    except:
        return "NEUTRAL"

def get_daily_trend(df_1d: pd.DataFrame) -> str:
    try:
        if df_1d is None or df_1d.empty or len(df_1d) < 10:
            return "NEUTRAL"
        y = df_1d["close"].iloc[-10:].values
        x = np.arange(len(y))
        slope, _ = np.polyfit(x, y, 1)
        normalized_slope = slope / y.mean()
        if normalized_slope > 0.0003: return "UP"
        elif normalized_slope < -0.0003: return "DOWN"
        return "NEUTRAL"
    except:
        return "NEUTRAL"

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
            "sl_pct": 0.0025,
            "strategy_id": "default_quant_v1"
        }
    strategies.sort(key=lambda x: (x.get("live_score", 100.0), x.get("fitness", 0.0)), reverse=True)
    return strategies[0]

async def is_in_signal_cooldown(symbol) -> bool:
    try:
        key = f"last_signal:{symbol}"
        last_time = await redis_client.get(key)
        if last_time:
            last_time_str = last_time.decode('utf-8') if isinstance(last_time, bytes) else str(last_time)
            elapsed = int(time.time()) - int(last_time_str)
            if elapsed < SIGNAL_COOLDOWN:
                remaining = (SIGNAL_COOLDOWN - elapsed) // 60
                print(f"⏳ {symbol} في Cooldown — باقي {remaining} دقيقة")
                return True
    except Exception as e:
        print(f"⚠️ تنبيه فحص الكول داون لـ {symbol}: {e}")
    return False

async def set_signal_cooldown(symbol):
    try:
        key = f"last_signal:{symbol}"
        await redis_client.set(key, str(int(time.time())))
    except:
        pass

async def process_symbol(session, symbol):
    try:
        if await is_in_signal_cooldown(symbol):
            return

        df_1m, df_5m, df_4h, df_1d = await asyncio.gather(
            fetch_candles_async(session, symbol, "1m"),
            fetch_candles_async(session, symbol, "5m"),
            fetch_candles_async(session, symbol, "4h", limit=50),
            fetch_candles_async(session, symbol, "1d", limit=30)
        )

        if df_1m.empty or df_5m.empty or len(df_1m) < 50:
            return

        htf_trend = get_htf_trend(df_4h)
        daily_trend = get_daily_trend(df_1d)

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
        strategy_id = strategy_data.get("strategy_id", "gen_plan_3")

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

            final_direction = "LONG" if signal_direction == "BUY" else "SHORT"

            if final_direction == "SHORT" and htf_trend == "UP":
                print(f"🛑 [H4 Filter] {symbol} — رفض SHORT لأن H4 صاعد ⬆️")
                return
            if final_direction == "LONG" and htf_trend == "DOWN":
                print(f"🛑 [H4 Filter] {symbol} — رفض LONG لأن H4 نازل ⬇️")
                return

            if final_direction == "SHORT" and daily_trend == "UP":
                print(f"🛑 [Daily Filter] {symbol} — رفض SHORT لأن Daily صاعد ⬆️")
                return
            if final_direction == "LONG" and daily_trend == "DOWN":
                print(f"🛑 [Daily Filter] {symbol} — رفض LONG لأن Daily نازل ⬇️")
                return

            precision = get_price_precision(symbol)

            if current_regime == "ranging":
                mean_price = float(last_row.get("1m_mean_20", current_close))
                std_dev = float(last_row.get("1m_std_20", current_close * 0.0025))
                volatility_factor = max(1.0, abs(current_zscore))
                MIN_SL_PCT = 0.0065
                MIN_TP_PCT = 0.0100

                if final_direction == "LONG":
                    distance_to_mean = max(0.0, mean_price - current_close)
                    tp_price = current_close + (distance_to_mean * 0.8)
                    sl_price = current_close - (std_dev * volatility_factor)
                    if tp_price < current_close * (1 + MIN_TP_PCT): tp_price = current_close * (1 + MIN_TP_PCT)
                    if sl_price > current_close * (1 - MIN_SL_PCT): sl_price = current_close * (1 - MIN_SL_PCT)
                else:
                    distance_to_mean = max(0.0, current_close - mean_price)
                    tp_price = current_close - (distance_to_mean * 0.8)
                    sl_price = current_close + (std_dev * volatility_factor)
                    if tp_price > current_close * (1 - MIN_TP_PCT): tp_price = current_close * (1 - MIN_TP_PCT)
                    if sl_price < current_close * (1 + MIN_SL_PCT): sl_price = current_close * (1 + MIN_SL_PCT)

                print(f"📊 [Quant Mode Active] أهداف تكيفية إحصائية لحالة التذبذب.")

            else:
                volatility_factor = max(1.0, abs(current_zscore))
                adaptive_sl_pct = max(0.0065, sl_pct * volatility_factor)
                adaptive_tp_pct = max(0.0100, tp_pct * volatility_factor)

                if final_direction == "LONG":
                    tp_price = current_close * (1 + adaptive_tp_pct)
                    sl_price = current_close * (1 - adaptive_sl_pct)
                else:
                    tp_price = current_close * (1 - adaptive_tp_pct)
                    sl_price = current_close * (1 + adaptive_sl_pct)

                print(f"📈 [Trend Mode Active] أهداف مرنة مبنية على الزخم.")

            if abs(current_zscore) >= params.get('z_trigger', 1.5) + 0.5:
                entry_quality = "early"
            elif abs(current_zscore) <= params.get('z_trigger', 1.5) - 0.2:
                entry_quality = "late"
            else:
                entry_quality = "middle"

            # ✅ التعديل الوحيد — إضافة signal_id
            signal_id = f"{symbol.replace('-', '')}-{int(time.time())}"

            signal_payload = {
                "signal_id": signal_id, # ✅
                "symbol": symbol,
                "direction": final_direction,
                "price": round(current_close, precision),
                "tp1": round(tp_price, precision),
                "sl": round(sl_price, precision),
                "timestamp": int(time.time()),
                "status": "pending",
                "market_regime": current_regime,
                "htf_trend": htf_trend.lower(),
                "daily_trend": daily_trend.lower(),
                "entry_quality": entry_quality,
                "strategy_id": strategy_id,
                "quant_metrics": {
                    "zscore": round(current_zscore, 2),
                    "entropy": round(current_entropy, 2),
                    "fourier": round(current_fourier, 2)
                }
            }

            await redis_client.set(f"signal:pending:{symbol}", json.dumps(signal_payload))
            await set_signal_cooldown(symbol)
            print(f"🎯 إشارة: {symbol} -> {final_direction} | {current_regime.upper()} | H4: {htf_trend} | Daily: {daily_trend} | ID: {signal_id}")

    except Exception as e:
        print(f"❌ خطأ معالجة {symbol}: {e}")

async def main():
    print("=" * 65)
    print("🤖 ASYNC LIVE MONITOR BOT - CLEAN QUANT VERSION")
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
