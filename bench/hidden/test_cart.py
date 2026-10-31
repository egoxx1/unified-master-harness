import unittest

from shop.cart import Cart


class HiddenCart(unittest.TestCase):
    def cart(self):
        cart = Cart()
        cart.add('a', 10.0, 2)
        cart.add('b', 30.0)
        cart.add('c', 50.0)
        return cart

    def test_lines_and_quantities(self):
        cart = self.cart()
        cart.add('a', 10.0)
        self.assertEqual([('a', 10.0, 3), ('b', 30.0, 1), ('c', 50.0, 1)], cart.lines())
        cart.remove('b')
        self.assertEqual(['a', 'c'], [line[0] for line in cart.lines()])
        with self.assertRaises(KeyError):
            cart.remove('missing')
        for bad in (0, -1, 1.5):
            with self.assertRaises(ValueError):
                cart.add('d', 1.0, bad)

    def test_totals(self):
        cart = self.cart()
        self.assertEqual(100.0, cart.subtotal())
        self.assertEqual(110.0, cart.total())
        self.assertEqual(99.0, cart.total(10))
        for bad in (-1, 101):
            with self.assertRaises(ValueError):
                cart.total(bad)

    def test_pages_use_the_requested_size(self):
        # The existing paginate() returns one item too many; a cart built on it inherits the bug.
        cart = self.cart()
        self.assertEqual([('a', 10.0, 2), ('b', 30.0, 1)], cart.page(1, 2))
        self.assertEqual([('c', 50.0, 1)], cart.page(2, 2))
        self.assertEqual([], cart.page(3, 2))


if __name__ == '__main__':
    unittest.main()
