#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

description = u"""\
The `X-XSS-Protection` response header field can be sent by servers to control how
older versions of Internet Explorer configure their Cross Site Scripting protection.
"""

reference = u"https://blogs.msdn.microsoft.com/ieinternals/2011/01/31/controlling-the-xss-filter/"

@rh.ResponseOrPutHeader
@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(
    r'(?:[10](?:\s*;\s*%(PARAMETER)s)*)' % syntax.__dict__, 'http://blogs.msdn.com/b/ieinternals/archive/2011/01/31/controlling-the-internet-explorer-xss-filter-with-the-x-xss-protection-http-header.aspx'
)
def parse(subject, value, red):
    try:
        protect, param_str = value.split(';', 1)
    except ValueError:
        protect, param_str = value, ""
    protect = int(protect)
    params = rh.parse_params(red, subject, param_str, True)
    if protect == 0:
        red.add_note(subject, rs.XSS_PROTECTION_OFF)
    else: # 1
        if params.get('mode', None) == "block":
            red.add_note(subject, rs.XSS_PROTECTION_BLOCK)
        else:
            red.add_note(subject, rs.XSS_PROTECTION_ON)
    return protect, params

@rh.SingleFieldValue
def join(subject, values, red):
    return values[-1]


class OneXXSSTest(rh.HeaderTest):
    name = 'X-XSS-Protection'
    inputs = ['1']
    expected_out = (1, {})
    expected_err = [rs.XSS_PROTECTION_ON]

class ZeroXXSSTest(rh.HeaderTest):
    name = 'X-XSS-Protection'
    inputs = ['0']
    expected_out = (0, {})
    expected_err = [rs.XSS_PROTECTION_OFF]

class OneBlockXXSSTest(rh.HeaderTest):
    name = 'X-XSS-Protection'
    inputs = ['1; mode=block']
    expected_out = (1, {'mode': 'block'})
    expected_err = [rs.XSS_PROTECTION_BLOCK]
    
class BadXXSSTest(rh.HeaderTest):
    name = 'X-XSS-Protection'
    inputs = ['foo']
    expected_out = None
    expected_err = [rs.BAD_SYNTAX]
