import os
import unittest
from unittest import mock

from alerts.client import build_request
from alerts.format import format_alert


class AlertTests(unittest.TestCase):
    def test_format(self):
        self.assertEqual("[WARNING] disk 91% full", format_alert("warning", " disk 91% full "))
        with self.assertRaises(ValueError):
            format_alert("debug", "x")

    @mock.patch.dict(os.environ, {"ALERTS_API_TOKEN": "t"})
    def test_request_body(self):
        self.assertEqual({"text": "[CRITICAL] db down"}, build_request("critical", "db down")["body"])

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_missing_token_is_a_clear_error(self):
        with self.assertRaises(RuntimeError):
            build_request("info", "x")
