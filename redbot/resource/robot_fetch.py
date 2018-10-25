#!/usr/bin/env python

"""
REDbot Robot Fetcher.

Fetches robots.txt for a given URL.
"""

from configparser import SectionProxy
import hashlib
from os import path
from typing import Union, Dict # pylint: disable=unused-import
from urllib.robotparser import RobotFileParser
from urllib.parse import urlsplit

import thor

from redbot import __version__
from redbot.cache_file import CacheFile
from redbot.type import RawHeaderListType

UA_STRING = "RED/%s (https://redbot.org/)" % __version__
RobotChecker = Union[RobotFileParser, 'DummyChecker']

class RobotFetcher:
    """
    Fetch robots.txt and check to see if we're allowed.
    """
    check_name = "robot"
    response_phrase = "The robots.txt response"
    freshness_lifetime = 30 * 60
    client = thor.http.HttpClient()
    client.idle_timeout = 5
    robot_checkers = {} # type: Dict[str, RobotChecker]  # cache of robots.txt checkers
    robot_lookups = {} # type: Dict[str, set]
    emitter = thor.events.EventEmitter()

    def __init__(self, config: SectionProxy) -> None:
        self.config = config

    def check_robots(self, url: str, sync: bool = False) -> Union[bool, None]:
        """
        Fetch the robots.txt for URL.

        When sync is true, the result is returned. Sync does not go to network; if
        there is not a local (memory or cache) robots.txt, it will return True.

        When it's false, the "robot" event will be emitted, with two arguments:
          - the URL
          - True if it's allowed, False if not
        """

        origin = url_to_origin(url)
        if origin is None:
            if sync:
                return True
            self.emitter.emit("robot-%s" % url, True)
            return None
        origin_hash = hashlib.sha1(origin.encode('ascii', 'replace')).hexdigest()

        if origin in self.robot_checkers:
            return self._robot_check(url, self.robot_checkers[origin], sync)

        if self.config.get('robot_cache_dir', ''):
            robot_fd = CacheFile(path.join(self.config['robot_cache_dir'], origin_hash))
            cached_robots_txt = robot_fd.read()
            if cached_robots_txt is not None:
                self._load_checker(origin, cached_robots_txt)
                return self._robot_check(url, self.robot_checkers[origin], sync)

        if sync:
            return True

        if origin in self.robot_lookups:
            self.robot_lookups[origin].add(url)
        else:
            self.robot_lookups[origin] = set([url])
            exchange = self.client.exchange()
            @thor.on(exchange)
            def response_start(status: bytes, phrase: bytes, headers: RawHeaderListType) -> None:
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
                if self.config.get('robot_cache_dir', ''):
                    robot_fd = CacheFile(path.join(self.config['robot_cache_dir'], origin_hash))
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
            exchange.request_start(b"GET", robots_url.encode('ascii'),
                                   [(b'User-Agent', UA_STRING.encode('ascii'))])
            exchange.request_done([])
        return None

    def _load_checker(self, origin: str, robots_txt: bytes) -> None:
        """Load a checker for an origin, given its robots.txt file."""
        if robots_txt == "": # empty or non-200
            checker = DummyChecker() # type: RobotChecker
        else:
            checker = RobotFileParser()
            checker.parse(robots_txt.decode('ascii', 'replace').splitlines())
        self.robot_checkers[origin] = checker
        def del_checker() -> None:
            try:
                del self.robot_checkers[origin]
            except:
                pass
        thor.schedule(self.freshness_lifetime, del_checker)

    def _robot_check(self, url: str, robots_checker: RobotChecker,
                     sync: bool = False) -> Union[bool, None]:
        """Continue after getting the robots file."""
        result = robots_checker.can_fetch(UA_STRING, url)
        if sync:
            return result
        self.emitter.emit("robot-%s" % url, result)
        return None



def url_to_origin(url: str) -> Union[str, None]:
    "Convert an URL to an RFC6454 Origin."
    default_port = {
        'http': 80,
        'https': 443}
    try:
        p_url = urlsplit(url)
        origin = "%s://%s:%s" % (p_url.scheme.lower(),
                                 p_url.hostname.lower(),
                                 p_url.port or default_port.get(p_url.scheme, 0))
    except (AttributeError, ValueError):
        origin = None
    return origin


class DummyChecker:
    """Dummy checker for non-200 or empty responses."""
    @staticmethod
    def can_fetch(ua_string: str, url: str) -> bool:
        return True
