import unittest

from store.catalog import load_catalog
from store.money import format_cents, to_cents
from store.orders import order_total
from store.pricing import apply_discount
from store.refunds import refund_amount


class StoreTests(unittest.TestCase):
    def test_money(self):
        self.assertEqual(1000, to_cents("10.00"))
        self.assertEqual(550, to_cents("5.50"))
        self.assertEqual("$19.99", format_cents(1999))
        self.assertEqual("-$0.05", format_cents(-5))

    def test_discount(self):
        self.assertEqual(900, apply_discount(1000, 10))
        with self.assertRaises(ValueError):
            apply_discount(1000, 101)

    def test_orders_and_refunds(self):
        catalog = load_catalog()
        self.assertEqual(1000, catalog["CAP"]["price"])
        self.assertEqual(2550, order_total(catalog, [("CAP", 2), ("BAG", 1)]))
        self.assertEqual(1000, refund_amount(catalog, "CAP", 1))
        self.assertEqual(900, refund_amount(catalog, "CAP", 1, opened=True))


if __name__ == "__main__":
    unittest.main()
