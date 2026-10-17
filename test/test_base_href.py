#!/usr/bin/env python3

import unittest
from test.test_descend import LocalServers, check_locally, make_config
from typing import List, Tuple
from urllib.parse import urljoin, urlsplit

from httplint.message import HttpMessageLinter

from redbot.resource import HttpResource
from redbot.resource.link_parse import HTMLLinkParser, resolve_base

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
        ("parent", '<base href="../x/">', "http://example.com/x/x.js"),
        ("absolute URI", '<base href="https://o.example/b/">', "https://o.example/b/x.js"),
        ("protocol-relative", '<base href="//o.example/b/">', "http://o.example/b/x.js"),
        ("empty", '<base href="">', DEFAULT),
        ("valueless", "<base href>", DEFAULT),
        ("query and fragment", '<base href="/sub/?a=1#frag">', "http://example.com/sub/x.js"),
        ("uppercase", '<BASE HREF="/sub/">', "http://example.com/sub/x.js"),
        ("target only", '<base target="_blank">', DEFAULT),
        (
            "target then href",
            '<base target="_blank"><base href="/sub/">',
            "http://example.com/sub/x.js",
        ),
        ("javascript scheme", '<base href="javascript:alert(1)//">', DEFAULT),
        ("data scheme", '<base href="data:text/html,hi">', DEFAULT),
        ("invalid", '<base href="http://[bad/">', DEFAULT),
        ("first base wins", '<base href="/a/"><base href="/b/">', "http://example.com/a/x.js"),
        ("invalid first base wins", '<base href="http://[bad/"><base href="/b/">', DEFAULT),
    ]

    def test_base_resolution(self) -> None:
        for name, base, expected in self.CASES:
            with self.subTest(name):
                links: List[Tuple[str, str]] = []
                _message, parser = parser_for(links)
                parser.feed(f'<head>{base}<script src="x.js"></script></head>')
                self.assertEqual(links, [("script", expected)])

    def test_base_affects_later_links(self) -> None:
        links: List[Tuple[str, str]] = []
        _message, parser = parser_for(links)
        parser.feed('<script src="x.js"></script><base href="/sub/"><script src="y.js"></script>')
        self.assertEqual(
            links,
            [("script", DEFAULT), ("script", "http://example.com/sub/y.js")],
        )

    def test_strips_ascii_whitespace(self) -> None:
        self.assertEqual(resolve_base(PAGE, " \t\n/sub/\f\r "), "http://example.com/sub/")
        # browsers keep non-ASCII whitespace such as NBSP
        self.assertEqual(resolve_base(PAGE, "\u00a0/sub/"), "http://example.com/dir/\u00a0/sub/")
        links: List[Tuple[str, str]] = []
        _message, parser = parser_for(links)
        parser.feed('<base href="\u00a0/sub/"><script src="x.js"></script>')
        self.assertEqual(links, [("script", "http://example.com/dir/\u00a0/sub/x.js")])

    def test_decoy_base_ignored(self) -> None:
        for tag in ["template", "svg", "math", "noscript"]:
            with self.subTest(tag):
                links: List[Tuple[str, str]] = []
                _message, parser = parser_for(links)
                parser.feed(
                    f'<head><{tag}><base href="/decoy/"></{tag}><base href="/real/">'
                    '<script src="x.js"></script></head>'
                )
                self.assertEqual(links, [("script", "http://example.com/real/x.js")])

    def test_inert_tags_harmless(self) -> None:
        for name, markup in [
            ("closed noscript", "<noscript><img src='n.gif'></noscript>"),
            ("nested", "<template><template></template><base href='/decoy/'></template>"),
            ("stray end tags", "</svg></template></noscript>"),
            ("self-closing", "<svg/><math/>"),
            ("closed svg in body", "<body><svg><path/></svg>"),
        ]:
            with self.subTest(name):
                links: List[Tuple[str, str]] = []
                _message, parser = parser_for(links)
                parser.feed(f'{markup}<base href="/sub/"><script src="x.js"></script>')
                self.assertEqual(links[-1], ("script", "http://example.com/sub/x.js"))

    def test_unclosed_inert_tag(self) -> None:
        # As in a browser, where an unclosed <svg>, <template> or <noscript> (scripts enabled)
        # holds the rest of the document.
        links: List[Tuple[str, str]] = []
        _message, parser = parser_for(links)
        parser.feed('<noscript><base href="/sub/"><script src="x.js"></script>')
        self.assertEqual(links, [("script", DEFAULT)])


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
        servers = RelativeBaseServers()
        try:
            same, _other = servers.ports
            resource = HttpResource(make_config()["redbot"], descend=True)
            resource.set_request(f"http://127.0.0.1:{same}/dir/page")
            self.assertTrue(check_locally(resource), "test stalled")
        finally:
            servers.close()
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
