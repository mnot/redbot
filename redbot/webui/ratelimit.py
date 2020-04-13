#!/usr/bin/env python

"""
Rate Limiting for RED, the Resource Expert Droid.
"""

from collections import defaultdict
from configparser import SectionProxy
from typing import Dict, Set, TYPE_CHECKING

import thor.loop

from redbot.formatter import Formatter
from redbot.webui.robot_check import url_to_origin

if TYPE_CHECKING:
    from redbot.webui import RedWebUi  # pylint: disable=cyclic-import,unused-import


class RateLimiter:
    limits = {}  # type: Dict[str, int]
    counts = {}  # type: Dict[str, Dict[str, int]]
    periods = {}  # type: Dict[str, float]
    watching = set()  # type: Set[str]
    running = False

    def __init__(self) -> None:
        self.loop = thor.loop

    def process(self, webui: "RedWebUi", formatter: Formatter) -> None:
        """Enforce limits on webui."""
        if not self.running:
            self.setup(webui.config)

        # enforce client limits
        client_id = webui.get_client_id()
        if client_id:
            try:
                self.increment("client_id", client_id)
            except RateLimitViolation:
                webui.error_response(
                    formatter,
                    b"429",
                    b"Too Many Requests",
                    "Your client is over limit. Please try later.",
                    "client over limit: %s" % client_id,
                )
                raise ValueError

        # enforce origin limits
        origin = url_to_origin(webui.test_uri)
        if origin:
            try:
                self.increment("origin", origin)
            except RateLimitViolation:
                webui.error_response(
                    formatter,
                    b"429",
                    b"Too Many Requests",
                    "Origin is over limit. Please try later.",
                    "origin over limit: %s" % origin,
                )
                raise ValueError

    def setup(self, config: SectionProxy) -> None:
        """Set up the counters for config."""
        client_limit = config.getint("limit_client_tests", fallback=0)
        if client_limit:
            client_period = config.getfloat("limit_client_period", fallback=1) * 3600
            self._setup("client_id", client_limit, client_period)

        origin_limit = config.getint("limit_origin_tests", fallback=0)
        if origin_limit:
            origin_period = config.getfloat("limit_origin_period", fallback=1) * 3600
            self._setup("origin", origin_limit, origin_period)
        self.running = True

    def _setup(self, metric_name: str, limit: int, period: float) -> None:
        """
        Set up a metric with a limit and a period (expressed in hours).
        Can be called multiple times.
        """
        if not metric_name in self.watching:
            self.limits[metric_name] = limit
            self.counts[metric_name] = defaultdict(int)
            self.periods[metric_name] = period
            self.loop.schedule(period, self.clear, metric_name)
            self.watching.add(metric_name)

    def increment(self, metric_name: str, discriminator: str) -> None:
        """
        Increment a metric for a discriminator.
        If the metric isn't set up, it will be ignored.
        Raises RateLimitViolation if this discriminator is over the limit.
        """
        if not metric_name in self.watching:
            return
        self.counts[metric_name][discriminator] += 1
        if self.counts[metric_name][discriminator] > self.limits[metric_name]:
            raise RateLimitViolation

    def clear(self, metric_name: str) -> None:
        """
        Clear a metric's counters.
        """
        self.counts[metric_name] = defaultdict(int)
        self.loop.schedule(self.periods[metric_name], self.clear, metric_name)


ratelimiter = RateLimiter()


class RateLimitViolation(Exception):
    pass
