import time
import threading
import traceback
import json
import uuid
from datetime import datetime

from data_engine import init_all_timeframes, load_all_timeframes, count_candles
from features import extract_all_features
from evolution import evolve
from strategy_generator import print_strategy, apply_strategy
from redis_store import load_best
from news_filter import should_trade
import os
from upstash_redis import Redis

# ══════════════════════════════
# Config
# ══════════════════════════════
SYMBOL = "SOL-USDT"
SYMBOL_CLEAN = "SOL"
MAX_OPEN_TRADES = 5
CAPITAL_PER_TRADE = 10
LEVERAGE = 3
EVOLVE_INTERVAL = 60

TP_PCT = 0.008 # 0.8%
SL_PCT = 0.004 # 0.4%
MIN_CONFIDENCE = 65

ERROR_LOG_FILE = "error_log.jsonl"

TARGET_CANDLES = {
    "1m": 50000,
    "5m": 20000,
    "15m": 10000,
}

# ══════════════════════════════
# Redis — upstash_redis مثل بوت التنفيذ
# ══════════════════════════════
redis_client = Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL", ""),
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
)

def redis_set(key, value):
    try:
        redis_client.set(key, json.dumps(value))
    except Exception as e:
        print(f"⚠️ Redis set error: {e}")

def redis_get(key):
    try:
        result = redis_client.get(key)
        if result:
            return json.loads(str(result))
    except:
        pass
    return None

# ══════════════════════════════
# State
# ══════════════════════════════
open_trades = []
best_strategy = None
lock = threading.Lock()


# ══════════════════════════════
# Error tracker
# ══════════════════════════════
def log_error(context, error):
    err_data = {
        "time": datetime.now().isoformat(),
        "context": context,
        "error": str(error),
        "traceback": traceback.format_exc()
    }
    print(f"❌ [{context}] {error}")
    try:
        with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(err_data, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"⚠️ Failed to write error log: {e}")


# ══════════════════════════════
# حساب Confidence
# ══════════════════════════════
def calc_confidence(row, direction):
    score = 50

    try:
        zscore = row.get("1m_zscore", 0)
        momentum = row.get("1m_momentum_pct", 0)
        entropy_val = row.get("1m_entropy", 1)
        vol_ratio = row.get("1m_vol_ratio", 1)
        hist_prob = row.get("1m_hist_prob_up", 0.5)
        autocorr = row.get("1m_autocorr_1", 0)

        if direction == "LONG":
            if zscore < -1.5: score += 10
            if momentum > 0: score += 10
            if hist_prob > 0.55: score += 10
            if autocorr > 0.1: score += 5
        else:
            if zscore > 1.5: score += 10
            if momentum < 0: score += 10
            if hist_prob < 0.45: score += 10
            if autocorr < -0.1: score += 5

        if entropy_val < 1.5: score += 5
        if vol_ratio < 1.2: score += 5
        if vol_ratio > 2.0: score -= 10

    except Exception as e:
        print(f"⚠️ خطأ حساب Confidence: {e}")

    return min(max(score, 0), 100)


# ══════════════════════════════
# إرسال الإشارة على Redis
# ══════════════════════════════
def send_signal_to_redis(direction, price, row):
    try:
        if direction == "LONG":
            tp1 = round(price * (1 + TP_PCT), 6)
            sl = round(price * (1 - SL_PCT), 6)
        else:
            tp1 = round(price * (1 - TP_PCT), 6)
            sl = round(price * (1 + SL_PCT), 6)

        atr = abs(price - sl)
        confidence = calc_confidence(row, direction)

        if confidence < MIN_CONFIDENCE:
            print(f"⚠️ Confidence ضعيف ({confidence}%) — تجاهل الإشارة")
            return False

        signal_data = {
            "signal_id": str(uuid.uuid4())[:8],
            "symbol": SYMBOL_CLEAN,
            "direction": direction,
            "price": price,
            "sl": sl,
            "tp1": tp1,
            "atr": atr,
            "confidence": confidence,
            "market_state": "trending",
            "rsi": 50,
            "adx": 25,
            "trend": direction,
            "status": "pending",
            "time": datetime.now().strftime("%H:%M:%S")
        }

        redis_set("signal:pending", signal_data)
        print(f"📡 إشارة على Redis | {direction} | Confidence: {confidence}% | TP: {tp1} | SL: {sl}")
        return True

    except Exception as e:
        print(f"❌ خطأ إرسال الإشارة: {e}")
        return False


# ══════════════════════════════
# Data prep
# ══════════════════════════════
def prepare_data():
    try:
        print("📊 Checking database...")
        init_all_timeframes(SYMBOL)

        for interval in TARGET_CANDLES:
            count = count_candles(SYMBOL, interval)
            print(f" ✅ {interval}: {count} candles")

        print("\n📐 Loading timeframes...")
        dfs = load_all_timeframes(SYMBOL)

        print("⚙️ Extracting features...")
        df_features = extract_all_features(dfs)
        print(f"✅ {len(df_features)} rows | {len(df_features.columns)} features")

        return df_features

    except Exception as e:
        log_error("prepare_data", e)
        return None


# ══════════════════════════════
# Evolution loop
# ══════════════════════════════
def evolution_loop(df):
    global best_strategy
    round_num = 1

    while True:
        try:
            print(f"\n{'═'*40}")
            print(f"🧬 Evolution cycle {round_num} — {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'═'*40}")

            best = evolve(df)

            if best:
                s = best["stats"]
                with lock:
                    best_strategy = best["strategy"]

                print("\n🏆 Best strategy:")
                print_strategy(best["strategy"], 0)
                print(
                    f" 📊 WinRate: {s['win_rate']*100:.1f}% | "
                    f"Profit: {s['total_profit']*100:.2f}% | "
                    f"DD: {s['drawdown']*100:.1f}% | "
                    f"Sharpe: {s['sharpe']:.2f} | "
                    f"Trades: {s['trades']}"
                )
            else:
                print("⚠️ No valid strategy found")

            round_num += 1
            time.sleep(EVOLVE_INTERVAL)

        except Exception as e:
            log_error(f"evolution_loop_gen_{round_num}", e)
            time.sleep(60)


# ══════════════════════════════
# Trading loop
# ══════════════════════════════
def trading_loop():
    global open_trades, best_strategy

    print("\n⚡ Trading loop started...")

    from data_engine import load_all_timeframes
    from features import extract_all_features

    while True:
        try:
            trade_ok, reason = should_trade("bitcoin")

            if not trade_ok:
                print(f"🚫 {reason}")
                time.sleep(60)
                continue

            with lock:
                strategy = best_strategy
                open_count = len(open_trades)

            if strategy is None:
                saved = load_best()
                if saved:
                    strategy = saved["strategy"]
                    with lock:
                        best_strategy = strategy
                    print("📂 Loaded strategy from Redis")
                else:
                    time.sleep(30)
                    continue

            if open_count >= MAX_OPEN_TRADES:
                time.sleep(5)
                continue

            dfs = load_all_timeframes(SYMBOL)
            df = extract_all_features(dfs)

            if df is None or df.empty:
                time.sleep(10)
                continue

            last_row = df.iloc[-1].to_dict()
            price = float(last_row.get("close", 0))

            if price <= 0:
                time.sleep(10)
                continue

            signal = apply_strategy(strategy, last_row)

            # طباعة قيم الشروط
            print(f"─── {datetime.now().strftime('%H:%M:%S')} ───────────────")
            for cond in strategy.get("conditions", []):
                feature = cond["feature"]
                operator = cond["operator"]
                threshold = cond["threshold"]
                value = last_row.get(f"1m_{feature}", last_row.get(feature, 0))
                try:
                    met = "✅" if eval(f"{value} {operator} {threshold}") else "❌"
                except:
                    met = "❓"
                print(f"📊 {feature} = {float(value):.4f} | {operator} {threshold} {met}")

            if signal:
                direction = strategy["direction"]
                print(f"\n🚀 SIGNAL {direction} | {datetime.now().strftime('%H:%M:%S')}")

                sent = send_signal_to_redis(direction, price, last_row)

                if sent:
                    with lock:
                        open_trades.append({
                            "direction": direction,
                            "time": datetime.now(),
                            "capital": CAPITAL_PER_TRADE
                        })

            time.sleep(10)

        except Exception as e:
            log_error("trading_loop", e)
            time.sleep(30)


# ══════════════════════════════
# نظّف الصفقات المغلقة
# ══════════════════════════════
def cleanup_loop():
    while True:
        try:
            result = redis_get("signal:result")
            if result:
                symbol = result.get("symbol", "")
                print(f"📊 نتيجة {symbol}: {result.get('result')} | PnL: {result.get('pnl_pct')}%")
                with lock:
                    open_trades.clear()
        except Exception as e:
            print(f"⚠️ خطأ cleanup: {e}")
        time.sleep(30)


# ══════════════════════════════
# Main
# ══════════════════════════════
def main():
    print("🚀 Quant Bot Started — with Error Tracking")
    print("━" * 40)

    df = prepare_data()

    if df is None:
        print("❌ Failed to start — no data")
        return

    threading.Thread(target=evolution_loop, args=(df,), daemon=True).start()
    threading.Thread(target=trading_loop, daemon=True).start()
    threading.Thread(target=cleanup_loop, daemon=True).start()

    print("\n✅ System running")

    try:
        while True:
            time.sleep(60)
            with lock:
                print(f"📊 Open trades: {len(open_trades)}/{MAX_OPEN_TRADES}")
    except KeyboardInterrupt:
        print("\n🛑 Stopped")


if __name__ == "__main__":
    main()

