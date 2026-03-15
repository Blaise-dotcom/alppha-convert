import psycopg2
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


def get_conn():
    return psycopg2.connect(DATABASE_URL)


# ─── Initialisation des tables ────────────────────────────────────────────────

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id     BIGINT PRIMARY KEY,
                    username    TEXT,
                    first_name  TEXT,
                    is_premium  BOOLEAN DEFAULT FALSE,
                    premium_until DATE,
                    created_at  TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_usage (
                    user_id      BIGINT,
                    usage_date   DATE,
                    downloads    INTEGER DEFAULT 0,
                    compressions INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, usage_date)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id         SERIAL PRIMARY KEY,
                    user_id    BIGINT,
                    plan       TEXT,
                    currency   TEXT,
                    amount     NUMERIC,
                    status     TEXT DEFAULT 'pending',
                    tx_hash    TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
        conn.commit()
    logger.info("✅ Base de données initialisée")


# ─── Utilisateurs ─────────────────────────────────────────────────────────────

def ensure_user(user_id: int, username: str = None, first_name: str = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, username, first_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                    SET username   = EXCLUDED.username,
                        first_name = EXCLUDED.first_name
            """, (user_id, username, first_name))
        conn.commit()


def is_premium(user_id: int) -> bool:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT is_premium, premium_until FROM users WHERE user_id = %s",
                (user_id,)
            )
            row = cur.fetchone()
    if not row:
        return False
    return bool(row["is_premium"]) and row["premium_until"] is not None and row["premium_until"] >= date.today()


def set_premium(user_id: int, until_date: date):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users
                SET is_premium = TRUE, premium_until = %s
                WHERE user_id = %s
            """, (until_date, user_id))
        conn.commit()


# ─── Usage quotidien ──────────────────────────────────────────────────────────

def get_usage(user_id: int) -> dict:
    today = date.today()
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT downloads, compressions
                FROM daily_usage
                WHERE user_id = %s AND usage_date = %s
            """, (user_id, today))
            row = cur.fetchone()
    return dict(row) if row else {"downloads": 0, "compressions": 0}


def increment_usage(user_id: int, field: str):
    """field: 'downloads' ou 'compressions'"""
    today = date.today()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO daily_usage (user_id, usage_date, {field})
                VALUES (%s, %s, 1)
                ON CONFLICT (user_id, usage_date) DO UPDATE
                    SET {field} = daily_usage.{field} + 1
            """, (user_id, today))
        conn.commit()


# ─── Transactions ─────────────────────────────────────────────────────────────

def add_transaction(user_id: int, plan: str, currency: str, amount, tx_hash: str = None) -> int:
    status = "pending" if tx_hash else "completed"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO transactions (user_id, plan, currency, amount, tx_hash, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (user_id, plan, currency, amount, tx_hash, status))
            tx_id = cur.fetchone()[0]
        conn.commit()
    return tx_id


def complete_transaction(tx_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE transactions SET status = 'completed' WHERE id = %s", (tx_id,))
        conn.commit()
