import unittest

from shop.pagination import paginate


class HiddenPaginate(unittest.TestCase):
    def test_pages(self):
        items = list(range(1, 26))
        self.assertEqual(list(range(1, 11)), paginate(items, 1, 10))
        self.assertEqual(list(range(11, 21)), paginate(items, 2, 10))
        self.assertEqual(list(range(21, 26)), paginate(items, 3, 10))
        self.assertEqual([], paginate(items, 4, 10))
        with self.assertRaises(ValueError):
            paginate(items, 0, 10)
