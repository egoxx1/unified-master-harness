import unittest

from stay.booking import nights, price
from stay.dates import parse


class StayTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual((2026, 1, 3), (parse("2026-01-03").year, parse("2026-01-03").month, parse("2026-01-03").day))

    def test_nights(self):
        self.assertEqual(2, nights("2026-01-01", "2026-01-03"))
        self.assertEqual(1, nights("2026-02-28", "2026-03-01"))

    def test_price(self):
        self.assertEqual(17800, price("2026-01-01", "2026-01-03"))
