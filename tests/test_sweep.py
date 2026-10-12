
import unittest
from unittest.mock import Mock, patch

import sweep


class TestInventorySweep(unittest.TestCase):

    @patch("sweep.request_with_retry")
    def test_duplicate_skus_are_deduplicated(self, mock_request):
        """Repeated SKUs across pages should appear only once."""
        mock_request.side_effect = [
            Mock(
                status_code=200,
                headers={},
                json=lambda: {
                    "items": [
                        {
                            "sku_id": "SKU-001",
                            "name": "Milk",
                            "in_stock": True,
                            "qty": 2,
                        }
                    ],
                    "partial": False,
                    "next_cursor": "15",
                    "meta": {"source": "origin"},
                },
                raise_for_status=lambda: None,
            ),
            Mock(
                status_code=200,
                headers={},
                json=lambda: {
                    "items": [
                        {
                            "sku_id": "SKU-001",
                            "name": "Milk",
                            "in_stock": True,
                            "qty": 2,
                        },
                        {
                            "sku_id": "SKU-002",
                            "name": "Bread",
                            "in_stock": False,
                            "qty": 0,
                        },
                    ],
                    "partial": False,
                    "next_cursor": None,
                    "meta": {"source": "origin"},
                },
                raise_for_status=lambda: None,
            ),
        ]

        result = sweep.get_inventory(
            "MUM-001",
            "2026-09-28T04:30:00Z",
        )

        self.assertTrue(result["complete"])
        self.assertEqual(len(result["items"]), 2)

        sku_ids = {
            item["sku_id"]
            for item in result["items"]
        }
        self.assertEqual(sku_ids, {"SKU-001", "SKU-002"})

    @patch("sweep.request_with_retry")
    def test_partial_response_is_incomplete(self, mock_request):
        """A partial snapshot must not be treated as complete."""
        mock_request.return_value = Mock(
            status_code=200,
            headers={},
            json=lambda: {
                "items": [],
                "partial": True,
                "next_cursor": None,
                "meta": {"source": "origin"},
            },
            raise_for_status=lambda: None,
        )

        result = sweep.get_inventory(
            "DEL-004",
            "2026-09-28T10:30:00Z",
        )

        self.assertFalse(result["complete"])
        self.assertEqual(result["reason"], "partial response")

    @patch("sweep.request_with_retry")
    def test_edge_response_is_incomplete(self, mock_request):
        """A soft-ban response must not be trusted as inventory."""
        mock_request.return_value = Mock(
            status_code=200,
            headers={},
            json=lambda: {
                "items": [],
                "partial": False,
                "next_cursor": None,
                "meta": {"source": "edge"},
            },
            raise_for_status=lambda: None,
        )

        result = sweep.get_inventory(
            "MUM-001",
            "2026-09-28T04:30:00Z",
        )

        self.assertFalse(result["complete"])
        self.assertIn("edge", result["reason"])


if __name__ == "__main__":
    unittest.main()
