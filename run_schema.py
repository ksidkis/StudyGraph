from database.connection import get_connection

with get_connection() as conn:
    with conn.cursor() as cur:
        with open("database/schema.sql", "r") as f:
            cur.execute(f.read())
    conn.commit()

print("Tables created 🧱")