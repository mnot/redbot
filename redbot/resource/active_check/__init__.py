#!/usr/bin/env python

"""
Subrequests to do things like range requests, content negotiation checks,
and validation.
"""


from redbot.resource.active_check.conneg import ConnegCheck
from redbot.resource.active_check.range import RangeRequest
from redbot.resource.active_check.etag_validate import ETagValidate
from redbot.resource.active_check.lm_validate import LmValidate


class ActiveChecks(object):
    checks = [ConnegCheck, RangeRequest, ETagValidate, LmValidate]

    def __init__(self, resource):
        self.check_instances = [ac(resource, ac.check_name) for ac in self.checks]
        resource.add_check(*self.check_instances)

    def check(self):
        "Run all active checks against resource."
        for instance in self.check_instances:
            instance.check()
