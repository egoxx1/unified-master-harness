import unittest

from alerts.client import build_request
from alerts.format import format_alert


class AlertTests(unittest.TestCase):
    def test_format(self):
        self.assertEqual("[WARNING] disk 91% full", format_alert("warning", " disk 91% full "))
        with self.assertRaises(ValueError):
            format_alert("debug", "x")

    def test_request_body(self):
        self.assertEqual({"text": "[CRITICAL] db down"}, build_request("critical", "db down")["body"])
