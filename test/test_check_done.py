#!/usr/bin/env python3

"""
check_done is emitted exactly once per resource, after everything has finished, however the
active checks and linked resources happen to complete (mnot/redbot#487).
"""

import unittest
from configparser import SectionProxy
from test.test_descend import LocalServers, make_config
from typing import Any, Dict, List, Tuple
from unittest import mock

import thor

from redbot.formatter.text import TextFormatter
from redbot.resource import HttpResource
from redbot.resource.active_check.base import SubRequest
from redbot.resource.fetch import RedFetcher
from redbot.type import StrHeaderListType

TIMEOUT = 10  # seconds; a regression should fail the test, not hang it
SETTLE = 0.5  # seconds to keep running after the first check_done, to catch late repeats
TOP = "http://example.com/"


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
    ) -> None:
        SubRequest.__init__(self, config, base)
        self.name = name
        self.log = log
        self.synchronous = synchronous

    def modify_request_headers(self, base_headers: StrHeaderListType) -> StrHeaderListType:
        return base_headers

    def check(self) -> None:
        self.log.append(f"start:{self.name}")
        if self.synchronous:
            self.finish()

    def finish(self) -> None:
        "Complete as a real check does: fetch_done, then check_done."
        self.log.append(f"finish:{self.name}")
        self._fetch_done()

    def done(self) -> None:
        pass


class TestRunActiveChecks(unittest.TestCase):
    "Fake checks that complete synchronously, in each position."

    def setUp(self) -> None:
        self.config = make_config()["redbot"]
        self.log: List[str] = []

    def build(self, pattern: str) -> Tuple[HttpResource, List[FakeCheck]]:
        "pattern: one letter per check; S completes in check(), A is left for the test to finish."
        resource = HttpResource(self.config, descend=True)
        resource.set_request(TOP)
        checks = [
            FakeCheck(self.config, resource, str(i), self.log, letter == "S")
            for i, letter in enumerate(pattern)
        ]
        resource.subreqs = {f"fake{c.name}": c for c in checks}  # type: ignore[misc]
        resource.on("check_done", lambda: self.log.append("check_done"))
        resource.response.finish_content(True)
        return resource, checks

    @staticmethod
    def start(resource: HttpResource) -> None:
        "The response has arrived: this runs the active checks."
        resource._fetch_done()  # pylint: disable=protected-access

    def test_synchronous_completion_in_any_position(self) -> None:
        patterns = ["SAAA", "ASAA", "AASA", "AAAS", "SSSA", "SASA", "SSSS", "AAAA"]
        for pattern in patterns:
            for reverse in [False, True]:
                with self.subTest(pattern=pattern, reverse=reverse):
                    self.log.clear()
                    resource, checks = self.build(pattern)
                    self.start(resource)
                    self.assertEqual(
                        [e for e in self.log if e.startswith("start:")],
                        [f"start:{i}" for i in range(len(pattern))],
                    )
                    pending = [c for c, letter in zip(checks, pattern) if letter == "A"]
                    if reverse:
                        pending.reverse()
                    for check in pending:
                        self.assertNotIn("check_done", self.log)
                        check.finish()
                    self.assertEqual(self.log.count("check_done"), 1, self.log)
                    self.assertEqual(self.log[-1], "check_done", self.log)
                    self.assertEqual(sum(e.startswith("finish:") for e in self.log), len(pattern))
                    self.assertTrue(resource.check_done)

    def test_late_finish_check_does_not_repeat(self) -> None:
        resource, _checks = self.build("SSSS")
        self.start(resource)
        resource.finish_check()
        resource.finish_check()
        self.assertEqual(self.log.count("check_done"), 1, self.log)

    def test_waits_for_linked_resource(self) -> None:
        resource, _checks = self.build("SSSS")
        with mock.patch.object(HttpResource, "check"):
            resource.process_link(TOP, "/app.js", "script", "")
        linked, _tag = resource.linked[0]
        self.start(resource)
        self.assertEqual(self.log.count("check_done"), 0, self.log)
        linked._fetch_done()  # pylint: disable=protected-access
        self.assertEqual(self.log.count("check_done"), 1, self.log)
        self.assertEqual(self.log[-1], "check_done", self.log)


class LinkServers(LocalServers):
    "Serves a page linking to whatever is in .links (PORT stands for the first server's port)."

    links: List[str] = []

    def page(self) -> str:
        tags = "".join(
            f'<script src="{link.replace("PORT", str(self.ports[0]))}"></script>'
            for link in self.links
        )
        return f"<html><head>{tags}</head><body>hi</body></html>"


class EndToEnd(unittest.TestCase):
    "Real requests against a local server."

    def setUp(self) -> None:
        # The fetcher's HTTP client is shared by the whole process.
        self.saved_check_ip = RedFetcher.client.check_ip
        RedFetcher.client.check_ip = None
        self.servers = LinkServers()
        self.config = make_config()["redbot"]

    def tearDown(self) -> None:
        self.servers.close()
        RedFetcher.client.check_ip = self.saved_check_ip

    def run_resource(self, resource: HttpResource) -> Dict[str, Any]:
        "Run with a formatter bound until just after check_done, so late repeats are seen too."
        seen: Dict[str, Any] = {"check_done": 0, "finish_output": 0, "timed_out": False}

        class Counting(TextFormatter):
            def finish_output(self) -> None:
                seen["finish_output"] += 1
                super().finish_output()

        Counting(self.config, resource, lambda _text: None, {}).bind_resource(resource)

        @thor.events.on(resource)
        def check_done() -> None:
            seen["check_done"] += 1
            seen.setdefault("unfinished", self.unfinished(resource))
            thor.schedule(SETTLE, thor.stop)

        def give_up() -> None:
            seen["timed_out"] = True
            thor.stop()

        timeout = thor.schedule(TIMEOUT, give_up)
        resource.check()
        thor.run()
        timeout.delete()
        self.assertFalse(seen["timed_out"], "check_done never fired")
        return seen

    @staticmethod
    def unfinished(resource: HttpResource) -> List[str]:
        "What hadn't finished when check_done was emitted."
        everything = list(resource.subreqs.values()) + [r for r, _t in resource.linked]
        return [str(r.request.uri) for r in everything if not r.fetch_done]

    def check_once(self, seen: Dict[str, Any]) -> None:
        self.assertEqual(seen["check_done"], 1)
        self.assertEqual(seen["finish_output"], 1)
        self.assertEqual(seen["unfinished"], [])

    def test_accept_encoding_request(self) -> None:
        # The scenario in #487: conneg is skipped and completes inside check().
        resource = HttpResource(self.config)
        resource.set_request(
            f"http://127.0.0.1:{self.servers.ports[0]}/good.js",
            headers=[("Accept-Encoding", "gzip")],
        )
        seen = self.run_resource(resource)
        self.check_once(seen)
        self.assertIs(resource.inm_support, True)  # filled in before the output was made

    def descend(self, links: List[str], **kwargs: Any) -> Tuple[HttpResource, Dict[str, Any]]:
        self.servers.links = links
        same = self.servers.ports[0]
        resource = HttpResource(self.config, descend=True)
        resource.set_request(f"http://127.0.0.1:{same}/page", **kwargs)
        return resource, self.run_resource(resource)

    def test_first_link_fails_synchronously(self) -> None:
        resource, seen = self.descend(["ftp://127.0.0.1/bad.js", "http://127.0.0.1:PORT/a.js"])
        self.check_once(seen)
        self.assertIsNotNone(resource.linked[0][0].fetch_error)
        self.assertTrue(resource.linked[1][0].response.complete)

    def test_all_links_fail_synchronously_with_accept_encoding(self) -> None:
        resource, seen = self.descend(
            ["ftp://127.0.0.1/a.js", "http://127.0.0.1:0/b.js"],
            headers=[("Accept-Encoding", "gzip")],
        )
        self.check_once(seen)
        for linked, _tag in resource.linked:
            self.assertIsNotNone(linked.fetch_error)


if __name__ == "__main__":
    unittest.main()
