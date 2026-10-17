#!/usr/bin/env python3

import unittest
from test.test_descend import LocalServers, make_config
from typing import List, Tuple
from urllib.parse import urljoin, urlsplit

import thor
from httplint.message import HttpMessageLinter

from redbot.resource import HttpResource
from redbot.resource.fetch import RedFetcher
from redbot.resource.link_parse import HTMLLinkParser

PAGE = "http://example.com/dir/page?q=1"
DEFAULT = "http://example.com/dir/x.js"


def parser_for(links: List[Tuple[str, str]]) -> Tuple[HttpMessageLinter, HTMLLinkParser]:
    "A real parser; links collects (tag, URI) as HttpResource.process_link would resolve them."

    def capture(base: str, link: str, tag: str, title: str) -> None:
        links.append((tag, urljoin(base, link)))

    message = HttpMessageLinter()
    message.headers.parsed.update({"content-type": ["text/html"]})
    message.base_uri = PAGE
    return message, HTMLLinkParser(message, [capture])


class TestBaseHref(unittest.TestCase):
    CASES = [
        ("no base", "", DEFAULT),
        ("absolute path", '<base href="/sub/">', "http://example.com/sub/x.js"),
        ("relative path", '<base href="sub/">', "http://example.com/dir/sub/x.js"),
        ("parent", '<base href="../up/">', "http://example.com/up/x.js"),
        ("absolute URI", '<base href="https://o.example/b/">', "https://o.example/b/x.js"),
        ("protocol-relative", '<base href="//o.example/b/">', "http://o.example/b/x.js"),
        ("empty", '<base href="">', DEFAULT),
        ("valueless", "<base href>", DEFAULT),
        ("query and fragment", '<base href="/sub/?a=1#frag">', "http://example.com/sub/x.js"),
        ("surrounding space", '<base href="  /sub/ ">', "http://example.com/sub/x.js"),
        ("uppercase", '<BASE HREF="/sub/">', "http://example.com/sub/x.js"),
        ("target only", '<base target="_blank">', DEFAULT),
        (
            "target then href",
            '<base target="_blank"><base href="/sub/">',
            "http://example.com/sub/x.js",
        ),
        ("javascript scheme", '<base href="javascript:alert(1)//">', DEFAULT),
        ("mixed-case javascript", '<base href="JavaScript:foo/">', DEFAULT),
        ("data scheme", '<base href="data:text/html,hi">', DEFAULT),
        ("invalid", '<base href="http://[bad/">', DEFAULT),
        ("first base wins", '<base href="/a/"><base href="/b/">', "http://example.com/a/x.js"),
        ("relative second base", '<base href="/a/"><base href="b/">', "http://example.com/a/x.js"),
        ("invalid first base wins", '<base href="http://[bad/"><base href="/b/">', DEFAULT),
    ]

    def test_base_resolution(self) -> None:
        for name, base, expected in self.CASES:
            with self.subTest(name):
                links: List[Tuple[str, str]] = []
                _message, parser = parser_for(links)
                parser.feed(f'<head>{base}<script src="x.js"></script></head>')
                self.assertEqual(links, [("script", expected)])

    def test_absolute_links_unchanged(self) -> None:
        links: List[Tuple[str, str]] = []
        _message, parser = parser_for(links)
        parser.feed('<base href="/sub/"><script src="/abs.js"></script>')
        self.assertEqual(links, [("script", "http://example.com/abs.js")])

    def test_base_affects_later_links(self) -> None:
        links: List[Tuple[str, str]] = []
        _message, parser = parser_for(links)
        parser.feed('<script src="x.js"></script><base href="/sub/"><script src="y.js"></script>')
        self.assertEqual(
            links,
            [("script", DEFAULT), ("script", "http://example.com/sub/y.js")],
        )

    def test_base_is_stored_resolved(self) -> None:
        message, parser = parser_for([])
        parser.feed('<base href="/sub/">')
        self.assertEqual(message.base_uri, "http://example.com/sub/")


class RelativeBaseServers(LocalServers):
    "Serves a page under /dir/ with a relative <base>."

    page_path = "/dir/page"

    def page(self) -> str:
        return (
            '<html><head><base href="/sub/">'
            '<script src="x.js"></script><script src="/abs.js"></script>'
            "</head><body>hi</body></html>"
        )


class TestRelativeBaseDescend(unittest.TestCase):
    def test_links_fetched_from_base(self) -> None:
        saved_check_ip = RedFetcher.client.check_ip
        RedFetcher.client.check_ip = None
        servers = RelativeBaseServers()
        timed_out: List[bool] = []

        def give_up() -> None:
            timed_out.append(True)
            thor.stop()

        try:
            same, _other = servers.ports
            resource = HttpResource(make_config()["redbot"], descend=True)
            resource.set_request(f"http://127.0.0.1:{same}/dir/page")
            resource.on("check_done", thor.stop)
            timeout = thor.schedule(20, give_up)
            resource.check()
            thor.run()
            timeout.delete()
        finally:
            servers.close()
            RedFetcher.client.check_ip = saved_check_ip
        self.assertFalse(timed_out, "test stalled")
        self.assertTrue(resource.check_done)
        by_path = {urlsplit(str(r.request.uri)).path: r for (r, _tag) in resource.linked}
        self.assertEqual(sorted(by_path), ["/abs.js", "/sub/x.js"])
        for linked in by_path.values():
            self.assertIsNone(linked.fetch_error)
            self.assertTrue(linked.response.complete)
        self.assertEqual(by_path["/sub/x.js"].request.uri, f"http://127.0.0.1:{same}/sub/x.js")
        self.assertEqual(
            {path for (_port, path) in servers.seen}, {"/dir/page", "/sub/x.js", "/abs.js"}
        )
        self.assertEqual(resource.response.base_uri, f"http://127.0.0.1:{same}/sub/")


if __name__ == "__main__":
    unittest.main()
