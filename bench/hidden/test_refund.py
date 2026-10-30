import unittest

from store.catalog import load_catalog
from store.money import to_cents
from store.orders import order_total
from store.refunds import manual_refund, refund_amount


class RefundTests(unittest.TestCase):
    def test_reported_refund(self):
        self.assertEqual(1999, refund_amount(load_catalog(), "MUG", 1))

    def test_every_catalog_price_and_order(self):
        catalog = load_catalog()
        self.assertEqual({"MUG": 1999, "TEE": 435, "PEN": 29, "CAP": 1000, "BAG": 550},
                         {sku: p["price"] for sku, p in catalog.items()})
        self.assertEqual(1999 + 3 * 435 + 29, order_total(catalog, [("MUG", 1), ("TEE", 3), ("PEN", 1)]))
        self.assertEqual(87, refund_amount(catalog, "PEN", 3))
        self.assertEqual(1800, refund_amount(catalog, "MUG", 1, opened=True))

    def test_to_cents_is_exact_for_every_cent_amount(self):
        for cents in range(-10000, 10001):
            text = f"{'-' if cents < 0 else ''}{abs(cents) // 100}.{abs(cents) % 100:02d}"
            self.assertEqual(cents, to_cents(text), text)
        self.assertEqual(-510, manual_refund("-5.10"))
        self.assertEqual(1230, manual_refund("12.30"))


if __name__ == "__main__":
    unittest.main()
