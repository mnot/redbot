#!/usr/bin/env python3

"""
check_done is emitted exactly once per resource, after everything has finished, however the
active checks and linked resources happen to complete (mnot/redbot#487).
"""

import unittest
from configparser import ConfigParser, SectionProxy
from typing import Any, Callable, Dict, List, Optional, Tuple

import thor
import thor.http

from redbot.formatter import Formatter
from redbot.formatter.html import SingleEntryHtmlFormatter
from redbot.formatter.text import TextFormatter
from redbot.resource import HttpResource
from redbot.resource.active_check.base import SubRequest
from redbot.resource.fetch import RedFetcher
from redbot.type import StrHeaderListType

TIMEOUT = 10  # seconds; a regression should fail the test, not hang it
SETTLE = 0.5  # seconds to keep running after the first check_done, to catch late repeats


def make_config() -> SectionProxy:
    conf = ConfigParser()
    conf.read_dict({"redbot": {"enable_local_access": "yes"}})
    return conf["redbot"]


class FakeCheck(SubRequest):
    "An active check whose completion the test controls."

    check_name = "Fake"
    check_id = "fake"

    def __init__(
        self,
        config: SectionProxy,
        base: HttpResource,
        name: str,
        log: List[str],
        synchronous: bool,
        raises: bool = False,
        done_raises: bool = False,
    ) -> None:
        SubRequest.__init__(self, config, base)
        self.name = name
        self.log = log
        self.synchronous = synchronous
        self.raises = raises
        self.done_raises = done_raises

    def modify_request_headers(self, base_headers: StrHeaderListType) -> StrHeaderListType:
        return base_headers

    def check(self) -> None:
        self.log.append(f"start:{self.name}")
        if self.raises:
            raise ValueError("boom")
        if self.synchronous:
            self.finish()

    def finish(self) -> None:
        "Complete as a real check does: fetch_done, then check_done."
        self.log.append(f"finish:{self.name}")
        self._fetch_done()

    def done(self) -> None:
        if self.done_raises:
            raise ValueError("boom in done")


class TestRunActiveChecks(unittest.TestCase):
    "Fake checks that complete synchronously, in each position."

    def setUp(self) -> None:
        self.config = make_config()
        self.log: List[str] = []

    def build(self, pattern: str, **kwargs: Any) -> Tuple[HttpResource, List[FakeCheck]]:
        "pattern: one letter per check; S completes in check(), A is left for the test to finish."
        resource = HttpResource(self.config)
        resource.set_request("http://example.com/")
        checks = [
            FakeCheck(self.config, resource, str(i), self.log, letter == "S", **kwargs)
            for i, letter in enumerate(pattern)
        ]
        resource.subreqs = {f"fake{c.name}": c for c in checks}  # type: ignore[misc]
        resource.on("check_done", lambda: self.log.append("check_done"))
        resource.response.finish_content(True)
        return resource, checks

    def start(self, resource: HttpResource) -> None:
        "The response has arrived: this runs the active checks."
        resource.fetch_done = False
        resource._fetch_done()  # pylint: disable=protected-access

    def test_synchronous_completion_in_any_position(self) -> None:
        patterns = ["SAAA", "ASAA", "AASA", "AAAS", "SSAA", "SSSA", "ASSS", "SASA", "SSSS", "AAAA"]
        for pattern in patterns:
            for reverse in [False, True]:
                with self.subTest(pattern=pattern, reverse=reverse):
                    self.log.clear()
                    resource, checks = self.build(pattern)
                    self.start(resource)
                    pending = [c for c, letter in zip(checks, pattern) if letter == "A"]
                    if reverse:
                        pending.reverse()
                    for check in pending:
                        self.assertNotIn("check_done", self.log)
                        check.finish()
                    self.assertEqual(self.log.count("check_done"), 1, self.log)
                    self.assertEqual(self.log[-1], "check_done", self.log)
                    self.assertEqual(
                        sorted(e for e in self.log if e.startswith("finish:")),
                        [f"finish:{i}" for i in range(len(pattern))],
                    )
                    self.assertTrue(resource.check_done)

    def test_every_check_starts(self) -> None:
        # Starting one mustn't depend on how an earlier one completed.
        for pattern in ["SSSS", "SAAA", "AAAS"]:
            with self.subTest(pattern=pattern):
                self.log.clear()
                resource, _checks = self.build(pattern)
                self.start(resource)
                self.assertEqual(
                    [e for e in self.log if e.startswith("start:")],
                    [f"start:{i}" for i in range(len(pattern))],
                )

    def test_check_that_raises_does_not_stall_the_others(self) -> None:
        for position in range(4):
            with self.subTest(position=position):
                self.log.clear()
                resource, checks = self.build("SSSS")
                for i, check in enumerate(checks):
                    check.synchronous = i != position
                    check.raises = i == position
                debug: List[str] = []
                resource.on("debug", debug.append)
                self.start(resource)
                self.assertEqual(sum(e.startswith("start:") for e in self.log), 4)
                self.assertTrue(checks[position].fetch_done)
                self.assertIsNotNone(checks[position].fetch_error)
                self.assertTrue(any("boom" in m for m in debug), debug)
                self.assertTrue(resource.check_done)
                self.assertEqual(self.log.count("check_done"), 1, self.log)

    def test_pending_check_after_a_raising_one_still_gates_check_done(self) -> None:
        resource, checks = self.build("AAAA")
        checks[1].raises = True
        self.start(resource)
        self.assertNotIn("check_done", self.log)
        for check in [checks[0], checks[2], checks[3]]:
            self.assertNotIn("check_done", self.log)
            check.finish()
        self.assertEqual(self.log.count("check_done"), 1, self.log)
        self.assertEqual(self.log[-1], "check_done", self.log)

    def test_check_that_raises_after_finishing_does_not_repeat(self) -> None:
        resource, checks = self.build("SSSS")

        def finish_then_raise() -> None:
            checks[1].log.append("start:1")
            checks[1].finish()
            raise ValueError("boom")

        checks[1].check = finish_then_raise  # type: ignore[method-assign]
        self.start(resource)
        self.assertEqual(self.log.count("check_done"), 1, self.log)

    def test_check_that_fails_to_clean_up_does_not_stall(self) -> None:
        resource, checks = self.build("SSSS")
        checks[2].synchronous = False
        checks[2].raises = True
        checks[2].done_raises = True  # so stop() raises too
        self.start(resource)
        self.assertEqual(self.log.count("check_done"), 1, self.log)
        self.assertTrue(resource.check_done)

    def test_late_finish_check_does_not_repeat(self) -> None:
        resource, _checks = self.build("SSSS")
        self.start(resource)
        resource.finish_check()
        resource.finish_check()
        self.assertEqual(self.log.count("check_done"), 1, self.log)

    def test_not_complete_before_fetch_done(self) -> None:
        resource, _checks = self.build("SSSS")
        resource.finish_check()
        self.assertEqual(self.log, [])
        self.assertFalse(resource.check_done)


class Servers:
    "A local HTTP server for the end-to-end tests."

    def __init__(self, slow: float = 0.3) -> None:
        self.slow = slow
        self.server = thor.http.HttpServer(b"127.0.0.1", 0)
        sock = self.server.tcp_server.sock
        assert sock is not None
        self.port: int = sock.getsockname()[1]
        self.links: List[str] = []
        self.server.on("exchange", self.handle)

    def page(self) -> bytes:
        tags = "".join(f'<script src="{link}"></script>' for link in self.links)
        return f"<html><head>{tags}</head><body>hi</body></html>".encode("ascii")

    def handle(self, exchange: Any) -> None:
        path = exchange.uri.decode("ascii")
        if path == "/slow.js":
            thor.schedule(self.slow, self.respond, exchange, path)
        else:
            self.respond(exchange, path)

    def respond(self, exchange: Any, path: str) -> None:
        if path == "/page":
            body, ctype = self.page(), b"text/html"
        else:
            body, ctype = b"console.log(1);\n", b"application/javascript"
        headers = [
            (b"Content-Type", ctype),
            (b"Content-Length", str(len(body)).encode("ascii")),
            (b"Last-Modified", b"Mon, 01 Jan 2024 00:00:00 GMT"),
        ]
        if any(k.lower() == b"if-modified-since" for k, _v in exchange.req_hdrs):
            exchange.response_start(b"304", b"Not Modified", headers[2:])
        else:
            exchange.response_start(b"200", b"OK", headers)
            exchange.response_body(body)
        exchange.response_done([])

    def close(self) -> None:
        self.server.shutdown()


class EndToEnd(unittest.TestCase):
    "Real requests against a local server."

    def setUp(self) -> None:
        # The fetcher's HTTP client is shared by the whole process.
        self.saved_check_ip = RedFetcher.client.check_ip
        RedFetcher.client.check_ip = None
        self.servers = Servers()
        self.config = make_config()

    def tearDown(self) -> None:
        self.servers.close()
        RedFetcher.client.check_ip = self.saved_check_ip

    def run_resource(
        self,
        resource: HttpResource,
        formatter_class: Optional[Callable[..., Formatter]] = None,
    ) -> Dict[str, Any]:
        "Run until just after check_done, so late repeats are seen too."
        seen: Dict[str, Any] = {"check_done": 0, "finish_output": 0, "writes": 0}
        timed_out: List[bool] = []

        @thor.events.on(resource)
        def check_done() -> None:
            seen["check_done"] += 1
            seen.setdefault("at_check_done", self.state(resource))
            thor.schedule(SETTLE, thor.stop)

        if formatter_class:
            counting = self.counting(formatter_class, seen)
            formatter = counting(self.config, resource, self.write(seen), {})
            formatter.bind_resource(resource)

        def give_up() -> None:
            timed_out.append(True)
            thor.stop()

        timeout = thor.schedule(TIMEOUT, give_up)
        resource.check()
        thor.run()
        timeout.delete()
        self.assertFalse(timed_out, "check_done never fired")
        return seen

    @staticmethod
    def write(seen: Dict[str, Any]) -> Callable[[str], None]:
        def out(_text: str) -> None:
            seen["writes"] += 1

        return out

    @staticmethod
    def counting(formatter_class: Callable[..., Formatter], seen: Dict[str, Any]) -> Any:
        class Counting(formatter_class):  # type: ignore[valid-type,misc]
            def finish_output(self) -> None:
                seen["finish_output"] += 1
                super().finish_output()

        return Counting

    @staticmethod
    def state(resource: HttpResource) -> Dict[str, bool]:
        "What had finished when check_done was emitted."
        state = {f"check:{k}": c.fetch_done for k, c in resource.subreqs.items()}
        state.update({f"link:{r.request.uri}": r.fetch_done for r, _t in resource.linked})
        return state

    def accept_encoding_request(self, formatter_class: Callable[..., Formatter]) -> None:
        # The scenario in #487: conneg is skipped and completes inside check().
        resource = HttpResource(self.config)
        resource.set_request(
            f"http://127.0.0.1:{self.servers.port}/good.js",
            headers=[("Accept-Encoding", "gzip")],
        )
        seen = self.run_resource(resource, formatter_class)
        self.assertEqual(seen["check_done"], 1)
        self.assertEqual(seen["finish_output"], 1)
        self.assertTrue(all(seen["at_check_done"].values()), seen["at_check_done"])
        self.assertIs(resource.ims_support, True)  # filled in before the output was made
        self.assertGreater(seen["writes"], 0)

    def test_accept_encoding_request_text(self) -> None:
        self.accept_encoding_request(TextFormatter)

    def test_accept_encoding_request_html(self) -> None:
        self.accept_encoding_request(SingleEntryHtmlFormatter)

    def descend(
        self, links: List[str], headers: Optional[StrHeaderListType] = None
    ) -> Tuple[HttpResource, Dict[str, Any]]:
        self.servers.links = [link.replace("PORT", str(self.servers.port)) for link in links]
        resource = HttpResource(self.config, descend=True)
        resource.set_request(f"http://127.0.0.1:{self.servers.port}/page", headers=headers)
        return resource, self.run_resource(resource, TextFormatter)

    def check_descended(self, resource: HttpResource, seen: Dict[str, Any], count: int) -> None:
        self.assertEqual(len(resource.linked), count)
        self.assertEqual(seen["check_done"], 1)
        self.assertEqual(seen["finish_output"], 1)
        self.assertTrue(all(seen["at_check_done"].values()), seen["at_check_done"])
        self.assertEqual(len(seen["at_check_done"]), count + len(resource.subreqs))

    def test_first_link_fails_synchronously(self) -> None:
        resource, seen = self.descend(["ftp://127.0.0.1/bad.js", "http://127.0.0.1:PORT/a.js"])
        self.check_descended(resource, seen, 2)
        self.assertIsNotNone(resource.linked[0][0].fetch_error)
        self.assertTrue(resource.linked[1][0].response.complete)

    def test_all_links_fail_synchronously(self) -> None:
        resource, seen = self.descend(["ftp://127.0.0.1/a.js", "http://127.0.0.1:0/b.js"])
        self.check_descended(resource, seen, 2)
        for linked, _tag in resource.linked:
            self.assertIsNotNone(linked.fetch_error)

    def test_all_links_fail_synchronously_with_accept_encoding(self) -> None:
        # Failed links and the checks that complete synchronously, with only lm_validate left.
        resource, seen = self.descend(
            ["ftp://127.0.0.1/a.js", "http://127.0.0.1:0/b.js"],
            headers=[("Accept-Encoding", "gzip")],
        )
        self.check_descended(resource, seen, 2)

    def test_all_links_fail_synchronously_without_active_checks(self) -> None:
        # Nothing but the (synchronously failed) links to wait for once the page has been read.
        self.servers.links = ["ftp://127.0.0.1/a.js", "ftp://127.0.0.1/b.js"]
        resource = HttpResource(self.config, descend=True, active_checks_enabled=False)
        resource.set_request(f"http://127.0.0.1:{self.servers.port}/page")
        seen = self.run_resource(resource, TextFormatter)
        self.assertEqual(seen["check_done"], 1)
        self.assertEqual(seen["finish_output"], 1)

    def test_parent_waits_for_slow_link(self) -> None:
        # The active checks and the failed link are long done before the slow link is.
        resource, seen = self.descend(["ftp://127.0.0.1/bad.js", "http://127.0.0.1:PORT/slow.js"])
        self.check_descended(resource, seen, 2)
        self.assertTrue(resource.linked[1][0].response.complete)


if __name__ == "__main__":
    unittest.main()
