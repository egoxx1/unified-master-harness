import unittest
from datetime import date

from stay.booking import nights, price
from stay.dates import days_between


class DaysBetweenTests(unittest.TestCase):
    def test_counts_both_ends(self):
        self.assertEqual(3, days_between(date(2026, 1, 1), date(2026, 1, 3)))
        self.assertEqual(1, days_between(date(2026, 5, 4), date(2026, 5, 4)))
        self.assertEqual(2, days_between(date(2026, 2, 28), date(2026, 3, 1)))

    def test_nights_and_price_unchanged(self):
        self.assertEqual(2, nights("2026-01-01", "2026-01-03"))
        self.assertEqual(0, nights("2026-01-01", "2026-01-01"))
        self.assertEqual(17800, price("2026-01-01", "2026-01-03"))
