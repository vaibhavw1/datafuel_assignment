
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as osa_app


class TestOSAAPI(unittest.TestCase):

    def setUp(self):
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".db",
            delete=False
        )
        self.db_path = temp_file.name
        temp_file.close()

        self.connections = []

        self.conn = self.new_connection()

        self.conn.executescript("""
            CREATE TABLE stores (
                store_id TEXT PRIMARY KEY,
                city TEXT NOT NULL,
                name TEXT NOT NULL,
                is_active INTEGER NOT NULL,
                is_serviceable INTEGER NOT NULL
            );

            CREATE TABLE sweeps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id TEXT NOT NULL,
                as_of TEXT NOT NULL,
                complete INTEGER NOT NULL,
                reason TEXT,
                UNIQUE(store_id, as_of)
            );

            CREATE TABLE inventory (
                store_id TEXT NOT NULL,
                as_of TEXT NOT NULL,
                sku_id TEXT NOT NULL,
                name TEXT NOT NULL,
                in_stock INTEGER NOT NULL,
                qty INTEGER,
                price REAL,
                observed_at TEXT,
                PRIMARY KEY (store_id, as_of, sku_id)
            );
        """)
        self.conn.commit()

        self.db_patcher = patch(
            "app.get_connection",
            side_effect=self.new_connection
        )
        self.db_patcher.start()

        self.client = TestClient(osa_app.app)

    def new_connection(self):
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        self.connections.append(conn)
        return conn

    def tearDown(self):
        self.client.close()
        self.db_patcher.stop()

        for conn in self.connections:
            try:
                conn.close()
            except sqlite3.Error:
                pass

        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def add_store(self, store_id, city="Mumbai", active=1):
        self.conn.execute(
            """
            INSERT INTO stores
            (store_id, city, name, is_active, is_serviceable)
            VALUES (?, ?, ?, ?, 1)
            """,
            (store_id, city, store_id, active)
        )
        self.conn.commit()

    def add_sweep(self, store_id, as_of, complete=1):
        self.conn.execute(
            """
            INSERT INTO sweeps
            (store_id, as_of, complete)
            VALUES (?, ?, ?)
            """,
            (store_id, as_of, complete)
        )
        self.conn.commit()

    def add_item(self, store_id, as_of, sku_id, in_stock):
        self.conn.execute(
            """
            INSERT INTO inventory
            (store_id, as_of, sku_id, name, in_stock)
            VALUES (?, ?, ?, ?, ?)
            """,
            (store_id, as_of, sku_id, sku_id, in_stock)
        )
        self.conn.commit()

    def test_osa_uses_weighted_observations(self):
        self.add_store("MUM-001")
        as_of = "2026-09-28T04:30:00Z"
        self.add_sweep("MUM-001", as_of)

        self.add_item("MUM-001", as_of, "SKU-1", 1)
        self.add_item("MUM-001", as_of, "SKU-2", 0)
        self.add_item("MUM-001", as_of, "SKU-3", 1)
        self.add_item("MUM-001", as_of, "SKU-4", 1)

        response = self.client.get(
            "/osa?city=Mumbai&date=2026-09-28"
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["osa_pct"], 75.0)
        self.assertEqual(data["total_observations"], 4)
        self.assertEqual(data["in_stock_observations"], 3)

        coverage = data["coverage"]
        self.assertEqual(coverage["expected_stores"], 1)
        self.assertEqual(coverage["complete_stores"], 1)
        self.assertEqual(coverage["incomplete_stores"], 0)
        self.assertEqual(coverage["stores_with_inventory"], 1)

    def test_utc_timestamp_is_converted_to_ist_date(self):
        self.add_store("MUM-001")
        as_of = "2026-09-27T19:00:00Z"

        self.add_sweep("MUM-001", as_of)
        self.add_item("MUM-001", as_of, "SKU-1", 1)

        response = self.client.get(
            "/osa?city=Mumbai&date=2026-09-28"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["osa_pct"], 100.0)

    def test_no_observations_returns_no_data(self):
        self.add_store("MUM-001")
        self.add_sweep(
            "MUM-001",
            "2026-09-28T04:30:00Z"
        )

        response = self.client.get(
            "/osa?city=Mumbai&date=2026-09-28"
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "no_data")
        self.assertIsNone(data["osa_pct"])
        self.assertEqual(data["total_observations"], 0)

    def test_invalid_date_returns_400(self):
        response = self.client.get(
            "/osa?city=Mumbai&date=28-09-2026"
        )

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
