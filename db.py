import sqlite3

DB_NAME = "osa.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            store_id TEXT PRIMARY KEY,
            city TEXT NOT NULL,
            name TEXT NOT NULL,
            is_active INTEGER NOT NULL,
            is_serviceable INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sweeps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id TEXT NOT NULL,
            as_of TEXT NOT NULL,
            complete INTEGER NOT NULL,
            reason TEXT,
            UNIQUE(store_id, as_of)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            store_id TEXT NOT NULL,
            as_of TEXT NOT NULL,
            sku_id TEXT NOT NULL,
            name TEXT NOT NULL,
            in_stock INTEGER NOT NULL,
            qty INTEGER,
            price REAL,
            observed_at TEXT,
            PRIMARY KEY (store_id, as_of, sku_id)
        )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized.")