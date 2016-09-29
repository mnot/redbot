#!/usr/bin/env python

"""
RED Robot Fetcher.

Fetches robots.txt for a given URL.
"""

import hashlib
from os import path
try:
    from urllib.robotparser import RobotFileParser
    from urllib.parse import urlsplit
except ImportError:
    from robotparser import RobotFileParser
    from urlparse import urlsplit

import thor

from redbot import __version__
from redbot.cache_file import CacheFile

UA_STRING = "RED/%s (https://redbot.org/)" % __version__

class RobotFetcher(thor.events.EventEmitter):
    """
    Fetch robots.txt and check to see if we're allowed.
    """
    check_name = "robot"
    response_phrase = "The robots.txt response"
    freshness_lifetime = 30 * 60
    client = thor.http.HttpClient()
    robot_checkers = {} # cache of robots.txt checkers
    robot_cache_dir = None
    robot_lookups = {}

    def check_robots(self, url, sync=False):
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
            else:
                self.emit("robot-%s" % url, True)
                return
        origin_hash = hashlib.sha1(origin.encode('ascii', 'replace')).hexdigest()

        if origin in self.robot_checkers:
            return self._robot_check(url, self.robot_checkers[origin], sync)

        if self.robot_cache_dir:
            robot_fd = CacheFile(path.join(self.robot_cache_dir, origin_hash))
            cached_robots_txt = robot_fd.read()
            if cached_robots_txt != None:
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
            def response_start(status, phrase, headers):
                exchange.status = status

            exchange.res_body = b""
            @thor.on(exchange)
            def response_body(chunk):
                exchange.res_body += chunk

            @thor.on(exchange)
            def response_done(trailers):
                if not exchange.status.startswith(b"2"):
                    robots_txt = b""
                else:
                    robots_txt = exchange.res_body

                self._load_checker(origin, robots_txt)
                if self.robot_cache_dir:
                    robot_fd = CacheFile(path.join(self.robot_cache_dir, origin_hash))
                    robot_fd.write(robots_txt, self.freshness_lifetime)

                while True:
                    try:
                        check_url = self.robot_lookups[origin].pop()
                    except KeyError:
                        break
                    self._robot_check(check_url, self.robot_checkers[origin])
                del self.robot_lookups[origin]

            @thor.on(exchange)
            def response_error(error):
                exchange.status = b"500"
                response_done([])

            p_url = urlsplit(url)
            robots_url = "%s://%s/robots.txt" % (p_url.scheme, p_url.netloc)
            exchange.request_start(b"GET", robots_url.encode('ascii'),
                                   [(b'User-Agent', UA_STRING.encode('ascii'))])
            exchange.request_done([])

    def _load_checker(self, origin, robots_txt):
        """Load a checker for an origin, given its robots.txt file."""
        if robots_txt == "": # empty or non-200
            checker = DummyChecker()
        else:
            checker = RobotFileParser()
            checker.parse(robots_txt.decode('ascii', 'replace').splitlines())
        self.robot_checkers[origin] = checker
        def del_checker():
            try:
                del self.robot_checkers[origin]
            except:
                pass
        thor.schedule(self.freshness_lifetime, del_checker)

    def _robot_check(self, url, robots_checker, sync=False):
        """Continue after getting the robots file."""
        result = robots_checker.can_fetch(UA_STRING, url)
        if sync:
            return result
        else:
            self.emit("robot-%s" % url, result)



def url_to_origin(url):
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


class DummyChecker(object):
    """Dummy checker for non-200 or empty responses."""
    def can_fetch(self, ua_string, url):
        return True
