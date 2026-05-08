"""
strategy_weights.py
===================
Strategy Dynamic Weighting System
- كل استراتيجية تبدأ بوزن 1.0
- تزيد عند WIN (+0.02) وتنقص عند LOSS (-0.03)
- الحدود: min=0.2, max=2.0
"""

import sqlite3
import os
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# الإعدادات
# ─────────────────────────────────────────────
DB_PATH = os.getenv("WEIGHTS_DB_PATH", "strategy_weights.db")

DEFAULT_WEIGHT = 1.0
WIN_DELTA = +0.02
LOSS_DELTA = -0.03
MIN_WEIGHT = 0.2
MAX_WEIGHT = 2.0

ALL_STRATEGIES: List[str] = [
    "rsi", "macd", "ema", "bollinger", "volume",
    "momentum", "support_resistance", "pattern",
    "stochastic", "vwap", "adx", "fibonacci",
    "news", "memory", "supertrend",
]

# ── الأوزان الابتدائية حسب الطبقة ──────────
INITIAL_WEIGHTS: Dict[str, float] = {
    # 💪 قوي
    "rsi": 1.5,
    "bollinger": 1.5,
    "stochastic": 1.5,
    "fibonacci": 1.5,
    "support_resistance": 1.5,
    # 😐 متوسط
    "adx": 1.0,
    "supertrend": 1.0,
    "vwap": 1.0,
    "volume": 1.0,
    "pattern": 1.0,
    "news": 1.0,
    "memory": 1.0,
    # 😴 ضعيف
    "momentum": 0.5,
    "macd": 0.5,
    "ema": 0.5,
}


# ─────────────────────────────────────────────
# إدارة قاعدة البيانات
# ─────────────────────────────────────────────
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS strategy_weights (
                strategy_name TEXT PRIMARY KEY,
                weight FLOAT NOT NULL DEFAULT 1.0,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
        for name in ALL_STRATEGIES:
            w = INITIAL_WEIGHTS.get(name, DEFAULT_WEIGHT)
            conn.execute("""
                INSERT OR IGNORE INTO strategy_weights
                    (strategy_name, weight, wins, losses)
                VALUES (?, ?, 0, 0)
            """, (name, w))
        conn.commit()
    logger.info("✅ strategy_weights DB initialized (%s)", DB_PATH)


# ─────────────────────────────────────────────
# القراءة
# ─────────────────────────────────────────────
def get_weight(strategy_name: str) -> float:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT weight FROM strategy_weights WHERE strategy_name = ?",
            (strategy_name,)
        ).fetchone()
    return float(row["weight"]) if row else DEFAULT_WEIGHT


def get_all_weights() -> Dict[str, float]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT strategy_name, weight FROM strategy_weights"
        ).fetchall()
    return {r["strategy_name"]: float(r["weight"]) for r in rows}


def get_stats() -> List[Dict]:
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT strategy_name, weight, wins, losses,
                   CASE WHEN (wins + losses) > 0
                        THEN ROUND(100.0 * wins / (wins + losses), 1)
                        ELSE NULL
                   END AS win_rate
            FROM strategy_weights
            ORDER BY weight DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# التحديث
# ─────────────────────────────────────────────
def _clamp(value: float) -> float:
    return max(MIN_WEIGHT, min(value, MAX_WEIGHT))


def update_weights(strategies_used: List[str], result: str) -> Dict[str, float]:
    result = result.upper().strip()
    if result not in ("WIN", "LOSS"):
        logger.warning("⚠️ نتيجة غير معروفة: %s", result)
        return {}

    delta = WIN_DELTA if result == "WIN" else LOSS_DELTA
    win_inc = 1 if result == "WIN" else 0
    loss_inc = 0 if result == "WIN" else 1
    updated = {}

    with _get_conn() as conn:
        for name in strategies_used:
            name = name.lower().strip()
            conn.execute("""
                INSERT OR IGNORE INTO strategy_weights
                    (strategy_name, weight, wins, losses)
                VALUES (?, ?, 0, 0)
            """, (name, DEFAULT_WEIGHT))

            row = conn.execute(
                "SELECT weight, wins, losses FROM strategy_weights WHERE strategy_name = ?",
                (name,)
            ).fetchone()

            old_w = float(row["weight"])
            new_w = _clamp(old_w + delta)
            new_wins = row["wins"] + win_inc
            new_losses = row["losses"] + loss_inc

            conn.execute("""
                UPDATE strategy_weights
                SET weight = ?, wins = ?, losses = ?
                WHERE strategy_name = ?
            """, (new_w, new_wins, new_losses, name))

            updated[name] = new_w
            logger.info("📊 %s | %s | %.2f → %.2f | W:%d L:%d",
                        name, result, old_w, new_w, new_wins, new_losses)
        conn.commit()

    return updated


# ─────────────────────────────────────────────
# التصويت المرجّح
# ─────────────────────────────────────────────
def weighted_score(signals: Dict[str, float]) -> float:
    """
    احسب الـ score النهائي باستخدام الأوزان الديناميكية.
    signal_value بين 0.0 (نزول قوي) و 1.0 (صعود قوي).
    """
    if not signals:
        return 0.5

    weights = get_all_weights()
    total_weighted = 0.0
    total_weight = 0.0

    for strategy, signal in signals.items():
        w = weights.get(strategy.lower(), DEFAULT_WEIGHT)
        total_weighted += signal * w
        total_weight += w

    if total_weight == 0:
        return 0.5

    return round(total_weighted / total_weight, 4)


# ─────────────────────────────────────────────
# Reset
# ─────────────────────────────────────────────
def reset_all_weights() -> None:
    with _get_conn() as conn:
        conn.execute("""
            UPDATE strategy_weights
            SET weight = ?, wins = 0, losses = 0
        """, (DEFAULT_WEIGHT,))
        conn.commit()
    logger.info("🔄 تم إعادة تعيين كل الأوزان إلى %.1f", DEFAULT_WEIGHT)
