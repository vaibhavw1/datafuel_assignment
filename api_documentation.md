# API Documentation

## Overview

The OSA API returns the city-level On-Shelf Availability (OSA) percentage for a selected date. It uses inventory data stored in the local SQLite database.

## Endpoint

`GET /osa`

### Query Parameters

| Parameter | Required | Description |
|---|---|---|
| `city` | Yes | City to check: `Mumbai`, `Delhi`, or `Bengaluru` |
| `date` | No | Date in `YYYY-MM-DD` format, interpreted in Indian Standard Time (IST). If omitted, the API uses yesterday's date in IST. |

### Example Request

```http
GET http://127.0.0.1:8000/osa?city=Mumbai&date=2026-09-28
```

You can also open the endpoint in your browser after starting the FastAPI application.

## Response

When inventory data is available, the endpoint returns a response containing the OSA percentage and data coverage.

Example response structure:

```json
{
  "city": "Mumbai",
  "date": "2026-09-28",
  "status": "ok",
  "osa_pct": 87.65,
  "total_observations": 251,
  "in_stock_observations": 220,
  "coverage": {
    "expected_stores": 9,
    "complete_stores": 9,
    "incomplete_stores": 0,
    "stores_with_inventory": 9
  }
}
```

The numbers above are an example of the response structure. Use the actual output from your latest run when demonstrating the API.

### Response Fields

- `city`: City requested by the user.
- `date`: Date for which OSA was calculated.
- `status`: `ok` when usable inventory data is available; `no_data` when there are no usable observations.
- `osa_pct`: OSA percentage, rounded to two decimal places. It is `null` when no usable data exists.
- `total_observations`: Total inventory observations included in the calculation.
- `in_stock_observations`: Number of observations marked as in stock.
- `coverage`: Summary of the expected stores, completed stores, incomplete stores, and stores with inventory data.

## OSA Calculation

OSA is calculated using all included inventory observations rather than taking a simple average of store-level percentages.

\[
\text{OSA (\%)} =
\frac{\text{In-stock observations}}
{\text{Total observations}} \times 100
\]

Only usable observations from complete sweeps are included. Incomplete sweeps should not be treated as proof that products are out of stock.

## Error Handling

- **HTTP 400 — Invalid city:** Returned when the city is not one of the supported cities.
- **HTTP 400 — Invalid date:** Returned when the date is not in the expected `YYYY-MM-DD` format or is not a valid calendar date.
- **`no_data` status:** Returned when no usable inventory observations are available for the requested city and date. The OSA percentage is `null`.

## Running the API

From the project directory, activate the virtual environment and run:

```bash
uvicorn app:app --reload
```

The API will normally be available at:

`http://127.0.0.1:8000`

FastAPI's interactive documentation is available at:

`http://127.0.0.1:8000/docs`

