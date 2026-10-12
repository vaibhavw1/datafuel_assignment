
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException

from db import get_connection


app = FastAPI(title="QuickMart OSA API")

IST = ZoneInfo("Asia/Kolkata")

ALLOWED_CITIES = {"Mumbai", "Delhi", "Bengaluru"}


def utc_to_ist_date(timestamp):
    """
    Convert a UTC timestamp from the database
    to an Indian calendar date.
    """
    dt = datetime.fromisoformat(
        timestamp.replace("Z", "+00:00")
    )

    return dt.astimezone(IST).date()


def empty_coverage(
    expected_stores=0,
    complete_stores=0,
    incomplete_stores=0,
    stores_with_inventory=0
):
    return {
        "expected_stores": expected_stores,
        "complete_stores": complete_stores,
        "incomplete_stores": incomplete_stores,
        "stores_with_inventory": stores_with_inventory
    }


@app.get("/osa")
def get_osa(city: str, date: str = None):
    """
    Calculate weighted On-Shelf Availability (OSA)
    for a city and Indian calendar date.

    If date is omitted, use yesterday's date in IST.
    """

    # Validate city before accessing the database.
    if city not in ALLOWED_CITIES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported city: {city}. "
                "Allowed cities are Mumbai, Delhi, Bengaluru."
            )
        )

    # Default to yesterday in Indian Standard Time.
    if date is None:
        from datetime import timedelta

        requested_date = (
            datetime.now(IST).date() - timedelta(days=1)
        )
        date = requested_date.isoformat()
    else:
        # Validate both the date format and calendar date.
        try:
            requested_date = datetime.strptime(
                date, "%Y-%m-%d"
            ).date()

            # Reject non-canonical formats such as 2026-1-2.
            if requested_date.isoformat() != date:
                raise ValueError
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="date must be in YYYY-MM-DD format"
            )

    conn = get_connection()

    try:
        # Get all active stores for the requested city.
        stores = conn.execute(
            """
            SELECT store_id
            FROM stores
            WHERE city = ?
              AND is_active = 1
            ORDER BY store_id
            """,
            (city,)
        ).fetchall()

        if not stores:
            return {
                "city": city,
                "date": date,
                "status": "no_data",
                "osa_pct": None,
                "total_observations": 0,
                "in_stock_observations": 0,
                "coverage": empty_coverage()
            }

        expected_stores = len(stores)
        complete_stores = 0
        incomplete_stores = 0
        stores_with_inventory = 0

        total_observations = 0
        in_stock_observations = 0

        for store in stores:
            store_id = store["store_id"]

            # Find all sweeps belonging to this store.
            sweeps = conn.execute(
                """
                SELECT as_of, complete
                FROM sweeps
                WHERE store_id = ?
                ORDER BY as_of
                """,
                (store_id,)
            ).fetchall()

            # Only consider sweeps that fall on the requested
            # calendar date after conversion to IST.
            matching_sweeps = [
                sweep
                for sweep in sweeps
                if utc_to_ist_date(sweep["as_of"]) == requested_date
            ]

            # No sweep for this store/date means coverage is incomplete.
            if not matching_sweeps:
                incomplete_stores += 1
                continue

            # Prefer a complete sweep if one exists for this date.
            # If none exists, do not treat partial data as valid.
            complete_sweeps = [
                sweep
                for sweep in matching_sweeps
                if sweep["complete"]
            ]

            if not complete_sweeps:
                incomplete_stores += 1
                continue

            # Use the latest complete sweep on that IST date.
            matching_sweep = complete_sweeps[-1]
            complete_stores += 1

            # Only count inventory from the selected complete sweep.
            rows = conn.execute(
                """
                SELECT in_stock
                FROM inventory
                WHERE store_id = ?
                  AND as_of = ?
                """,
                (store_id, matching_sweep["as_of"])
            ).fetchall()

            if rows:
                stores_with_inventory += 1

            for row in rows:
                total_observations += 1

                if row["in_stock"]:
                    in_stock_observations += 1

        coverage = empty_coverage(
            expected_stores=expected_stores,
            complete_stores=complete_stores,
            incomplete_stores=incomplete_stores,
            stores_with_inventory=stores_with_inventory
        )

        # Do not report an OSA percentage when there are no
        # valid inventory observations.
        if total_observations == 0:
            return {
                "city": city,
                "date": date,
                "status": "no_data",
                "osa_pct": None,
                "total_observations": 0,
                "in_stock_observations": 0,
                "coverage": coverage
            }

        # Weighted OSA = in-stock observations / all observations.
        osa_pct = (
            in_stock_observations / total_observations
        ) * 100

        return {
            "city": city,
            "date": date,
            "status": "ok",
            "osa_pct": round(osa_pct, 2),
            "total_observations": total_observations,
            "in_stock_observations": in_stock_observations,
            "coverage": coverage
        }

    finally:
        conn.close()
