#!/usr/bin/env python

"""
REDbot Robot Fetcher.

Fetches robots.txt for a given URL.
"""

from configparser import SectionProxy
import hashlib
import hmac
from os import path
import secrets
from typing import (
    Union,
    Dict,
    Tuple,
    Callable,
    TYPE_CHECKING,
)  # pylint: disable=unused-import
from urllib.robotparser import RobotFileParser
from urllib.parse import urlsplit

import thor

from redbot import __version__
from redbot.cache_file import CacheFile
from redbot.formatter import Formatter
from redbot.message import HttpRequest
from redbot.resource import HttpResource
from redbot.type import RawHeaderListType

if TYPE_CHECKING:
    from redbot.webui import RedWebUi  # pylint: disable=cyclic-import,unused-import

RobotChecker = Union[RobotFileParser, "DummyChecker"]

UA_STRING = "RED/%s (https://redbot.org/)" % __version__
ROBOT_SECRET = secrets.token_bytes(16)  # type: bytes


def request_robot_proof(
    webui: "RedWebUi", continue_test: Callable[[], None], error_response: Callable
) -> None:
    robot_fetcher = RobotFetcher(webui.config)

    @thor.events.on(robot_fetcher)
    def robot(results: Tuple[str, bool]) -> None:
        url, robot_ok = results
        if robot_ok:
            continue_test()
        else:
            valid_till = str(int(thor.time()) + 60)
            robot_hmac = hmac.new(ROBOT_SECRET, bytes(valid_till, "ascii"), "sha512")
            error_response(
                b"403",
                b"Forbidden",
                f"This site doesn't allow robots. If you are human, please <a href='?uri={webui.test_uri}&robot_time={valid_till}&robot_hmac={robot_hmac.hexdigest()}'>click here</a>.",
            )

    robot_fetcher.check_robots(HttpRequest.iri_to_uri(webui.test_uri))


def check_robot_proof(
    webui: "RedWebUi", continue_test: Callable[[], None], error_response: Callable
) -> None:
    robot_time = webui.query_string.get("robot_time", [None])[0]
    robot_hmac = webui.query_string.get("robot_hmac", [None])[0]
    if robot_time and robot_time.isdigit() and robot_hmac:
        valid_till = int(robot_time)
        computed_hmac = hmac.new(ROBOT_SECRET, bytes(robot_time, "ascii"), "sha512")
        is_valid = robot_hmac == computed_hmac.hexdigest()
        if is_valid and valid_till >= thor.time():
            continue_test()
        else:
            error_response(b"403", b"Forbidden", "Naughty.", "Naughty robot key.")
            raise ValueError


class RobotFetcher(thor.events.EventEmitter):
    """
    Fetch robots.txt and check to see if we're allowed.
    """

    check_name = "robot"
    response_phrase = "The robots.txt response"
    freshness_lifetime = 30 * 60
    client = thor.http.HttpClient()
    client.idle_timeout = 5
    robot_checkers = {}  # type: Dict[str, RobotChecker]  # cache of robots.txt checkers
    robot_lookups = {}  # type: Dict[str, set]

    def __init__(self, config: SectionProxy) -> None:
        thor.events.EventEmitter.__init__(self)
        self.config = config

    def check_robots(self, url: str) -> None:
        """
        Fetch the robots.txt for URL.

        The 'robot' event will be emitted, with a (url, robot_ok) payload.
        """

        origin = url_to_origin(url)
        if origin is None:
            self.emit("robot", (url, True))
            return None
        origin_hash = hashlib.sha1(origin.encode("ascii", "replace")).hexdigest()

        if origin in self.robot_checkers:
            return self._robot_check(url, self.robot_checkers[origin])

        if self.config.get("robot_cache_dir", ""):
            robot_fd = CacheFile(path.join(self.config["robot_cache_dir"], origin_hash))
            cached_robots_txt = robot_fd.read()
            if cached_robots_txt is not None:
                self._load_checker(origin, cached_robots_txt)
                return self._robot_check(url, self.robot_checkers[origin])

        if origin in self.robot_lookups:
            self.robot_lookups[origin].add(url)
        else:
            self.robot_lookups[origin] = set([url])
            exchange = self.client.exchange()

            @thor.on(exchange)
            def response_start(
                status: bytes, phrase: bytes, headers: RawHeaderListType
            ) -> None:
                exchange.status = status

            exchange.res_body = b""

            @thor.on(exchange)
            def response_body(chunk: bytes) -> None:
                exchange.res_body += chunk

            @thor.on(exchange)
            def response_done(trailers: RawHeaderListType) -> None:
                if not exchange.status.startswith(b"2"):
                    robots_txt = b""
                else:
                    robots_txt = exchange.res_body

                self._load_checker(origin, robots_txt)
                if self.config.get("robot_cache_dir", ""):
                    robot_fd = CacheFile(
                        path.join(self.config["robot_cache_dir"], origin_hash)
                    )
                    robot_fd.write(robots_txt, self.freshness_lifetime)

                while True:
                    try:
                        check_url = self.robot_lookups[origin].pop()
                    except KeyError:
                        break
                    self._robot_check(check_url, self.robot_checkers[origin])
                try:
                    del self.robot_lookups[origin]
                except KeyError:
                    pass

            @thor.on(exchange)
            def error(error: thor.http.error.HttpError) -> None:
                exchange.status = b"500"
                response_done([])

            p_url = urlsplit(url)
            robots_url = "%s://%s/robots.txt" % (p_url.scheme, p_url.netloc)
            exchange.request_start(
                b"GET",
                robots_url.encode("ascii"),
                [(b"User-Agent", UA_STRING.encode("ascii"))],
            )
            exchange.request_done([])
        return None

    def _load_checker(self, origin: str, robots_txt: bytes) -> None:
        """Load a checker for an origin, given its robots.txt file."""
        if robots_txt == "":  # empty or non-200
            checker = DummyChecker()  # type: RobotChecker
        else:
            checker = RobotFileParser()
            checker.parse(robots_txt.decode("ascii", "replace").splitlines())
        self.robot_checkers[origin] = checker

        def del_checker() -> None:
            try:
                del self.robot_checkers[origin]
            except:
                pass

        thor.schedule(self.freshness_lifetime, del_checker)

    def _robot_check(self, url: str, robots_checker: RobotChecker) -> None:
        """Continue after getting the robots file."""
        robot_ok = robots_checker.can_fetch(UA_STRING, url)
        self.emit("robot", (url, robot_ok))


def url_to_origin(url: str) -> Union[str, None]:
    "Convert an URL to an RFC6454 Origin."
    default_port = {"http": 80, "https": 443}
    try:
        p_url = urlsplit(url)
        origin = "%s://%s:%s" % (
            p_url.scheme.lower(),
            p_url.hostname.lower(),
            p_url.port or default_port.get(p_url.scheme, 0),
        )
    except (AttributeError, ValueError):
        origin = None
    return origin


class DummyChecker:
    """Dummy checker for non-200 or empty responses."""

    @staticmethod
    def can_fetch(ua_string: str, url: str) -> bool:
        return True
