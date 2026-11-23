"""
Database access layer.

A single connection pool is created once and reused for every request.
This is the difference between ~800 ms and ~15 ms per query on Supabase.
"""
import os
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

_pool: "pool.SimpleConnectionPool | None" = None

# Supabase requires SSL. If your DSN already contains ?sslmode=require,
# passing it again here is harmless.
_MIN_CONN = 1
_MAX_CONN = int(os.environ.get("DB_POOL_MAX", "8"))


def init_pool() -> "pool.SimpleConnectionPool":
    """Create the connection pool (idempotent)."""
    global _pool
    if _pool is None:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError(
                "DATABASE_URL is not set. Copy .env.example to .env and fill it in."
            )
        _pool = pool.SimpleConnectionPool(
            _MIN_CONN, _MAX_CONN, dsn=dsn, sslmode="require", connect_timeout=10
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager
def db_cursor(commit: bool = False):
    """
    Usage:
        with db_cursor(commit=True) as cur:
            cur.execute("insert ...")
            cur.fetchone()

    Rolls back automatically on any exception, always returns the
    connection to the pool.
    """
    conn = init_pool().getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        if commit:
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        init_pool().putconn(conn)


def healthcheck() -> bool:
    """True when the database answers a trivial query."""
    try:
        with db_cursor() as cur:
            cur.execute("select 1 as ok")
            return cur.fetchone()["ok"] == 1
    except Exception:
        return False
