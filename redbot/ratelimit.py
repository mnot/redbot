#!/usr/bin/env python

"""
Rate Limiting for RED, the Resource Expert Droid.
"""

from collections import defaultdict
from typing import Dict, Set

import thor.loop


class RateLimiter:
    limits = {}  # type: Dict[str, int]
    counts = {}  # type: Dict[str, Dict[str, int]]
    periods = {} # type: Dict[str, int]
    watching = set() # type: Set[str]

    def __init__(self) -> None:
        self.loop = thor.loop

    def setup(self, metric_name: str, limit: int, period: int) -> None:
        """
        Set up a metric with a limit and a period.
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
