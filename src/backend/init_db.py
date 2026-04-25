import sqlite3
from src.backend.db import DB

conn = sqlite3.connect(DB)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS permissions (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    user_address TEXT
)
""")

conn.commit()
conn.close()

print("DB initialized")