#!/usr/bin/env python3

import re
import unittest
from configparser import ConfigParser
from typing import Dict, List, Optional, Tuple
from unittest import mock
from urllib.parse import urlsplit

import thor
import thor.http
from httplint.util import iri_to_uri
from thor.http.error import UrlError
from thor.http.uri import parse_uri

from redbot.formatter.html import TableHtmlFormatter
from redbot.resource import HttpResource, origin_of
from redbot.resource.fetch import RedFetcher

CREDENTIALS = [
    ("Authorization", "Bearer secret"),
    ("Cookie", "session=secret"),
    ("Proxy-Authorization", "Basic c2VjcmV0"),
]
OTHER_HEADERS = [("Accept-Language", "en")]
TOP = "https://example.com/page"


def host_rewriting_normaliser(iri: str) -> str:
    "What httplint 2026.10.1 did with non-ASCII userinfo: IDNA-encode it into the host."
    rewrites = {
        "https://é@example.com/x.js": "https://xn--@example-90a.com/x.js",
        "https://bücher@example.com/x.js": "https://xn--bcher@example-wob.com/x.js",
        # ASCII link text naming the page's host, so the comparison can't fail closed by accident
        "https://rewritten@example.com/x.js": "https://rewritten@example.net/x.js",
    }
    return rewrites.get(iri) or iri_to_uri(iri)


def make_config(**values: str) -> ConfigParser:
    # enable_local_access: the fetcher's HTTP client is shared by every HttpResource in the process,
    # and the first one built without it installs a public-addresses-only check on that client.
    conf = ConfigParser()
    conf.read_dict({"redbot": {"enable_local_access": "yes", **values}})
    return conf


class TestOriginOf(unittest.TestCase):
    """origin_of gets the (already normalised) request URI, as set by set_request."""

    def test_thor_parse_uri_shape(self):
        # origin_of relies on this (internal) return shape; if thor changes it, fail loudly here
        # rather than silently dropping credentials from every linked resource.
        self.assertEqual(
            parse_uri(b"https://user@Example.com:8443/a/b?q=1"),
            ("https", "Example.com", 8443, b"Example.com:8443", b"/a/b?q=1"),
        )
        self.assertEqual(
            origin_of("https://user@Example.com:8443/a/b?q=1"), ("https", "example.com", 8443)
        )

    @staticmethod
    def normalised(iri: str) -> Optional[Tuple[str, str, int]]:
        resource = HttpResource(make_config()["redbot"])
        resource.set_request(iri)
        return origin_of(resource.request.uri)

    def test_same_origin_variants(self):
        base = self.normalised("https://example.com/a")
        self.assertEqual(base, ("https", "example.com", 443))
        for iri in [
            "https://EXAMPLE.com/b",
            "https://Example.COM:443/b",
            "https://user@example.com/b",
            "https://example.com",
            "https://example.com/b?q#frag",
        ]:
            self.assertEqual(self.normalised(iri), base, iri)
        self.assertEqual(self.normalised("http://Example.com:80/"), ("http", "example.com", 80))

    def test_different_origins(self):
        base = self.normalised("https://example.com/")
        for iri in [
            "http://example.com/",
            "https://example.org/",
            "https://www.example.com/",
            "https://example.com:8443/",
            "https://example.com.evil.net/",
        ]:
            self.assertNotEqual(self.normalised(iri), base, iri)

    def test_punycode_and_unicode_hosts_agree(self):
        punycode = self.normalised("https://xn--bcher-kva.example/")
        self.assertIsNotNone(punycode)
        self.assertEqual(self.normalised("https://bücher.example/"), punycode)
        self.assertEqual(self.normalised("https://BÜCHER.example:443/"), punycode)

    def test_userinfo_does_not_change_the_origin(self) -> None:
        # httplint percent-encodes non-ASCII userinfo; the host is untouched.
        base = self.normalised("https://example.com/")
        for iri in [
            "https://é@example.com/x.js",
            "https://bücher@example.com/x.js",
            "https://user:pé@example.com/x.js",
            "https://user:pass@example.com/x.js",
        ]:
            self.assertEqual(self.normalised(iri), base, iri)

    def test_origin_follows_the_normalised_uri(self) -> None:
        # If normalisation rewrites the host, origin_of must follow the rewritten URI (which is
        # what's fetched), not the link text. httplint no longer does this, so simulate it.
        base = self.normalised("https://example.com/")
        with mock.patch("httplint.message.iri_to_uri", host_rewriting_normaliser):
            self.assertEqual(
                self.normalised("https://é@example.com/x.js"), ("https", "example-90a.com", 443)
            )
            self.assertNotEqual(self.normalised("https://é@example.com/x.js"), base)
            self.assertNotEqual(self.normalised("https://bücher@example.com/x.js"), base)

    def test_undeterminable_origins_are_none(self):
        for uri in [None, "", "/relative", "data:text/plain,hi", "ftp://example.com/"]:
            self.assertIsNone(origin_of(uri), uri)
        for iri in [
            "http://example.com:notaport/",
            "https://example.com:0/",
            "https://example.com.:443/",  # trailing dot: thor rejects the empty label
            "https://exa mple.com/",
        ]:
            self.assertIsNone(self.normalised(iri), iri)


class TestDescendHeaders(unittest.TestCase):
    """Run process_link on a fake page; URI normalisation is real, the network is not."""

    def descend(self, links: List[str], top: str = TOP) -> Dict[str, HttpResource]:
        resource = HttpResource(make_config()["redbot"], descend=True)
        resource.set_request(top, headers=CREDENTIALS + OTHER_HEADERS)
        with mock.patch.object(HttpResource, "check"):
            for link in links:
                resource.process_link(top, link, "script", "")
        return {str(linked.request.uri): linked for (linked, _tag) in resource.linked}

    @staticmethod
    def header_names(resource: HttpResource) -> List[str]:
        return sorted(n.lower() for (n, _v) in resource.request.headers.text)

    def test_same_origin_links_get_credentials(self):
        all_names = sorted(n.lower() for (n, _v) in CREDENTIALS + OTHER_HEADERS)
        linked = self.descend(
            [
                "/app.js",
                "https://example.com:443/b.js",
                "https://EXAMPLE.com/c.js",
                "https://user@example.com/d.js",
            ]
        )
        self.assertEqual(len(linked), 4)
        for uri, resource in linked.items():
            self.assertEqual(self.header_names(resource), all_names, uri)

    def test_credential_values_are_forwarded_intact(self):
        resource = self.descend(["/app.js"])["https://example.com/app.js"]
        self.assertEqual(
            dict(resource.request.headers.text),
            dict(CREDENTIALS + OTHER_HEADERS),
        )

    def test_cross_origin_links_do_not_get_credentials(self):
        cross = [
            "https://cdn.example.net/app.js",
            "https://www.example.com/app.js",
            "https://example.com:8443/app.js",
            "http://example.com/app.js",
            "//cdn2.example.net/app.js",
        ]
        linked = self.descend(cross)
        self.assertEqual(len(linked), len(cross))
        for uri, resource in linked.items():
            self.assertEqual(self.header_names(resource), ["accept-language"], uri)

    def test_userinfo_links_are_same_origin_and_get_credentials(self) -> None:
        # Non-ASCII userinfo is percent-encoded, so these still go to the page's host.
        all_names = sorted(n.lower() for (n, _v) in CREDENTIALS + OTHER_HEADERS)
        links = [
            "https://é@example.com/x.js",
            "https://bücher@example.com/x.js",
            "https://user:pé@example.com/x.js",
        ]
        linked = self.descend(links)
        self.assertEqual(len(linked), len(links))
        for uri, resource in linked.items():
            self.assertEqual(urlsplit(uri).hostname, "example.com", uri)
            self.assertEqual(origin_of(uri), origin_of(TOP), uri)
            self.assertEqual(self.header_names(resource), all_names, uri)

    def test_host_rewriting_normaliser_does_not_leak_credentials(self) -> None:
        # Credentials follow the host that's actually requested. httplint no longer rewrites the
        # host for userinfo, so simulate a normaliser that does.
        links = [
            "https://é@example.com/x.js",
            "https://bücher@example.com/x.js",
            "https://rewritten@example.com/x.js",
        ]
        with mock.patch("httplint.message.iri_to_uri", host_rewriting_normaliser):
            linked = self.descend(links)
        self.assertEqual(len(linked), len(links))
        for uri, resource in linked.items():
            self.assertEqual(self.header_names(resource), ["accept-language"], uri)
            self.assertNotEqual(origin_of(uri), origin_of(TOP), uri)

    def test_punycode_host_pages(self):
        top = "https://bücher.example/page"
        linked = self.descend(
            ["https://xn--bcher-kva.example/a.js", "https://bücher.example/b.js", "/c.js"],
            top=top,
        )
        self.assertEqual(len(linked), 3)
        for uri, resource in linked.items():
            self.assertEqual(len(self.header_names(resource)), 4, uri)

    def test_unparseable_links_fail_closed(self):
        linked = self.descend(["https://example.com.:443/a.js", "https://example.com:0/b.js"])
        for uri, resource in linked.items():
            self.assertNotIn("cookie", self.header_names(resource), uri)

    def test_unparseable_top_level_fails_closed(self):
        resource = HttpResource(make_config()["redbot"], descend=True)
        resource.set_request("https://example.com.:443/page", headers=CREDENTIALS)
        with mock.patch.object(HttpResource, "check"):
            resource.process_link("https://example.com/", "https://example.com./a.js", "script", "")
            resource.process_link("https://example.com/", "/b.js", "script", "")
        self.assertEqual(len(resource.linked), 2)
        for linked, _tag in resource.linked:
            self.assertEqual(self.header_names(linked), [])


class TestLinkedResourceChecks(unittest.TestCase):
    def test_unchecked_attributes_are_none_only_for_linked_resources(self):
        config = make_config()["redbot"]
        main = HttpResource(config, descend=True)
        linked = HttpResource(config, active_checks_enabled=False)
        for attr in ["ims_support", "inm_support", "gzip_support", "partial_support"]:
            self.assertIs(getattr(main, attr), False, attr)
            self.assertIsNone(getattr(linked, attr), attr)


class LocalServers:
    "Two local HTTP servers that record the request headers they receive, by (port, path)."

    def __init__(self) -> None:
        self.seen: Dict[Tuple[int, str], List[Dict[str, str]]] = {}
        self.servers = [self.listen(), self.listen()]
        self.ports: Tuple[int, int] = (self.servers[0][1], self.servers[1][1])

    def listen(self) -> Tuple[thor.http.HttpServer, int]:
        server = thor.http.HttpServer(b"127.0.0.1", 0)
        sock = server.tcp_server.sock
        assert sock is not None
        port = sock.getsockname()[1]
        server.on("exchange", self.handler(port))
        return server, port

    def handler(self, port: int):
        def handle(exchange) -> None:
            path = exchange.uri.decode("ascii")
            self.seen.setdefault((port, path), []).append(
                {k.decode("ascii").lower(): v.decode("ascii") for k, v in exchange.req_hdrs}
            )
            if path == "/page":
                body = self.page().encode("utf-8")
                ctype = b"text/html"
            else:
                body = b"x"
                ctype = b"text/plain"
            headers = [(b"ETag", b'"abc"'), (b"Cache-Control", b"max-age=60")]
            if self.seen[(port, path)][-1].get("if-none-match", "").strip() == '"abc"':
                exchange.response_start(b"304", b"Not Modified", headers)
            else:
                headers += [
                    (b"Content-Type", ctype),
                    (b"Content-Length", str(len(body)).encode("ascii")),
                ]
                exchange.response_start(b"200", b"OK", headers)
                exchange.response_body(body)
            exchange.response_done([])

        return handle

    def page(self) -> str:
        same, other = self.ports
        return (
            "<html><head>"
            f'<script src="http://127.0.0.1:{same}/same.js"></script>'
            f'<script src="http://127.0.0.1:{other}/port.js"></script>'
            "</head><body>hi</body></html>"
        )

    def close(self) -> None:
        for server, _port in self.servers:
            server.shutdown()


class UnsendableLinkServers(LocalServers):
    "Serves a page whose first link has an unsupported scheme, followed by a good one."

    def page(self) -> str:
        same, _other = self.ports
        return (
            "<html><head>"
            f'<script src="ftp://127.0.0.1:{same}/bad.js"></script>'
            f'<script src="http://127.0.0.1:{same}/good.js"></script>'
            "</head><body>hi</body></html>"
        )


class TestUnencodableUri(unittest.TestCase):
    "A resource whose request can't be sent fails by itself, not the whole test."

    @staticmethod
    def unencodable_resource(**kwargs: bool) -> HttpResource:
        resource = HttpResource(make_config()["redbot"], **kwargs)
        resource.set_request("http://example.com/x.js")
        # httplint 2026.10.2 percent-encodes a non-ASCII password (mnot/httplint#200), so no link
        # produces this any more; set the URI directly to keep the defensive path in
        # _send_request covered.
        resource.request.uri = "http://a:\u00e9@example.com/x.js"
        return resource

    def test_check_fails_cleanly(self) -> None:
        resource = self.unencodable_resource()
        done: List[str] = []
        resource.on("check_done", lambda: done.append("check_done"))
        with mock.patch.object(RedFetcher.client, "exchange") as exchange:
            resource.check()
        exchange.assert_not_called()
        self.assertTrue(resource.fetch_done)
        self.assertIsInstance(resource.fetch_error, UrlError)
        self.assertEqual(done, ["check_done"])

    def test_failing_link_check_still_completes(self) -> None:
        resource = HttpResource(make_config()["redbot"], descend=True)
        resource.set_request(TOP)
        debug: List[str] = []
        resource.on("debug", debug.append)
        done: List[str] = []
        resource.on("check_done", lambda: done.append("check_done"))
        with mock.patch.object(HttpResource, "check", side_effect=ValueError("boom")):
            resource.process_link(TOP, "/app.js", "script", "")
        self.assertFalse(resource._task_map)  # pylint: disable=protected-access
        linked, _tag = resource.linked[0]
        self.assertTrue(linked.fetch_done)
        self.assertIsNotNone(linked.fetch_error)
        self.assertTrue(any("boom" in message for message in debug), debug)
        # Still reading the page, so the link can't complete the parent...
        self.assertEqual(done, [])
        # ...but nothing is left waiting for it once the parent's own fetch finishes.
        resource.stop()
        self.assertEqual(done, ["check_done"])

    def test_failing_debug_listener_does_not_stall_link(self) -> None:
        # Cleanup must not depend on the debug message getting out. Everything here is
        # synchronous, so a regression fails the assertions rather than hanging.
        def broken(_message: str) -> None:
            raise RuntimeError("bad listener")

        resource = HttpResource(make_config()["redbot"], descend=True)
        resource.set_request(TOP)
        resource.on("debug", broken)
        with mock.patch.object(HttpResource, "check", side_effect=ValueError("boom")):
            resource.process_link(TOP, "/app.js", "script", "")
        self.assertFalse(resource._task_map)  # pylint: disable=protected-access
        self.assertTrue(resource.linked[0][0].fetch_done)

    def test_link_parser_reports_errors(self) -> None:
        with mock.patch.object(HttpResource, "process_link", side_effect=ValueError("boom")):
            resource = HttpResource(make_config()["redbot"], descend=True)
        resource.set_request(TOP)
        debug: List[str] = []
        resource.on("debug", debug.append)
        resource.response.process_response_topline(b"1.1", b"200", b"OK")
        resource.response.process_headers([(b"Content-Type", b"text/html")])
        resource._link_parser.feed(  # pylint: disable=protected-access
            '<script src="/a.js"></script>'
        )
        self.assertTrue(any("boom" in message for message in debug), debug)

    def test_descend_end_to_end(self) -> None:
        # A link that fails before its request is sent (thor rejects the scheme) must not stall
        # the page, or the links after it.
        saved_check_ip = RedFetcher.client.check_ip
        RedFetcher.client.check_ip = None
        servers = UnsendableLinkServers()
        timed_out: List[bool] = []

        def give_up() -> None:
            timed_out.append(True)
            thor.stop()

        try:
            same, _other = servers.ports
            resource = HttpResource(make_config()["redbot"], descend=True)
            resource.set_request(f"http://127.0.0.1:{same}/page")
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
        self.assertIsInstance(by_path["/bad.js"].fetch_error, UrlError)
        self.assertIsNone(by_path["/good.js"].fetch_error)
        self.assertTrue(by_path["/good.js"].response.complete)
        self.assertNotIn((same, "/bad.js"), servers.seen)


class TestDescendEndToEnd(unittest.TestCase):
    "Real requests against local servers."

    def setUp(self) -> None:
        # Don't depend on (or leak) whatever address check earlier tests left on the shared client.
        self.saved_check_ip = RedFetcher.client.check_ip
        RedFetcher.client.check_ip = None
        self.servers = LocalServers()
        self.config = make_config(enable_local_access="yes", max_runtime="20")["redbot"]
        same, _other = self.servers.ports
        self.resource = HttpResource(self.config, descend=True)
        self.resource.set_request(
            f"http://127.0.0.1:{same}/page",
            headers=CREDENTIALS + [("X-Other", "1")],
        )

        @thor.events.on(self.resource)
        def check_done() -> None:
            thor.stop()

        self.timeout = thor.schedule(20, thor.stop)
        self.resource.check()
        thor.run()
        self.timeout.delete()

    def tearDown(self) -> None:
        self.servers.close()
        RedFetcher.client.check_ip = self.saved_check_ip

    def test_credentials_only_reach_the_tested_origin(self):
        same, other = self.servers.ports
        seen = self.servers.seen
        self.assertTrue(self.resource.check_done)
        self.assertEqual(len(self.resource.linked), 2)
        # (Proxy-Authorization is a hop-by-hop credential that the client doesn't put on the
        # wire to an origin server at all, so it's only covered by the header tests above.)
        for hdr in ["authorization", "cookie", "x-other"]:
            self.assertIn(hdr, seen[(same, "/page")][0])
            self.assertIn(hdr, seen[(same, "/same.js")][0])
        self.assertIn((other, "/port.js"), seen)
        self.assertNotIn("authorization", seen[(other, "/port.js")][0])
        self.assertNotIn("cookie", seen[(other, "/port.js")][0])
        self.assertIn("x-other", seen[(other, "/port.js")][0])

    def test_linked_resources_make_a_single_request(self):
        for key, requests in self.servers.seen.items():
            if key[1] != "/page":
                self.assertEqual(len(requests), 1, key)
        # The top-level resource still ran its active checks.
        self.assertTrue(len(self.servers.seen[(self.servers.ports[0], "/page")]) > 1)
        self.assertTrue(self.resource.subreqs["etag_validate"].fetch_started)
        for linked, _tag in self.resource.linked:
            self.assertFalse(any(s.fetch_started for s in linked.subreqs.values()))

    def test_summary_table_marks_linked_checks_as_not_checked(self):
        out: List[str] = []
        formatter = TableHtmlFormatter(
            self.config,
            self.resource,
            out.append,
            {"nonce": "n", "descend": True},
        )
        formatter.bind_resource(self.resource)  # already done, so this renders immediately
        html = "".join(out)
        rows = re.findall(r'<tr class="droid">.*?</tr>', html, re.S)
        self.assertEqual(len(rows), 3)
        main, *linked_rows = rows

        def check_cells(row: str) -> List[str]:
            # IMS, INM, gzip, partial
            return re.findall(r"<td.*?</td>", row, re.S)[7:11]

        self.assertIn('class="yes"', check_cells(main)[1])  # INM validated on the main resource
        for row in linked_rows:
            for cell in check_cells(row):
                self.assertIn('class="maybe"', cell)


if __name__ == "__main__":
    unittest.main()
