import unittest

from shop.pagination import page_count, paginate
from shop.text import slugify, truncate


class HiddenListing(unittest.TestCase):
    def test_page_size(self):
        items = list(range(25))
        self.assertEqual(10, len(paginate(items, 2, 10)))
        self.assertEqual(5, len(paginate(items, 3, 10)))
        self.assertEqual(3, page_count(25, 10))

    def test_slug(self):
        self.assertEqual('summer-sale', slugify('Summer  Sale!!'))
        self.assertEqual('a-b', slugify(' A -- B '))
        self.assertEqual('t-shirt-xl', slugify('T-shirt (XL)'))

    def test_truncate_never_exceeds_limit(self):
        for limit in range(0, 8):
            out = truncate('hello world', limit)
            self.assertLessEqual(len(out), limit, (limit, out))
        self.assertEqual('hel...', truncate('hello world', 6))
        self.assertEqual('hello', truncate('hello', 5))


if __name__ == '__main__':
    unittest.main()
