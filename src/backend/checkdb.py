import sqlite3
from src.backend.db import DB

conn = sqlite3.connect(DB)
c = conn.cursor()

#c.execute("DELETE FROM permissions")

#conn.commit()
#conn.close()

c.execute("SELECT * FROM permissions")
rows = c.fetchall()

for r in rows:
    print(r)

print("All data deleted")