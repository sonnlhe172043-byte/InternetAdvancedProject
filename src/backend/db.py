# db.py

import psycopg2
import os

from psycopg2.pool import SimpleConnectionPool

from dotenv import load_dotenv

load_dotenv()

DB_PASSWORD = os.getenv("DB_PASSWORD")

# =========================
# CONNECTION POOL
# =========================
pool = SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    host="aws-1-ap-northeast-1.pooler.supabase.com",
    port=5432,
    dbname="postgres",
    user="postgres.yxmtutzdjqiybetvkguf",
    password=DB_PASSWORD
)

# =========================
# GET CONNECTION
# =========================
def get_conn():

    return pool.getconn()

# =========================
# RELEASE CONNECTION
# =========================
def release_conn(conn):

    pool.putconn(conn)

# =========================
# INIT DB
# =========================
def init_db():

    conn = get_conn()

    c = conn.cursor()

    # =========================
    # PERMISSIONS
    # =========================
    c.execute("""
        CREATE TABLE IF NOT EXISTS permissions (

            id TEXT PRIMARY KEY,

            email TEXT UNIQUE,

            user_address TEXT UNIQUE,

            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # =========================
    # FILES
    # =========================
    c.execute("""
        CREATE TABLE IF NOT EXISTS files (

            id SERIAL PRIMARY KEY,

            cid TEXT NOT NULL,

            filename TEXT NOT NULL,

            owner TEXT NOT NULL,

            uploader TEXT NOT NULL,

            tx_hash TEXT,

            ipfs_url TEXT NOT NULL,

            uploaded_at BIGINT NOT NULL,

            blockchain_status TEXT DEFAULT 'pending'
        )
    """)

    # =========================
    # INDEXES
    # =========================
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_owner
        ON files(owner)
    """)

    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_uploader
        ON files(uploader)
    """)

    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_uploaded_at
        ON files(uploaded_at DESC)
    """)

    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_cid
        ON files(cid)
    """)

    conn.commit()

    conn.close()