#!/usr/bin/env python

"""
Subrequests to do things like range requests, content negotiation checks,
and validation.
"""


from redbot.resource.active_check.conneg import ConnegCheck
from redbot.resource.active_check.range import RangeRequest
from redbot.resource.active_check.etag_validate import ETagValidate
from redbot.resource.active_check.lm_validate import LmValidate

checks = [ConnegCheck, RangeRequest, ETagValidate, LmValidate]

def start(resource):
    check_instances = [ac(resource, ac.check_name) for ac in checks]
    resource.add_check(*check_instances)
    for instance in check_instances:
        instance.check()
