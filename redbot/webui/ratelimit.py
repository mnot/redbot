"""
Rate Limiting for RED, the Resource Expert Droid.
"""

from collections import defaultdict
from configparser import SectionProxy
from typing import Dict, Set, Union, Callable, TYPE_CHECKING
from urllib.parse import urlsplit

import thor.loop

if TYPE_CHECKING:
    from redbot.webui import RedWebUi  # pylint: disable=cyclic-import,unused-import


class RateLimiter:
    limits: Dict[str, int] = {}
    counts: Dict[str, Dict[str, int]] = {}
    periods: Dict[str, float] = {}
    watching: Set[str] = set()
    running = False

    def __init__(self) -> None:
        self.loop = thor.loop

    def process(
        self, webui: "RedWebUi", test_uri: str, error_response: Callable
    ) -> None:
        """Enforce limits on webui."""
        if not self.running:
            self.setup(webui.config)

        # enforce client limits
        client_id = webui.get_client_id()
        if client_id:
            try:
                self.increment("client_id", client_id)
                self.increment("instant", client_id)
            except RateLimitViolation:
                error_response(
                    b"429",
                    b"Too Many Requests",
                    "Your client is over limit. Please try later.",
                )
                raise ValueError  # pylint: disable=raise-missing-from

        # enforce origin limits
        origin = url_to_origin(test_uri)
        if origin:
            try:
                self.increment("origin", origin)
            except RateLimitViolation:
                error_response(
                    b"429",
                    b"Too Many Requests",
                    "Origin is over limit. Please try later.",
                    f"origin over limit: {origin}",
                )
                raise ValueError  # pylint: disable=raise-missing-from

    def setup(self, config: SectionProxy) -> None:
        """Set up the counters for config."""
        instant_limit = config.getint("instant_limit", fallback=0)
        if instant_limit:
            self._setup("instant", instant_limit, 15)

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


def url_to_origin(url: str) -> Union[str, None]:
    "Convert an URL to an RFC6454 Origin."
    default_port = {"http": 80, "https": 443}
    try:
        p_url = urlsplit(url)
        origin = (
            f"{p_url.scheme.lower()}://"
            f"{(p_url.hostname or '').lower()}:"
            f"{p_url.port or default_port.get(p_url.scheme, 0)}"
        )
    except (AttributeError, ValueError):
        origin = None
    return origin
