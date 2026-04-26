import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
def get_conn():
    return psycopg2.connect(
        host="aws-1-ap-northeast-1.pooler.supabase.com",
        port=5432,
        dbname="postgres",
        user="postgres.yxmtutzdjqiybetvkguf",
        password=os.getenv("DB_PASSWORD")
    )

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            user_address TEXT
        )
    """)
    conn.commit()
    conn.close()