import unittest

from shop.pagination import page_count
from shop.pricing import total, with_tax
from shop.text import truncate


class ShopTests(unittest.TestCase):
    def test_page_count(self):
        self.assertEqual(3, page_count(25, 10))

    def test_pricing(self):
        self.assertEqual(11.0, with_tax(10))
        self.assertEqual(3.3, total([1.1, 2.2]))

    def test_truncate(self):
        self.assertEqual("hello", truncate("hello", 10))
        self.assertEqual("hel...", truncate("hello world", 6))


if __name__ == "__main__":
    unittest.main()
