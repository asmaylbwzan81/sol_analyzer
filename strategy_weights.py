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

# أسماء كل الاستراتيجيات الـ 14
ALL_STRATEGIES: List[str] = [
    "rsi", "macd", "ema", "bollinger", "volume",
    "momentum", "support_resistance", "pattern",
    "stochastic", "vwap", "adx", "fibonacci",
    "news", "memory", "supertrend",
]


# ─────────────────────────────────────────────
# إدارة قاعدة البيانات
# ─────────────────────────────────────────────
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """إنشاء الجدول وإضافة الاستراتيجيات إذا لم تكن موجودة."""
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

        # أضف أي استراتيجية ناقصة بالوزن الافتراضي
        for name in ALL_STRATEGIES:
            conn.execute("""
                INSERT OR IGNORE INTO strategy_weights
                    (strategy_name, weight, wins, losses)
                VALUES (?, ?, 0, 0)
            """, (name, DEFAULT_WEIGHT))
        conn.commit()

    logger.info("✅ strategy_weights DB initialized (%s)", DB_PATH)


# ─────────────────────────────────────────────
# القراءة
# ─────────────────────────────────────────────
def get_weight(strategy_name: str) -> float:
    """إرجاع وزن استراتيجية واحدة (1.0 إذا غير موجودة)."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT weight FROM strategy_weights WHERE strategy_name = ?",
            (strategy_name,)
        ).fetchone()
    return float(row["weight"]) if row else DEFAULT_WEIGHT


def get_all_weights() -> Dict[str, float]:
    """إرجاع dict كامل {strategy_name: weight}."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT strategy_name, weight FROM strategy_weights"
        ).fetchall()
    return {r["strategy_name"]: float(r["weight"]) for r in rows}


def get_stats() -> List[Dict]:
    """إرجاع إحصائيات كاملة لكل الاستراتيجيات (للعرض / التقارير)."""
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
    """
    حدّث أوزان الاستراتيجيات بعد انتهاء صفقة.

    Parameters
    ----------
    strategies_used : list[str]
        أسماء الاستراتيجيات التي شاركت في قرار الصفقة.
    result : str
        "WIN" أو "LOSS"

    Returns
    -------
    dict {strategy_name: new_weight}
    """
    result = result.upper().strip()
    if result not in ("WIN", "LOSS"):
        logger.warning("⚠️ نتيجة غير معروفة: %s — تم تجاهل التحديث", result)
        return {}

    delta = WIN_DELTA if result == "WIN" else LOSS_DELTA
    win_inc = 1 if result == "WIN" else 0
    loss_inc = 0 if result == "WIN" else 1

    updated = {}

    with _get_conn() as conn:
        for name in strategies_used:
            name = name.lower().strip()

            # إذا الاستراتيجية غير موجودة أضفها
            conn.execute("""
                INSERT OR IGNORE INTO strategy_weights
                    (strategy_name, weight, wins, losses)
                VALUES (?, ?, 0, 0)
            """, (name, DEFAULT_WEIGHT))

            row = conn.execute(
                "SELECT weight, wins, losses FROM strategy_weights WHERE strategy_name = ?",
                (name,)
            ).fetchone()

            old_weight = float(row["weight"])
            new_weight = _clamp(old_weight + delta)
            new_wins = row["wins"] + win_inc
            new_losses = row["losses"] + loss_inc

            conn.execute("""
                UPDATE strategy_weights
                SET weight = ?,
                    wins = ?,
                    losses = ?
                WHERE strategy_name = ?
            """, (new_weight, new_wins, new_losses, name))

            updated[name] = new_weight
            logger.info(
                "📊 %s | %s | %.2f → %.2f | W:%d L:%d",
                name, result, old_weight, new_weight, new_wins, new_losses
            )

        conn.commit()

    return updated


# ─────────────────────────────────────────────
# التصويت المرجّح (Weighted Voting)
# ─────────────────────────────────────────────
def weighted_score(signals: Dict[str, float]) -> float:
    """
    احسب الـ score النهائي باستخدام الأوزان الديناميكية.

    Parameters
    ----------
    signals : dict {strategy_name: signal_value}
        signal_value بين 0.0 (نزول قوي) و 1.0 (صعود قوي).

    Returns
    -------
    float — score مرجّح بين 0.0 و 1.0
    """
    if not signals:
        return 0.5 # محايد

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
# Reset (للاختبار أو إعادة الضبط)
# ─────────────────────────────────────────────
def reset_all_weights() -> None:
    """إعادة كل الأوزان للقيمة الافتراضية 1.0."""
    with _get_conn() as conn:
        conn.execute("""
            UPDATE strategy_weights
            SET weight = ?, wins = 0, losses = 0
        """, (DEFAULT_WEIGHT,))
        conn.commit()
    logger.info("🔄 تم إعادة تعيين كل الأوزان إلى %.1f", DEFAULT_WEIGHT)


# ─────────────────────────────────────────────
# تشغيل مباشر للاختبار
# ─────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # 1. تهيئة قاعدة البيانات
    init_db()

    # 2. محاكاة إشارات من الاستراتيجيات
    test_signals = {
        "rsi": 0.80,
        "macd": 0.70,
        "ema": 0.90,
        "bollinger": 0.60,
        "volume": 0.75,
    }

    print("\n📊 الأوزان الحالية:")
    for name, w in get_all_weights().items():
        print(f" {name:<25} {w:.2f}")

    # 3. حساب الـ score المرجّح
    score = weighted_score(test_signals)
    print(f"\n🎯 Weighted Score: {score}")
    if score >= 0.60:
        print(" → قرار: LONG ✅")
    elif score <= 0.40:
        print(" → قرار: SHORT 🔴")
    else:
        print(" → قرار: SKIP ⏭️")

    # 4. تحديث الأوزان بعد WIN
    print("\n✅ تحديث بعد WIN:")
    update_weights(list(test_signals.keys()), "WIN")

    # 5. تحديث الأوزان بعد LOSS
    print("\n❌ تحديث بعد LOSS:")
    update_weights(["macd", "bollinger"], "LOSS")

    # 6. إحصائيات كاملة
    print("\n📈 الإحصائيات الكاملة:")
    print(f"{'Strategy':<25} {'Weight':>7} {'Wins':>5} {'Losses':>7} {'Win%':>6}")
    print("-" * 55)
    for s in get_stats():
        wr = f"{s['win_rate']}%" if s['win_rate'] is not None else " N/A"
        print(f"{s['strategy_name']:<25} {s['weight']:>7.2f} {s['wins']:>5} {s['losses']:>7} {wr:>6}")

