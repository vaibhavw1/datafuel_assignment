from db import get_connection


conn = get_connection()

stores = conn.execute(
    "SELECT COUNT(*) AS count FROM stores"
).fetchone()

active_stores = conn.execute(
    "SELECT COUNT(*) AS count FROM stores WHERE is_active = 1"
).fetchone()

sweeps = conn.execute(
    "SELECT COUNT(*) AS count FROM sweeps"
).fetchone()

complete_sweeps = conn.execute(
    "SELECT COUNT(*) AS count FROM sweeps WHERE complete = 1"
).fetchone()

inventory = conn.execute(
    "SELECT COUNT(*) AS count FROM inventory"
).fetchone()

print("Total stores:", stores["count"])
print("Active stores:", active_stores["count"])
print("Sweeps:", sweeps["count"])
print("Complete sweeps:", complete_sweeps["count"])
print("Inventory rows:", inventory["count"])

print("\nInventory by store:")

rows = conn.execute(
    """
    SELECT
        store_id,
        COUNT(*) AS sku_count
    FROM inventory
    GROUP BY store_id
    ORDER BY store_id
    """
).fetchall()

for row in rows:
    print(row["store_id"], row["sku_count"])

conn.close()