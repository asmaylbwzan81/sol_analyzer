
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
from memory import save_signal_memory, should_block_signal

# ✅ AI Advisors (Observer Mode)
try:
    from ai_reviewer import review as ai_review, init_db as ai_init_db
    ai_init_db()
    AI_ENABLED = True
except Exception as e:
    print(f"⚠️ AI Reviewer غير متاح: {e}")
    AI_ENABLED = False

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
        if df_4h is None or df_4h.empty or len(df_4h) < 20: return "NEUTRAL"
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
        if df_1d is None or df_1d.empty or len(df_1d) < 10: return "NEUTRAL"
        y = df_1d["close"].iloc[-10:].values
        x = np.arange(len(y))
        slope, _ = np.polyfit(x, y, 1)
        normalized_slope = slope / y.mean()
        if normalized_slope > 0.0003: return "UP"
        elif normalized_slope < -0.0003: return "DOWN"
        return "NEUTRAL"
    except:
        return "NEUTRAL"

def detect_market_state(entropy: float, zscore: float, macro_htf: str) -> str:
    if entropy < 0.4 and abs(zscore) > 0.8:
        return "clean"
    elif entropy > 0.7:
        return "noisy"
    else:
        return "normal"

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
            if isinstance(raw_data, str): strategies.append(json.loads(raw_data))
            else: strategies.append(raw_data)
    if not strategies:
        return {
            "params": {"entropy_max": 0.6, "fourier_min": 0.04, "z_trigger": 1.5},
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

async def set_signal_cooldown(symbol, multiplier=1):
    try:
        key = f"last_signal:{symbol}"
        cooldown = SIGNAL_COOLDOWN * multiplier
        await redis_client.set(key, str(int(time.time())))
        await redis_client.expire(key, cooldown)
    except:
        pass

async def get_loss_streak(symbol) -> int:
    try:
        key = f"loss_streak:{symbol}"
        val = await redis_client.get(key)
        return int(val) if val else 0
    except:
        return 0

async def update_loss_streak(symbol, win: bool):
    try:
        key = f"loss_streak:{symbol}"
        if win:
            await redis_client.set(key, "0")
        else:
            streak = await get_loss_streak(symbol)
            await redis_client.set(key, str(streak + 1))
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

        macro_htf = get_htf_trend(df_4h)
        macro_daily = get_daily_trend(df_1d)

        df_features = extract_all_features({"1m": df_1m, "5m": df_5m})
        if df_features is None or df_features.empty:
            return

        last_row = df_features.iloc[-1]
        current_close = float(last_row["close"])
        micro_regime = str(last_row["1m_regime"]).strip().lower()
        current_zscore = float(last_row["1m_zscore_20"])
        current_entropy = float(last_row["1m_entropy"])
        current_fourier = float(last_row["1m_fourier"])

        if not np.isfinite(current_zscore): return
        if not np.isfinite(current_entropy): return
        if not np.isfinite(current_fourier): return

        if micro_regime == "volatile":
            print(f"⚡ {symbol} — تجاهل السوق المتقلب")
            return

        market_state = detect_market_state(current_entropy, current_zscore, macro_htf)

        if market_state == "clean":
            min_z_ranging = 0.3
            min_z_trending = 0.5
            confidence_threshold = 0.60
        elif market_state == "noisy":
            min_z_ranging = 0.5
            min_z_trending = 0.8
            confidence_threshold = 0.85
        else:
            min_z_ranging = 0.35
            min_z_trending = 0.65
            confidence_threshold = 0.75

        if micro_regime == "ranging":
            min_z = min_z_ranging
        else:
            min_z = min_z_trending

        if abs(current_zscore) < min_z:
            return

        confidence = abs(current_zscore) * (2 - current_entropy)
        if confidence < confidence_threshold:
            return

        strategy_data = await get_best_live_strategy_async(symbol, micro_regime)

        if "params" not in strategy_data:
            return
        if not isinstance(strategy_data.get("params"), dict):
            return

        params = strategy_data["params"]
        tp_pct = float(strategy_data["tp_pct"])
        sl_pct = float(strategy_data["sl_pct"])
        strategy_id = strategy_data.get("strategy_id", "gen_plan_3")

        trend_confirmed = (macro_daily == macro_htf) and macro_htf != "NEUTRAL"

        signal_direction = None

        if micro_regime == "ranging":
            if current_entropy <= params['entropy_max'] and current_fourier >= params['fourier_min']:
                if current_zscore >= params['z_trigger']:
                    signal_direction = "SELL"
                elif current_zscore <= -params['z_trigger']:
                    signal_direction = "BUY"

        elif micro_regime == "trending":
            if market_state == "clean":
                trend_ok = macro_htf != "NEUTRAL"
            else:
                trend_ok = trend_confirmed

            if not trend_ok:
                return
            if macro_htf == "UP" and current_zscore <= -1.0:
                signal_direction = "BUY"
            elif macro_htf == "DOWN" and current_zscore >= 1.0:
                signal_direction = "SELL"

        if signal_direction:
            final_direction = "LONG" if signal_direction == "BUY" else "SHORT"

            if final_direction == "SHORT" and (macro_htf == "UP" or macro_daily == "UP"):
                print(f"🛑 [Macro Shield] {symbol} — رفض SHORT ⬆️")
                return

            if final_direction == "LONG" and (macro_htf == "DOWN" or macro_daily == "DOWN"):
                print(f"🛑 [Macro Shield] {symbol} — رفض LONG ⬇️")
                return

            ok, reason = should_trade(symbol.split("-")[0].lower())
            if not ok:
                print(f"🚫 {symbol} — {reason}")
                return

            try:
                blocked = await should_block_signal(redis_client, symbol, final_direction, micro_regime, macro_htf.lower())
                if blocked:
                    print(f"🧠 [Memory Blocked] {symbol} — حظر الإشارة.")
                    return
            except Exception as e:
                print(f"⚠️ Memory check failed: {e}")

            precision = get_price_precision(symbol)

            if abs(current_zscore) >= params.get('z_trigger', 1.5) + 0.5:
                entry_quality = "early"
            elif abs(current_zscore) <= params.get('z_trigger', 1.5) - 0.2:
                entry_quality = "late"
            else:
                entry_quality = "middle"

            vol_factor = min(max(abs(current_zscore), 1.0), 2.0)
            vol_factor *= (1 + current_entropy * 0.5)
            vol_factor = min(vol_factor, 2.0)

            if abs(current_zscore) > 2.0:
                risk_mult = 1.2
            elif abs(current_zscore) < 1.2:
                risk_mult = 0.8
            else:
                risk_mult = 1.0

            if micro_regime == "ranging":
                mean_price = float(last_row.get("1m_mean_20", current_close))
                std_dev = float(last_row.get("1m_std_20", current_close * 0.0025))
                MIN_SL_PCT = 0.0065
                MIN_TP_PCT = 0.0100

                if final_direction == "LONG":
                    distance_to_mean = max(0.0, mean_price - current_close)
                    tp_price = current_close + (distance_to_mean * 0.8)
                    sl_price = current_close - (std_dev * vol_factor)
                    if tp_price < current_close * (1 + MIN_TP_PCT): tp_price = current_close * (1 + MIN_TP_PCT)
                    if sl_price > current_close * (1 - MIN_SL_PCT): sl_price = current_close * (1 - MIN_SL_PCT)
                else:
                    distance_to_mean = max(0.0, current_close - mean_price)
                    tp_price = current_close - (distance_to_mean * 0.8)
                    sl_price = current_close + (std_dev * vol_factor)
                    if tp_price > current_close * (1 - MIN_TP_PCT): tp_price = current_close * (1 - MIN_TP_PCT)
                    if sl_price < current_close * (1 + MIN_SL_PCT): sl_price = current_close * (1 + MIN_SL_PCT)
            else:
                adaptive_tp_pct = tp_pct * vol_factor * risk_mult
                adaptive_sl_pct = sl_pct * vol_factor * risk_mult
                adaptive_tp_pct = min(adaptive_tp_pct, 0.0065)
                adaptive_sl_pct = min(adaptive_sl_pct, 0.0045)

                if final_direction == "LONG":
                    tp_price = current_close * (1 + adaptive_tp_pct)
                    sl_price = current_close * (1 - adaptive_sl_pct)
                else:
                    tp_price = current_close * (1 - adaptive_tp_pct)
                    sl_price = current_close * (1 + adaptive_sl_pct)

            signal_id = f"{symbol.replace('-', '')}-{int(time.time())}"

            groq_comment = ""
            llama_comment = ""
            ai_final_confidence = confidence
            if AI_ENABLED:
                try:
                    base_score = min(confidence / 4.0, 1.0)
                    ai_verdict, ai_reason, groq_comment, llama_comment = ai_review(
                        row=last_row.to_dict(),
                        final_score=base_score,
                        direction=final_direction,
                        price=current_close,
                        pattern_stats=None
                    )
                    print(f"🧠 [AI Advisors] {symbol} → {ai_reason}")
                except Exception as e:
                    print(f"⚠️ AI Review failed: {e}")

            # ✅ إصلاح: تحويل confidence من نظام 0-4 إلى 0-100
            confidence_pct = round(min(confidence / 4.0, 1.0) * 100, 1)

            signal_payload = {
                "signal_id": signal_id,
                "symbol": symbol,
                "direction": final_direction,
                "price": round(current_close, precision),
                "tp1": round(tp_price, precision),
                "sl": round(sl_price, precision),
                "timestamp": int(time.time()),
                "status": "pending",
                "market_regime": micro_regime,
                "htf_trend": macro_htf.lower(),
                "daily_trend": macro_daily.lower(),
                "entry_quality": entry_quality,
                "market_state": market_state,
                "strategy_id": strategy_id,
                "confidence": confidence_pct, # ✅ هلق بين 0-100
                "groq_reason": groq_comment,
                "or_reason": llama_comment,
                "quant_metrics": {
                    "zscore": round(current_zscore, 2),
                    "entropy": round(current_entropy, 2),
                    "fourier": round(current_fourier, 2)
                }
            }

            await redis_client.set(f"signal:pending:{symbol}", json.dumps(signal_payload))

            loss_streak = await get_loss_streak(symbol)
            cooldown_mult = min(loss_streak + 1, 3)
            await set_signal_cooldown(symbol, multiplier=cooldown_mult)

            await save_signal_memory(redis_client, signal_id, signal_payload)
            print(f"🎯 إشارة: {symbol} -> {final_direction} | Confidence: {confidence_pct}% | Micro: {micro_regime.upper()} | State: {market_state.upper()} | H4: {macro_htf} | ID: {signal_id}")

    except Exception as e:
        print(f"❌ خطأ معالجة {symbol}: {e}")

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
            sleep_time = max(45, min(75, 60 + int(np.random.randint(-10, 10))))
            await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    asyncio.run(main())

