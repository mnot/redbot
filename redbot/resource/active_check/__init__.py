#!/usr/bin/env python

"""
Subrequests to do things like range requests, content negotiation checks,
and validation.
"""


from redbot.resource.active_check.conneg import ConnegCheck
from redbot.resource.active_check.range import RangeRequest
from redbot.resource.active_check.etag_validate import ETagValidate
from redbot.resource.active_check.lm_validate import LmValidate

def spawn_all(resource):
    "Run all active checks against resource."
    resource.add_task(ConnegCheck(resource, 'Identity').run)
    resource.add_task(RangeRequest(resource, 'Range').run)
    resource.add_task(ETagValidate(resource, 'If-None-Match').run)
    resource.add_task(LmValidate(resource, 'If-Modified-Since').run)
