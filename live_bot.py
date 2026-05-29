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
from signal_scorer import compute_confidence

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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔧 HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
    if entropy < 0.4 and abs(zscore) > 0.8: return "clean"
    elif entropy > 0.7: return "noisy"
    else: return "normal"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔹 ATR VOLATILITY DETECTOR
# يحدد حالة السوق: expanding / compressing / normal
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calc_atr(df, period=14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def detect_volatility_regime(df_1m) -> tuple:
    """
    يرجع: (regime, atr_ratio)
    expanding → السوق يتوسع → فرص حقيقية
    compressing → السوق منكمش → fake chop
    normal → طبيعي
    """
    try:
        atr = calc_atr(df_1m)
        atr_mean = atr.rolling(50).mean()
        atr_ratio = float((atr / (atr_mean + 1e-9)).iloc[-1])

        if not np.isfinite(atr_ratio):
            return "normal", 1.0

        if atr_ratio > 1.3:
            return "expanding", atr_ratio
        elif atr_ratio < 0.7:
            return "compressing", atr_ratio
        else:
            return "normal", atr_ratio
    except:
        return "normal", 1.0


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
            "tp_pct": 0.0045, "sl_pct": 0.0025, "strategy_id": "default_quant_v1"
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
                print(f"⏳ {symbol} في Cooldown — باقي {(SIGNAL_COOLDOWN-elapsed)//60} دقيقة")
                return True
    except Exception as e:
        print(f"⚠️ Cooldown check error {symbol}: {e}")
    return False

async def set_signal_cooldown(symbol, multiplier=1):
    try:
        key = f"last_signal:{symbol}"
        await redis_client.set(key, str(int(time.time())))
        await redis_client.expire(key, SIGNAL_COOLDOWN * multiplier)
    except: pass

async def get_loss_streak(symbol) -> int:
    try:
        val = await redis_client.get(f"loss_streak:{symbol}")
        return int(val) if val else 0
    except: return 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔹 LAYER 1: SIGNAL ENGINE
# يحدد اتجاه الإشارة بناءً على long/short score
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def signal_engine(last_row, micro_regime, macro_htf) -> tuple:
    """
    يرجع: (signal_direction, long_prob, short_prob) أو None
    """
    zscore = float(last_row.get("1m_zscore_20", 0))
    momentum = float(last_row.get("1m_momentum_10", 0))
    volume = float(last_row.get("volume", 1))

    long_score = max(0, -zscore) + max(0, momentum)
    short_score = max(0, zscore) + max(0, -momentum)

    # volume يأثر على الاتجاه الأقوى فقط
    volume_score = np.log1p(volume)
    if momentum > 0:
        long_score *= volume_score
    else:
        short_score *= volume_score

    # regime boost
    if micro_regime == "trending":
        if macro_htf == "UP": long_score *= 1.2
        elif macro_htf == "DOWN": short_score *= 1.2

    if long_score == 0 and short_score == 0:
        return None, 0, 0

    total = long_score + short_score + 1e-9
    long_prob = long_score / total
    short_prob = short_score / total

    # neutral zone — لا قرار إذا الفرق ضعيف
    if abs(long_prob - short_prob) < 0.15:
        return None, long_prob, short_prob

    direction = "BUY" if long_prob > short_prob else "SELL"
    return direction, long_prob, short_prob


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔹 LAYER 2: SCORING ENGINE
# مصدر واحد للـ confidence
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def scoring_engine(last_row, macro_htf, macro_daily, current_zscore, min_z) -> float:
    """
    يرجع: confidence 0-100
    """
    z_strength = min(abs(current_zscore) / (min_z + 1e-9), 1.0)

    confidence = compute_confidence(last_row.to_dict(), macro_htf, macro_daily)
    confidence = float(np.clip(confidence, 0, 100))

    # debug
    print(f" 📊 [Scoring] confidence_raw={confidence:.1f} | z_strength={z_strength:.2f}")
    return confidence


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔹 LAYER 3: RISK ENGINE
# macro penalty + quality gate
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def risk_engine(confidence, final_direction, macro_htf, current_zscore, long_prob, short_prob) -> tuple:
    """
    يرجع: (confidence_final, approved)
    """
    # macro penalty ديناميكي
    if final_direction == "SHORT" and macro_htf == "UP":
        penalty = 0.6 + (0.4 * abs(current_zscore) / 2)
        confidence *= penalty
        print(f" ⚠️ [Risk] Macro penalty SHORT vs UP → {penalty:.2f}")

    if final_direction == "LONG" and macro_htf == "DOWN":
        penalty = 0.6 + (0.4 * abs(current_zscore) / 2)
        confidence *= penalty
        print(f" ⚠️ [Risk] Macro penalty LONG vs DOWN → {penalty:.2f}")

    confidence = float(np.clip(confidence, 0, 100))

    # quality gate
    if confidence < 66:
        print(f" ❌ [Risk] confidence={confidence:.1f} < 60 → رفض")
        return confidence, False

    print(f" ✅ [Risk] confidence={confidence:.1f} | long_prob={long_prob:.2f} | short_prob={short_prob:.2f} → قبول")
    return confidence, True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔹 LAYER 4: EXECUTION LAYER
# حساب SL/TP وإرسال الإشارة
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calc_sl_tp(final_direction, current_close, current_zscore, current_entropy, micro_regime, last_row, tp_pct, sl_pct):
    vol_factor = min(max(abs(current_zscore), 1.0), 2.0)
    vol_factor *= (1 + current_entropy * 0.5)
    vol_factor = min(vol_factor, 2.0)

    risk_mult = 1.2 if abs(current_zscore) > 2.0 else (0.8 if abs(current_zscore) < 1.2 else 1.0)

    if micro_regime == "ranging":
        mean_price = float(last_row.get("1m_mean_20", current_close))
        std_dev = float(last_row.get("1m_std_20", current_close * 0.0025))
        MIN_SL_PCT = 0.0065
        MIN_TP_PCT = 0.0100

        if final_direction == "LONG":
            tp_price = current_close + max(0.0, mean_price - current_close) * 0.8
            sl_price = current_close - std_dev * vol_factor
            if tp_price < current_close * (1 + MIN_TP_PCT): tp_price = current_close * (1 + MIN_TP_PCT)
            if sl_price > current_close * (1 - MIN_SL_PCT): sl_price = current_close * (1 - MIN_SL_PCT)
        else:
            tp_price = current_close - max(0.0, current_close - mean_price) * 0.8
            sl_price = current_close + std_dev * vol_factor
            if tp_price > current_close * (1 - MIN_TP_PCT): tp_price = current_close * (1 - MIN_TP_PCT)
            if sl_price < current_close * (1 + MIN_SL_PCT): sl_price = current_close * (1 + MIN_SL_PCT)
    else:
        adaptive_tp = min(tp_pct * vol_factor * risk_mult, 0.0065)
        adaptive_sl = min(sl_pct * vol_factor * risk_mult, 0.0045)

        if final_direction == "LONG":
            tp_price = current_close * (1 + adaptive_tp)
            sl_price = current_close * (1 - adaptive_sl)
        else:
            tp_price = current_close * (1 - adaptive_tp)
            sl_price = current_close * (1 + adaptive_sl)

    return tp_price, sl_price


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔁 MAIN PROCESS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
        current_entropy= float(last_row["1m_entropy"])
        current_fourier= float(last_row["1m_fourier"])

        if not all(np.isfinite(v) for v in [current_zscore, current_entropy, current_fourier]):
            return

        if micro_regime == "volatile":
            print(f"⚡ {symbol} — تجاهل السوق المتقلب")
            return

        market_state = detect_market_state(current_entropy, current_zscore, macro_htf)

        if market_state == "clean": min_z = 0.3 if micro_regime == "ranging" else 0.5
        elif market_state == "noisy": min_z = 0.5 if micro_regime == "ranging" else 0.8
        else: min_z = 0.35 if micro_regime == "ranging" else 0.65

        # ─── ATR VOLATILITY DETECTOR ───
        print(f"\n{'─'*50}")
        print(f"🔍 {symbol} | H4:{macro_htf} | Daily:{macro_daily} | Regime:{micro_regime.upper()}")
        vol_regime, atr_ratio = detect_volatility_regime(df_1m)
        print(f" 📈 [ATR] {vol_regime.upper()} | ratio={atr_ratio:.2f}")

        if vol_regime == "compressing":
            print(f" ⏸️ [ATR] {symbol} — سوق منكمش → تجاهل")
            return

        # ─── NOISE DAMPENING LAYER ───
        noise_level = current_entropy
        if noise_level > 0.85:
            last_row = last_row.copy()
            last_row["1m_momentum_10"] = float(last_row.get("1m_momentum_10", 0)) * 0.4
            last_row["1m_zscore_20"] = float(last_row.get("1m_zscore_20", 0)) * 0.5
            print(f" 🔇 [Noise] entropy={noise_level:.2f} → dampening 50%")
        elif noise_level > 0.75:
            last_row = last_row.copy()
            last_row["1m_momentum_10"] = float(last_row.get("1m_momentum_10", 0)) * 0.6
            last_row["1m_zscore_20"] = float(last_row.get("1m_zscore_20", 0)) * 0.7
            print(f" 🔇 [Noise] entropy={noise_level:.2f} → dampening 30%")

        # ─── LAYER 1: SIGNAL ENGINE ───
        raw_direction, long_prob, short_prob = signal_engine(last_row, micro_regime, macro_htf)
        if raw_direction is None:
            return

        final_direction = "LONG" if raw_direction == "BUY" else "SHORT"

        # ─── LAYER 2: SCORING ENGINE ───
        confidence = scoring_engine(last_row, macro_htf, macro_daily, current_zscore, min_z)

        # ATR boost: إشارة في سوق متوسع = أقوى
        if vol_regime == "expanding":
            atr_boost = min(1.0 + (atr_ratio - 1.3) * 0.3, 1.2)
            confidence = min(confidence * atr_boost, 100)
            print(f" 🚀 [ATR Boost] confidence × {atr_boost:.2f} → {confidence:.1f}")

        # ─── LAYER 3: RISK ENGINE ───
        confidence, approved = risk_engine(confidence, final_direction, macro_htf, current_zscore, long_prob, short_prob)
        if not approved:
            return

        # news + memory filters
        ok, reason = should_trade(symbol.split("-")[0].lower())
        if not ok:
            print(f"🚫 {symbol} — {reason}")
            return

        try:
            blocked = await should_block_signal(redis_client, symbol, final_direction, micro_regime, macro_htf.lower())
            if blocked:
                print(f"🧠 [Memory Blocked] {symbol}")
                return
        except Exception as e:
            print(f"⚠️ Memory check failed: {e}")

        # ─── LAYER 4: EXECUTION ───
        strategy_data = await get_best_live_strategy_async(symbol, micro_regime)
        if "params" not in strategy_data or not isinstance(strategy_data.get("params"), dict):
            return

        tp_price, sl_price = calc_sl_tp(
            final_direction, current_close, current_zscore, current_entropy,
            micro_regime, last_row,
            float(strategy_data["tp_pct"]),
            float(strategy_data["sl_pct"])
        )

        precision = get_price_precision(symbol)
        strategy_id = strategy_data.get("strategy_id", "default_quant_v1")
        z_trigger = strategy_data["params"].get("z_trigger", 1.5)
        entry_quality = "early" if abs(current_zscore) >= z_trigger + 0.5 else ("late" if abs(current_zscore) <= z_trigger - 0.2 else "middle")

        signal_id = f"{symbol.replace('-', '')}-{int(time.time())}"
        groq_comment = ""
        llama_comment= ""

        if AI_ENABLED:
            try:
                base_score = min(confidence / 100.0, 1.0)
                ai_verdict, ai_reason, groq_comment, llama_comment = ai_review(
                    row=last_row.to_dict(), final_score=base_score,
                    direction=final_direction, price=current_close, pattern_stats=None
                )
                print(f"🧠 [AI] {symbol} → {ai_reason}")
            except Exception as e:
                print(f"⚠️ AI Review failed: {e}")

        confidence_pct = round(confidence, 1)

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
            "confidence": confidence_pct,
            "groq_reason": groq_comment,
            "or_reason": llama_comment,
            "quant_metrics": {
                "zscore": round(current_zscore, 2),
                "entropy": round(current_entropy, 2),
                "fourier": round(current_fourier, 2),
                "long_prob": round(long_prob, 3),
                "short_prob": round(short_prob, 3),
                "atr_regime": vol_regime,
                "atr_ratio": round(atr_ratio, 3)
            }
        }

        await redis_client.set(f"signal:pending:{symbol}", json.dumps(signal_payload))

        loss_streak = await get_loss_streak(symbol)
        await set_signal_cooldown(symbol, multiplier=min(loss_streak + 1, 3))
        await save_signal_memory(redis_client, signal_id, signal_payload)

        print(f"🎯 {symbol} → {final_direction} | Confidence: {confidence_pct}% | long_prob={long_prob:.2f} | short_prob={short_prob:.2f} | Regime: {micro_regime.upper()} | H4: {macro_htf}")

    except Exception as e:
        print(f"❌ خطأ معالجة {symbol}: {e}")


async def main():
    print("=" * 65)
    print("🤖 ASYNC LIVE MONITOR BOT - REFACTORED ARCHITECTURE")
    print(" Layer 1: Signal Engine")
    print(" Layer 2: Scoring Engine")
    print(" Layer 3: Risk Engine")
    print(" Layer 4: Execution Layer")
    print("=" * 65)

    async with aiohttp.ClientSession() as session:
        while True:
            start_time = time.time()
            tasks = [process_symbol(session, symbol) for symbol in SYMBOLS]
            await asyncio.gather(*tasks)
            sleep_time = max(45, min(75, 60 + int(np.random.randint(-10, 10))))
            await asyncio.sleep(sleep_time)

if __name__ == "__main__":
    asyncio.run(main())

