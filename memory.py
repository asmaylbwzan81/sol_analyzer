import json
import time

# memory.py - Trade Signal Memory System (Redis Async)
#
# Expected Redis structure:
# signal:memory:{signal_id} -> JSON string
# signal:result:{signal_id} -> JSON string
# signal:history:{symbol} -> LIST of signal_ids


# 1. SAVE SIGNAL MEMORY

async def save_signal_memory(redis, signal_id: str, signal_data: dict):
    # Save signal conditions at time of sending
    key = f"signal:memory:{signal_id}"

    payload = json.dumps({
        **signal_data,
        "timestamp": signal_data.get("timestamp", int(time.time()))
    })

    await redis.set(key, payload)

    symbol = signal_data.get("symbol")
    if symbol:
        await redis.lpush(f"signal:history:{symbol}", signal_id)
        await redis.ltrim(f"signal:history:{symbol}", 0, 19)


# 2. GET SIGNAL RESULT

async def get_signal_result(redis, signal_id: str):
    # Read result written by execution bot
    key = f"signal:result:{signal_id}"

    data = await redis.get(key)
    if not data:
        return None

    if isinstance(data, bytes):
        data = data.decode("utf-8")

    return json.loads(data)


# 3. SHOULD BLOCK SIGNAL (CORE MEMORY LOGIC)

async def should_block_signal(
    redis,
    symbol: str,
    direction: str,
    market_regime: str,
    htf_trend: str
) -> bool:
    # If same conditions failed >= 2 times in last 3 - block signal

    history_key = f"signal:history:{symbol}"
    signal_ids = await redis.lrange(history_key, 0, 9)

    if not signal_ids:
        return False

    failed = 0
    checked = 0

    for sid in signal_ids:
        if isinstance(sid, bytes):
            sid = sid.decode("utf-8")

        mem_raw = await redis.get(f"signal:memory:{sid}")
        if not mem_raw:
            continue

        if isinstance(mem_raw, bytes):
            mem_raw = mem_raw.decode("utf-8")

        memory = json.loads(mem_raw)

        if (
            memory.get("symbol") == symbol and
            memory.get("direction") == direction and
            memory.get("market_regime") == market_regime and
            memory.get("htf_trend") == htf_trend
        ):
            result = await get_signal_result(redis, sid)

            if result and result.get("result") == "LOSS":
                failed += 1

            checked += 1

        if checked >= 3:
            break

    return failed >= 2


# 4. OPTIONAL DEBUG HELPER

async def debug_signal_memory(redis, symbol: str):
    # Print last signals for inspection
    history = await redis.lrange(f"signal:history:{symbol}", 0, 9)

    out = []

    for sid in history:
        if isinstance(sid, bytes):
            sid = sid.decode("utf-8")

        mem = await redis.get(f"signal:memory:{sid}")
        res = await redis.get(f"signal:result:{sid}")

        out.append({
            "signal_id": sid,
            "memory": mem.decode() if isinstance(mem, bytes) and mem else mem,
            "result": res.decode() if isinstance(res, bytes) and res else res
        })

    return out
