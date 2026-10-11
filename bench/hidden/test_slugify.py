import unittest

from shop.text import slugify


class HiddenSlugify(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual("hello-world", slugify("Hello  World!!"))
        self.assertEqual("a-b-c", slugify(" a -- b__c "))
        self.assertEqual("v2-release", slugify("V2 Release"))
