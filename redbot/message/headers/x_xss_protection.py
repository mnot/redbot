#!/usr/bin/env python

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.syntax import rfc7231

class x_xss_protection(headers.HttpHeader):
    canonical_name = u"X-XSS-Protection"
    description = u"""\
The `X-XSS-Protection` response header field can be sent by servers to control how
older versions of Internet Explorer configure their Cross Site Scripting protection."""
    reference = \
        u"https://blogs.msdn.microsoft.com/ieinternals/2011/01/31/controlling-the-xss-filter/"
    syntax = r'(?:[10](?:\s*;\s*%s)*)' % rfc7231.parameter
    list_header = False
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value, add_note):
        try:
            protect, param_str = field_value.split(';', 1)
        except ValueError:
            protect, param_str = field_value, ""
        try:
            protect = int(protect)
        except ValueError:
            raise
        params = headers.parse_params(param_str, add_note, True)
        if protect == 0:
            add_note(XSS_PROTECTION_OFF)
        else: # 1
            if params.get('mode', None) == "block":
                add_note(XSS_PROTECTION_BLOCK)
            else:
                add_note(XSS_PROTECTION_ON)
        return protect, params



class XSS_PROTECTION_ON(Note):
    category = categories.SECURITY
    level = levels.INFO
    summary = u"%(response)s enables XSS filtering in IE8+."
    text = u"""\
Recent versions of Internet Explorer have built-in Cross-Site Scripting (XSS) attack protection;
they try to automatically filter requests that fit a particular profile.

%(response)s has explicitly enabled this protection. If IE detects a Cross-site scripting attack,
it will "sanitise" the page to prevent the attack. In other words, the page will still render.

This header probably won't have any effect on other clients.

See [this blog entry](http://bit.ly/tJbICH) for more information."""


class XSS_PROTECTION_OFF(Note):
    category = categories.SECURITY
    level = levels.INFO
    summary = u"%(response)s disables XSS filtering in IE8+."
    text = u"""\
Recent versions of Internet Explorer have built-in Cross-Site Scripting (XSS) attack protection;
they try to automatically filter requests that fit a particular profile.

%(response)s has explicitly disabled this protection. In some scenarios, this is useful to do, if
the protection interferes with the application.

This header probably won't have any effect on other clients.

See [this blog entry](http://bit.ly/tJbICH) for more information."""

class XSS_PROTECTION_BLOCK(Note):
    category = categories.SECURITY
    level = levels.INFO
    summary = u"%(response)s blocks XSS attacks in IE8+."
    text = u"""\
Recent versions of Internet Explorer have built-in Cross-Site Scripting (XSS) attack protection;
they try to automatically filter requests that fit a particular profile.

Usually, IE will rewrite the attacking HTML, so that the attack is neutralised, but the content can
still be seen. %(response)s instructs IE to not show such pages at all, but rather to display an
error.

This header probably won't have any effect on other clients.

See [this blog entry](http://bit.ly/tJbICH) for more information."""



class OneXXSSTest(headers.HeaderTest):
    name = 'X-XSS-Protection'
    inputs = ['1']
    expected_out = (1, {})
    expected_err = [XSS_PROTECTION_ON]

class ZeroXXSSTest(headers.HeaderTest):
    name = 'X-XSS-Protection'
    inputs = ['0']
    expected_out = (0, {})
    expected_err = [XSS_PROTECTION_OFF]

class OneBlockXXSSTest(headers.HeaderTest):
    name = 'X-XSS-Protection'
    inputs = ['1; mode=block']
    expected_out = (1, {'mode': 'block'})
    expected_err = [XSS_PROTECTION_BLOCK]

class BadXXSSTest(headers.HeaderTest):
    name = 'X-XSS-Protection'
    inputs = ['foo']
    expected_out = None
    expected_err = [headers.BAD_SYNTAX]
