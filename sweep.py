
import argparse
import random
import time
from datetime import datetime

import requests

from db import get_connection, init_db


BASE_URL = "http://127.0.0.1:8765"
API_KEY = "dfhire-2026"

HEADERS = {"X-Api-Key": API_KEY}

# Keep requests below the burst limit and reduce sustained load.
MIN_REQUEST_INTERVAL = 0.4
_last_request_time = 0.0


def validate_as_of(value):
    """Require an ISO-8601 timestamp with a timezone."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Use an ISO-8601 timestamp, e.g. 2026-09-28T04:30:00Z"
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError(
            "The --as-of timestamp must include a timezone."
        )

    return value


def wait_for_request_slot():
    """Space out requests to reduce rate limiting and soft-ban risk."""
    global _last_request_time

    now = time.monotonic()
    remaining = MIN_REQUEST_INTERVAL - (now - _last_request_time)

    if remaining > 0:
        time.sleep(remaining)

    _last_request_time = time.monotonic()


def request_with_retry(method, url, **kwargs):
    """Retry rate limits and transient server/network failures."""
    max_retries = 3

    for attempt in range(max_retries + 1):
        wait_for_request_slot()

        try:
            response = requests.request(
                method,
                url,
                timeout=10,
                **kwargs,
            )

            if response.status_code == 429:
                if attempt == max_retries:
                    return response

                retry_after = response.headers.get("Retry-After", "2")
                try:
                    wait_time = float(retry_after)
                except ValueError:
                    wait_time = 2 ** attempt

                time.sleep(max(0, wait_time))
                continue

            if response.status_code in (500, 503):
                if attempt == max_retries:
                    return response

                time.sleep(2 ** attempt + random.uniform(0, 0.5))
                continue

            return response

        except (requests.Timeout, requests.ConnectionError):
            if attempt == max_retries:
                raise

            time.sleep(2 ** attempt + random.uniform(0, 0.5))

    raise RuntimeError("Request failed after retries")


def get_stores():
    """Fetch all store pages from the portal."""
    stores = []
    page = 1
    seen_pages = set()

    while page is not None:
        if page in seen_pages:
            raise RuntimeError(f"Store pagination repeated page {page}")

        seen_pages.add(page)

        response = request_with_retry(
            "GET",
            f"{BASE_URL}/v1/stores",
            headers=HEADERS,
            params={"page": page},
        )
        response.raise_for_status()
        data = response.json()

        stores.extend(data["stores"])
        page = data.get("next_page")

    # Prevent duplicate store records from being processed twice.
    stores_by_id = {store["store_id"]: store for store in stores}
    return list(stores_by_id.values())


def get_inventory(store_id, as_of):
    """Fetch every page and reject partial or degraded snapshots."""
    items_by_sku = {}
    cursor = None
    seen_cursors = set()

    while True:
        params = {"as_of": as_of}
        if cursor is not None:
            params["cursor"] = cursor

        response = request_with_retry(
            "GET",
            f"{BASE_URL}/v1/stores/{store_id}/inventory",
            headers=HEADERS,
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        meta = data.get("meta") or {}
        source = meta.get("source")

        # The portal can return degraded data with HTTP 200.
        if source != "origin":
            return {
                "items": [],
                "complete": False,
                "reason": f"unexpected inventory source: {source!r}",
            }

        if data.get("partial", False):
            return {
                "items": [],
                "complete": False,
                "reason": "partial response",
            }

        for item in data.get("items", []):
            items_by_sku[item["sku_id"]] = item

        next_cursor = data.get("next_cursor")

        if next_cursor is None:
            break

        if next_cursor in seen_cursors or next_cursor == cursor:
            return {
                "items": [],
                "complete": False,
                "reason": "pagination cursor repeated",
            }

        seen_cursors.add(next_cursor)
        cursor = next_cursor

    return {
        "items": list(items_by_sku.values()),
        "complete": True,
        "reason": None,
    }


def save_store(store):
    """Insert or update store metadata."""
    conn = get_connection()

    try:
        conn.execute(
            """
            INSERT INTO stores (
                store_id, city, name, is_active, is_serviceable
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(store_id) DO UPDATE SET
                city = excluded.city,
                name = excluded.name,
                is_active = excluded.is_active,
                is_serviceable = excluded.is_serviceable
            """,
            (
                store["store_id"],
                store["city"],
                store["name"],
                int(store["is_active"]),
                int(store["is_serviceable"]),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def save_inventory(store_id, as_of, result):
    """Save sweep status and only trusted, complete inventory."""
    conn = get_connection()

    try:
        existing = conn.execute(
            """
            SELECT complete
            FROM sweeps
            WHERE store_id = ? AND as_of = ?
            """,
            (store_id, as_of),
        ).fetchone()

        # Never replace a trusted snapshot with a failed rerun.
        if (
            existing is not None
            and existing["complete"] == 1
            and not result["complete"]
        ):
            return

        conn.execute(
            """
            INSERT INTO sweeps (store_id, as_of, complete, reason)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(store_id, as_of) DO UPDATE SET
                complete = excluded.complete,
                reason = excluded.reason
            """,
            (
                store_id,
                as_of,
                int(result["complete"]),
                result["reason"],
            ),
        )

        # Replace old rows atomically for this snapshot.
        conn.execute(
            """
            DELETE FROM inventory
            WHERE store_id = ? AND as_of = ?
            """,
            (store_id, as_of),
        )

        if result["complete"]:
            for item in result["items"]:
                conn.execute(
                    """
                    INSERT INTO inventory (
                        store_id, as_of, sku_id, name,
                        in_stock, qty, price, observed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(store_id, as_of, sku_id)
                    DO UPDATE SET
                        name = excluded.name,
                        in_stock = excluded.in_stock,
                        qty = excluded.qty,
                        price = excluded.price,
                        observed_at = excluded.observed_at
                    """,
                    (
                        store_id,
                        as_of,
                        item["sku_id"],
                        item["name"],
                        int(item["in_stock"]),
                        item.get("qty"),
                        item.get("price"),
                        item.get("observed_at"),
                    ),
                )

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Collect QuickMart inventory for a snapshot timestamp."
    )
    parser.add_argument(
        "--as-of",
        required=True,
        type=validate_as_of,
        help="ISO-8601 timestamp with timezone, e.g. 2026-09-28T04:30:00Z",
    )
    args = parser.parse_args()
    as_of = args.as_of

    started = time.monotonic()
    init_db()

    stores = get_stores()
    print(f"Total stores discovered: {len(stores)}")

    for store in stores:
        save_store(store)

    # Track active stores. Serviceability can change during the day,
    # so it is not used to decide whether a store belongs in the sweep.
    active_stores = [store for store in stores if store["is_active"]]
    print(f"Active stores to sweep: {len(active_stores)}")
    print(f"Snapshot timestamp: {as_of}")

    successful = 0
    incomplete = 0
    failed = 0
    problems = []

    for index, store in enumerate(active_stores, start=1):
        store_id = store["store_id"]
        print(f"[{index}/{len(active_stores)}] Sweeping {store_id}...")

        try:
            result = get_inventory(store_id, as_of)
            save_inventory(store_id, as_of, result)

            if result["complete"]:
                successful += 1
                print(f"  OK: {len(result['items'])} unique items")
            else:
                incomplete += 1
                problems.append((store_id, result["reason"]))
                print(f"  INCOMPLETE: {result['reason']}")

        except requests.RequestException as exc:
            reason = f"request failed: {exc}"
            failed += 1
            problems.append((store_id, reason))
            print(f"  FAILED: {reason}")

            # Record the failed attempt so coverage does not silently
            # treat this store as if it had never been attempted.
            try:
                save_inventory(
                    store_id,
                    as_of,
                    {
                        "items": [],
                        "complete": False,
                        "reason": reason,
                    },
                )
            except Exception as save_exc:
                print(f"  Could not save failure status: {save_exc}")

        except Exception as exc:
            reason = f"unexpected error: {exc}"
            failed += 1
            problems.append((store_id, reason))
            print(f"  FAILED: {reason}")

            try:
                save_inventory(
                    store_id,
                    as_of,
                    {
                        "items": [],
                        "complete": False,
                        "reason": reason,
                    },
                )
            except Exception as save_exc:
                print(f"  Could not save failure status: {save_exc}")

    elapsed = time.monotonic() - started

    print("\nSweep completed.")
    print(f"Timestamp: {as_of}")
    print(f"Successful: {successful}")
    print(f"Incomplete: {incomplete}")
    print(f"Failed: {failed}")
    print(f"Elapsed: {elapsed:.1f} seconds")

    if problems:
        print("Stores requiring attention:")
        for store_id, reason in problems:
            print(f"  {store_id}: {reason}")


if __name__ == "__main__":
    main()
