import unittest

from store.catalog import load_catalog
from store.orders import order_total
from store.pricing import apply_discount
from store.promotions import promo_price
from store.report import daily_report


class PercentDiscountTests(unittest.TestCase):
    def test_apply_discount_takes_percent(self):
        self.assertEqual(900, apply_discount(1000, 10))
        self.assertEqual(990, apply_discount(1000, 1))
        self.assertEqual(1699, apply_discount(1999, 15))
        self.assertEqual(1000, apply_discount(1000, 0))
        self.assertEqual(0, apply_discount(1000, 100))
        for bad in (-1, 101, 150):
            with self.assertRaises(ValueError):
                apply_discount(1000, bad)

    def test_member_tiers_keep_their_discount(self):
        catalog = load_catalog()
        self.assertEqual(1900, order_total(catalog, [("CAP", 2)], "silver"))
        self.assertEqual(1800, order_total(catalog, [("CAP", 2)], "gold"))
        self.assertEqual(["order 1: $18.00", "order 2: $11.00", "total: $29.00"],
                         daily_report(catalog, [(1, [("CAP", 2)], "gold"), (2, [("BAG", 2)], None)]))

    def test_promotions_keep_their_discount(self):
        self.assertEqual(1700, promo_price(2000, "SPRING"))
        self.assertEqual(1400, promo_price(2000, "STAFF"))


if __name__ == "__main__":
    unittest.main()
