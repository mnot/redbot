#!/usr/bin/env python3

"""
max_links limits the links that are checked, not the links on the page (mnot/redbot#522).
"""

import unittest
from configparser import ConfigParser
from unittest import mock

from redbot.resource import HttpResource

BASE = "http://example.com/"


class TestMaxLinks(unittest.TestCase):
    def resource(self, max_links: int) -> HttpResource:
        conf = ConfigParser()
        conf.read_dict({"redbot": {"max_links": str(max_links)}})
        resource = HttpResource(conf["redbot"], descend=True)
        resource.set_request(BASE)
        return resource

    def feed(self, resource: HttpResource, links: list[tuple[str, str]]) -> None:
        with mock.patch.object(HttpResource, "check"):
            for tag, link in links:
                resource.process_link(BASE, link, tag, "")

    def test_anchors_do_not_use_up_the_budget(self):
        resource = self.resource(3)
        self.feed(resource, [("a", f"/page{i}") for i in range(10)] + [("img", "/logo.png")])
        self.assertEqual([tag for _, tag in resource.linked], ["img"])
        self.assertEqual(len(resource.links["a"]), 10)

    def test_checked_links_are_still_capped(self):
        resource = self.resource(3)
        self.feed(resource, [("img", f"/image{i}.png") for i in range(10)])
        self.assertEqual(len(resource.linked), 3)

    def test_repeated_links_are_checked_once(self):
        resource = self.resource(3)
        self.feed(resource, [("img", "/logo.png")] * 5)
        self.assertEqual(len(resource.linked), 1)
        self.assertEqual(resource.link_count, 1)


if __name__ == "__main__":
    unittest.main()
