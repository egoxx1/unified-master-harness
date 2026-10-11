import unittest

from shop.pricing import discount


class HiddenDiscount(unittest.TestCase):
    def test_discount(self):
        self.assertEqual(90.0, discount(100, 10))
        self.assertEqual(66.66, discount(99.99, 33.33))
        self.assertEqual(100, discount(100, 0))
        self.assertEqual(0, discount(100, 100))
        for bad in (-1, 101):
            with self.assertRaises(ValueError):
                discount(100, bad)
