#!/usr/bin/env python

"""
Subrequests to do things like range requests, content negotiation checks,
and validation.
"""

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2013 Mark Nottingham

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
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
