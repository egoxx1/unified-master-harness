import unittest

from shop.text import initials


class InitialsTests(unittest.TestCase):
    def test_two_names(self):
        self.assertEqual("A.L.", initials("Ada Lovelace"))

    def test_hyphenated(self):
        self.assertEqual("J.-P.S.", initials("Jean-Paul Sartre"))
