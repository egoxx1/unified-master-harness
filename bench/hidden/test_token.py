import importlib
import os
import sys
import unittest
from unittest import mock


def fresh_client():
    for name in [m for m in sys.modules if m == "alerts" or m.startswith("alerts.")]:
        del sys.modules[name]
    return importlib.import_module("alerts.client")


class TokenTests(unittest.TestCase):
    def test_imports_without_token(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            fresh_client()  # the KeyError at import time is the reported failure

    def test_sends_token_from_environment(self):
        with mock.patch.dict(os.environ, {"ALERTS_API_TOKEN": "tok_test_123"}):
            client = fresh_client()
            self.assertEqual("Bearer tok_test_123", client.build_request("info", "ok")["headers"]["Authorization"])

    def test_missing_token_fails_when_sending(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            client = fresh_client()
            with self.assertRaises(Exception):
                client.build_request("info", "ok")
