import unittest
from pathlib import Path


class HiddenReadme(unittest.TestCase):
    def test_typo_fixed(self):
        text = Path("README.md").read_text()
        self.assertIn("when we receive payment confirmation", text)
        self.assertNotIn("recieve", text)
