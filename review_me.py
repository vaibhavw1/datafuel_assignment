
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

PORTAL = "http://127.0.0.1:8765"
HEADERS = {"X-Api-Key": "dfhire-2026"}

MAX_RETRIES = 3
REQUEST_TIMEOUT = 5
IST = ZoneInfo("Asia/Kolkata")


def fetch_inventory(store_id, as_of, cursor="0"):
    """Fetch all inventory pages for a store."""

    results = []
    seen_cursors = set()

    while cursor:
        if cursor in seen_cursors:
            raise RuntimeError(f"Repeated cursor for store {store_id}: {cursor}")

        seen_cursors.add(cursor)

        for attempt in range(MAX_RETRIES):
            try:
                r = requests.get(
                    f"{PORTAL}/v1/stores/{store_id}/inventory",
                    params={"as_of": as_of, "cursor": cursor},
                    headers=HEADERS,
                    timeout=REQUEST_TIMEOUT,
                )
                r.raise_for_status()
                body = r.json()
                break

            except (requests.RequestException, ValueError):
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(1)

        if not isinstance(body, dict) or not isinstance(body.get("items"), list):
            raise ValueError(f"Invalid inventory response for store {store_id}")

        results.extend(body["items"])
        cursor = body.get("next_cursor")

    return results


def save(conn, store_id, as_of, items):
    """Save inventory records into the database."""

    for it in items:
        conn.execute(
            """
            INSERT OR REPLACE INTO inventory
            (store_id, as_of, sku_id, name, in_stock, qty, price, observed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                store_id,
                as_of,
                it["sku_id"],
                it["name"],
                int(bool(it["in_stock"])),
                it.get("qty"),
                it.get("price"),
                it["observed_at"],
            ),
        )

    conn.commit()


def city_osa(conn, city, day=None):
    """On-shelf availability for a city and an IST date."""

    day = day or (
        datetime.now(IST).date() - timedelta(days=1)
    ).isoformat()

    stores = [
        r[0]
        for r in conn.execute(
            "SELECT store_id FROM stores WHERE city = ? AND is_active = 1",
            (city,),
        )
    ]

    total_observations = 0
    in_stock_observations = 0

    for store_id in stores:
        rows = conn.execute(
            """
            SELECT in_stock, observed_at
            FROM inventory
            WHERE store_id = ?
            """,
            (store_id,),
        ).fetchall()

        for in_stock, observed_at in rows:
            if not observed_at:
                continue

            timestamp = datetime.fromisoformat(
                observed_at.replace("Z", "+00:00")
            )

            # Handle timestamps that don't include a timezone.
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(timezone.utc)

            if timestamp.astimezone(IST).date().isoformat() != day:
                continue

            total_observations += 1
            if in_stock:
                in_stock_observations += 1

    if total_observations == 0:
        return None

    return round(
        100 * in_stock_observations / total_observations, 2
    )


if __name__ == "__main__":
    conn = sqlite3.connect("osa.db")

    try:
        # Use the schema already managed by db.py.
        as_of = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        for store_id in ["MUM-001", "MUM-002"]:
            items = fetch_inventory(store_id, as_of)
            save(conn, store_id, as_of, items)

        print(city_osa(conn, "Mumbai"))

    finally:
        conn.close()
