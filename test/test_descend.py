#!/usr/bin/env python3

import unittest
from configparser import ConfigParser
from typing import Dict, List, Tuple
from unittest import mock

from redbot.resource import HttpResource, origin_of

CREDENTIALS = [
    ("Authorization", "Bearer secret"),
    ("Cookie", "session=secret"),
    ("Proxy-Authorization", "Basic c2VjcmV0"),
]
OTHER_HEADERS = [("Accept-Language", "en")]


class TestOriginOf(unittest.TestCase):
    def test_default_ports_are_normalised(self):
        self.assertEqual(origin_of("http://example.com/a"), origin_of("http://EXAMPLE.com:80/b"))
        self.assertEqual(origin_of("https://example.com/"), origin_of("https://example.com:443/"))

    def test_scheme_host_and_port_all_matter(self):
        base = origin_of("https://example.com/")
        self.assertNotEqual(base, origin_of("http://example.com/"))
        self.assertNotEqual(base, origin_of("https://example.org/"))
        self.assertNotEqual(base, origin_of("https://www.example.com/"))
        self.assertNotEqual(base, origin_of("https://example.com:8443/"))

    def test_no_origin(self):
        self.assertIsNone(origin_of("/relative"))
        self.assertIsNone(origin_of("data:text/plain,hi"))
        self.assertIsNone(origin_of("http://example.com:notaport/"))


class TestDescend(unittest.TestCase):
    def setUp(self) -> None:
        conf = ConfigParser()
        conf.add_section("redbot")
        self.config = conf["redbot"]

    def descend(self, top_uri: str, links: List[str]) -> Dict[str, HttpResource]:
        "Run process_link for each link on a fake page, without any network access."
        resource = HttpResource(self.config, descend=True)
        resource.set_request(top_uri, headers=CREDENTIALS + OTHER_HEADERS)
        with mock.patch.object(HttpResource, "check"):
            for link in links:
                resource.process_link(top_uri, link, "script", "")
        return {linked.request.uri: linked for (linked, _tag) in resource.linked}

    @staticmethod
    def header_names(resource: HttpResource) -> List[str]:
        return [n.lower() for (n, _v) in resource.request.headers.text]

    def test_same_origin_link_gets_credentials(self):
        linked = self.descend("https://example.com/page", ["/app.js", "https://example.com:443/b.js"])
        self.assertEqual(len(linked), 2)
        for resource in linked.values():
            self.assertEqual(
                sorted(self.header_names(resource)),
                sorted(n.lower() for (n, _v) in CREDENTIALS + OTHER_HEADERS),
            )

    def test_cross_origin_links_do_not_get_credentials(self):
        cross = [
            "https://cdn.example.net/app.js",
            "https://www.example.com/app.js",  # different host
            "https://example.com:8443/app.js",  # different port
            "http://example.com/app.js",  # different scheme
        ]
        linked = self.descend("https://example.com/page", cross)
        self.assertEqual(len(linked), len(cross))
        for uri, resource in linked.items():
            names = self.header_names(resource)
            self.assertEqual(names, ["accept-language"], uri)

    def test_mixed_links(self):
        linked = self.descend(
            "https://example.com/page", ["/local.js", "https://tracker.example.net/t.js"]
        )
        self.assertIn("cookie", self.header_names(linked["https://example.com/local.js"]))
        self.assertNotIn("cookie", self.header_names(linked["https://tracker.example.net/t.js"]))

    def test_linked_resources_skip_active_checks(self):
        linked = self.descend("https://example.com/page", ["/app.js"])["https://example.com/app.js"]
        self.assertFalse(linked.active_checks_enabled)
        linked.response.complete = True
        with mock.patch("redbot.resource.fetch.RedFetcher.check") as check:
            linked.run_active_checks()
        check.assert_not_called()
        self.assertTrue(linked.check_done)
        self.assertFalse(any(s.fetch_started for s in linked.subreqs.values()))

    def test_top_level_resource_still_runs_active_checks(self):
        resource = HttpResource(self.config, descend=True)
        self.assertTrue(resource.active_checks_enabled)
        resource.set_request("https://example.com/page")
        resource.response.complete = True
        started: List[Tuple[str, str]] = []
        with mock.patch(
            "redbot.resource.active_check.base.SubRequest.check",
            lambda self: started.append((self.check_id, "")),
        ):
            resource.run_active_checks()
        self.assertEqual(len(started), len(resource.subreqs))
        self.assertGreater(len(started), 0)


if __name__ == "__main__":
    unittest.main()
