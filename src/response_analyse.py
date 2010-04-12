#!/usr/bin/env python

"""
The Resource Expert Droid Response Analyser.

Provides two classes: ResponseHeaderParser and ResponseStatusChecker.

Both take a RedFetcher instance (post-done()) as their only argument.

ResponseHeaderParser will examine the response headers and set messages
on the RedFetcher instance as appropriate. It will also parse the
headers and populate parsed_hdrs.

ResponseStatusChecker will examine the response based upon its status
code and also set messages as appropriate.

ResponseHeaderParser MUST be called on the RedFetcher instance before
running ResponseStatusChecker, because it relies on the headers being
parsed.

See red.py for the main RED engine and webui.py for the Web front-end.
red_fetcher.py is the actual response fetching engine.
"""

__version__ = "1"
__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2010 Mark Nottingham

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

import calendar
import locale
import re
import time
from cgi import escape as e
from email.utils import parsedate as lib_parsedate
from urlparse import urljoin

import nbhttp.error
import red_speak as rs
from uri_validate import absolute_URI, URI_reference


# base URL for RFC2616 references
rfc2616 = "http://www.apps.ietf.org/rfc/rfc2616.html#%s"

### configuration
max_hdr_size = 4 * 1024
max_ttl_hdr = 20 * 1024

# generic syntax regexen (assume processing with re.VERBOSE)
TOKEN = r'(?:[!#\$%&\'\*\+\-\.\^_`|~A-Za-z0-9]+?)'
QUOTED_STRING = r'(?:"(?:[ \t\x21\x23-\x5B\x5D-\x7E]|\\[\x01-\x09\x0B-\x0C\x0E\xFF])*")'
PARAMETER = r'(?:%(TOKEN)s(?:=(?:%(TOKEN)s|%(QUOTED_STRING)s))?)' % locals()
TOK_PARAM = r'(?:%(TOKEN)s(?:\s*;\s*%(PARAMETER)s)*)' % locals()
PRODUCT = r'(?:%(TOKEN)s(?:/%(TOKEN)s)?)' % locals()
COMMENT = r"""(?:
    \((?:
        [^\(\)] |
        \\\( |
        \\\) |
        (?:
            \((?:
                [^\(\)] |
                \\\( |
                \\\) |
                (?:
                    \((?:
                        [^\(\)] |
                        \\\( |
                        \\\)
                    )*\)
                )
            )*\)
        )
    )*\)
)""" # only handles two levels of nested comments; does not check chars
COMMA = r'(?:\s*(?:,\s*)+)'
DIGITS = r'(?:[0-9]+)'
DATE = r"""(?:\w{3},\ [0-9]{2}\ \w{3}\ [0-9]{4}\ [0-9]{2}:[0-9]{2}:[0-9]{2}\ GMT |
         \w{6,9},\ [0-9]{2}\-\w{3}\-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}\ GMT |
         \w{3}\ \w{3}\ [0-9 ][0-9]\ [0-9]{2}:[0-9]{2}:[0-9]{2}\ [0-9]{4})
        """


def GenericHeaderSyntax(meth):
    """
    Decorator to take a list of header values, split on commas (except where
    escaped) and return a list of header field-values. This will not work for
    Set-Cookie (which contains an unescaped comma) and similar headers
    containing bare dates.

    E.g.,
      ["foo,bar", "baz, bat"]
    becomes
      ["foo", "bar", "baz", "bat"]
    """
    def new(self, name, values):
        values = sum(
            [[f.strip() for f in re.findall(r'((?:[^",]|%s)+)(?=%s|\s*$)' %
             (QUOTED_STRING, COMMA), v)] for v in values], []
        ) or ['']
        return meth(self, name, values)
    return new

def SingleFieldValue(meth):
    """
    Decorator to make sure that there's only one value.
    """
    def new(self, name, values):
        if len(values) > 1:
            self.setMessage(name, rs.SINGLE_HEADER_REPEAT)
        return meth(self, name, values)
    return new

def CheckFieldSyntax(exp, ref):
    """
    Decorator to check each header field-value to conform to the regex exp,
    and if not to point users to url ref.
    """
    def wrap(meth):
        def new(self, name, values):
            for value in values:
                if not re.match(r"^\s*(?:%s)\s*$" % exp, value, re.VERBOSE):
                    self.setMessage(name, rs.BAD_SYNTAX, ref_uri=ref)
                    def bad_syntax(self, name, values):
                        return None
                    return bad_syntax(self, name, values)
            return meth(self, name, values)
        return new
    return wrap

class ResponseHeaderParser(object):
    """
    Parse and check the response for obvious syntactic errors,
    as well as semantic errors that are self-contained (i.e.,
    it can be determined without examining other headers, etc.).
    """
    def __init__(self, red):
        self.red = red
        hdr_dict = {}
        header_block_size = len(red.res_phrase) + 13
        clean_res_hdrs = []
        for name, value in red.res_hdrs:
            hdr_size = len(name) + len(value)
            if hdr_size > max_hdr_size:
                self.setMessage(name.lower(), rs.HEADER_TOO_LARGE,
                                header_name=name, header_size=f_num(hdr_size))
            header_block_size += hdr_size
            try:
                name = name.decode('ascii', 'strict')
            except UnicodeError:
                name = name.decode('ascii', 'ignore')
                self.setMessage('%s' % name.lower(), rs.HEADER_NAME_ENCODING,
                                header_name=name)
            try:
                value = value.decode('ascii', 'strict')
            except UnicodeError:
                value = value.decode('iso-8859-1', 'replace')
                self.setMessage('%s' % name.lower(), rs.HEADER_VALUE_ENCODING,
                                header_name=name)
            clean_res_hdrs.append((name, value))
            if not re.match("^\s*%s\s*$" % TOKEN, name):
                self.setMessage(name, rs.FIELD_NAME_BAD_SYNTAX)
            norm_name = name.lower()
            value = value.strip()
            if hdr_dict.has_key(norm_name):
                hdr_dict[norm_name][1].append(value)
            else:
                hdr_dict[norm_name] = (name, [value])
        # replace the original header tuple with ones that are clean unicode
        red.res_hdrs = clean_res_hdrs
        # check the total header block size
        if header_block_size > max_ttl_hdr:
            self.setMessage('header', rs.HEADER_BLOCK_TOO_LARGE,
                            header_block_size=f_num(header_block_size))
        # build a dictionary of header values
        for nn, (fn, values) in hdr_dict.items():
            name_token = nn.replace('-', '_')
            # anything starting with an underscore or with any caps won't match
            if hasattr(self, name_token):
                parsed_value = getattr(self, name_token)(fn, values)
                if parsed_value != None:
                    self.red.parsed_hdrs[nn] = parsed_value

    def setMessage(self, name, msg, **vars):
        ident = 'header-%s' % name.lower()
        self.red.setMessage(ident, msg, field_name=name, **vars)

    @staticmethod
    def _parseDate(values):
        """Parse a HTTP date. Raises ValueError if it's bad."""
        value = values[-1]
        if not re.match(r"%s$" % DATE, value, re.VERBOSE):
            raise ValueError
        date_tuple = lib_parsedate(value)
        if date_tuple is None:
            raise ValueError
        # http://sourceforge.net/tracker/index.php?func=detail&aid=1194222&group_id=5470&atid=105470
        if date_tuple[0] < 100:
            if date_tuple[0] > 68:
                date_tuple = (date_tuple[0]+1900,)+date_tuple[1:]
            else:
                date_tuple = (date_tuple[0]+2000,)+date_tuple[1:]
        date = calendar.timegm(date_tuple)
        return date

    @staticmethod
    def _unquoteString(instr):
        """
        Unquote a string; does NOT unquote control characters.

        @param instr: string to be unquoted
        @type instr: string
        @return: unquoted string
        @rtype: string
        """
        instr = str(instr).strip()
        if not instr or instr == '*':
            return instr
        if instr[0] == instr[-1] == '"':
            instr = instr[1:-1]
            instr = re.sub(r'\\(.)', r'\1', instr)
        return instr

    @staticmethod
    def _splitString(instr, item, split):
        """
        Split instr as a list of items separated by splits.

        @param instr: string to be split
        @param item: regex for item to be split out
        @param split: regex for splitter
        @return: list of strings
        """
        if not instr:
            return []
        return [h.strip() for h in re.findall(r'%s(?=%s|\s*$)' % (item, split), instr)]

    @GenericHeaderSyntax
    def accept_ranges(self, name, values):
        for value in values:
            if value not in ['bytes', 'none']:
                self.setMessage(name, rs.UNKNOWN_RANGE)
                break
        return values

    @GenericHeaderSyntax
    @SingleFieldValue
    @CheckFieldSyntax(DIGITS, rfc2616 % "sec-14.6")
    def age(self, name, values):
        try:
            age = int(values[-1])
        except ValueError:
            self.setMessage(name, rs.AGE_NOT_INT)
            return None
        if age < 0:
            self.setMessage(name, rs.AGE_NEGATIVE)
            return None
        return age

    @GenericHeaderSyntax
    @CheckFieldSyntax(TOKEN, rfc2616 % "sec-14.7")
    def allow(self, name, values):
        return values

    @GenericHeaderSyntax
    @CheckFieldSyntax(PARAMETER, rfc2616 % "sec-14.9")
    def cache_control(self, name, values):
        directives = set()
        for directive in values:
            try:
                attr, value = directive.split("=", 1)
                value = self._unquoteString(value)
            except ValueError:
                attr = directive
                value = None
            if attr in ['max-age', 's-maxage']:
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    self.setMessage(name, rs.BAD_CC_SYNTAX, bad_cc_attr=attr)
                    continue
            directives.add((attr, value))
        return directives

    @SingleFieldValue
    def content_base(self, name, values):
        self.setMessage(name, rs.HEADER_DEPRECATED, ref=rfc2616 % "sec-19.6.3")
        return values[-1]

    def content_disposition(self, name, values):
        # TODO: check syntax, parse
        pass

    @GenericHeaderSyntax
    @CheckFieldSyntax(TOKEN, rfc2616 % "sec-14.11")
    def content_encoding(self, name, values):
        values = [v.lower() for v in values]
        for value in values:
            # check to see if there are any non-gzip encodings, because
            # that's the only one we ask for.
            if value != 'gzip':
                self.setMessage(name, rs.ENCODING_UNWANTED, encoding=e(value))
                break
        return values

    @GenericHeaderSyntax
    @SingleFieldValue
    @CheckFieldSyntax(DIGITS, rfc2616 % "sec-14.13")
    def content_length(self, name, values):
        return int(values[-1])

    @SingleFieldValue
    def content_md5(self, name, values):
        return values[-1]

    def content_range(self, name, values):
        # TODO: check syntax, values?
        if self.red.res_status not in ["206", "416"]:
            self.setMessage(name, rs.CONTENT_RANGE_MEANINGLESS)
        return values

    @GenericHeaderSyntax
    @CheckFieldSyntax(r'(?:%(TOKEN)s/%(TOKEN)s(?:\s*;\s*%(PARAMETER)s)*)' % globals(),
                      rfc2616 % "sec-14.17")
    @SingleFieldValue
    def content_type(self, name, values):
        try:
            media_type, params = values[-1].split(";", 1)
        except ValueError:
            media_type, params = values[-1], ''
        media_type = media_type.lower()
        param_dict = {}
        for param in self._splitString(params, PARAMETER, "\s*;\s*"):
            try:
                a, v = param.split("=", 1)
                param_dict[a.lower()] = self._unquoteString(v)
            except ValueError:
                param_dict[param.lower()] = None
        return media_type, param_dict

    @SingleFieldValue
    def date(self, name, values):
        try:
            date = self._parseDate(values)
        except ValueError:
            self.setMessage(name, rs.BAD_DATE_SYNTAX)
            return None
        return date

    @SingleFieldValue
    def expires(self, name, values):
        try:
            date = self._parseDate(values)
        except ValueError:
            self.setMessage(name, rs.BAD_DATE_SYNTAX)
            return None
        return date

    @GenericHeaderSyntax
    @SingleFieldValue
    @CheckFieldSyntax(r'\*|(?:W/)?%s' % QUOTED_STRING, rfc2616 % "sec-14.19")
    def etag(self, name, values):
        instr = values[-1]
        if instr[:2] == 'W/':
            return (True, self._unquoteString(instr[2:]))
        else:
            return (False, self._unquoteString(instr))

    @GenericHeaderSyntax
    def keep_alive(self, name, values):
        directives = set()
        for directive in values:
            try:
                attr, value = directive.split("=", 1)
                value = self._unquoteString(value)
            except ValueError:
                attr = directive
                value = None
            attr = attr.lower()
            directives.add((attr, value))
        return values

    @SingleFieldValue
    def last_modified(self, name, values):
        try:
            date = self._parseDate(values)
        except ValueError:
            self.setMessage(name, rs.BAD_DATE_SYNTAX)
            return None
        if date > self.red.timestamp:
            self.setMessage(name, rs.LM_FUTURE)
            return
        else:
            self.setMessage(name, rs.LM_PRESENT,
              last_modified_string=relative_time(date, self.red.timestamp))
        return date

    @GenericHeaderSyntax
    def link(self, name, values):
        # TODO: check syntax, values?
        pass

    # The most common problem with Location is a non-absolute URI, so we separate
    # that from the syntax check.
    @CheckFieldSyntax(URI_reference, rfc2616 % "sec-14.30")
    @SingleFieldValue
    def location(self, name, values):
        if self.red.res_status not in ["201", "300", "301", "302", "303", "305", "307"]:
            self.setMessage(name, rs.LOCATION_UNDEFINED)
        if not re.match(r"^\s*(?:%s)\s*$" % absolute_URI, values[-1], re.VERBOSE):
            self.setMessage(name, rs.LOCATION_NOT_ABSOLUTE,
                            full_uri=e(urljoin(self.red.uri, values[-1])))
        return values[-1]

    def mime_version(self, name, values):
        self.setMessage(name, rs.MIME_VERSION)
        return values

    @GenericHeaderSyntax
    def p3p(self, name, values):
        # TODO: check syntax, values
        pass

    @GenericHeaderSyntax
    def pragma(self, name, values):
        values = set([v.lower() for v in values])
        if "no-cache" in values:
            self.setMessage(name, rs.PRAGMA_NO_CACHE)
        others = [True for v in values if v != "no-cache"]
        if others:
            self.setMessage(name, rs.PRAGMA_OTHER)
        return values

    @GenericHeaderSyntax
    @CheckFieldSyntax(r"(?:%s|%s)" % (DIGITS, DATE), rfc2616 % "sec-14.37")
    @SingleFieldValue
    def retry_after(self, name, values):
        pass

    def server(self, name, values):
        # TODO: check syntax, flag servers?
        pass

    @SingleFieldValue
    def soapaction(self, name, values):
        return values[-1]

    def set_cookie(self, name, values):
        # TODO: check syntax, values?
        pass

    @GenericHeaderSyntax
    def tcn(self, name, values):
        # TODO: check syntax, values?
        pass

    @GenericHeaderSyntax
    @CheckFieldSyntax(TOK_PARAM, rfc2616 % "sec-14.41")
    # TODO: accommodate transfer-parameters
    def transfer_encoding(self, name, values):
        values = [v.lower() for v in values]
        if 'identity' in values:
            self.setMessage(name, rs.TRANSFER_CODING_IDENTITY)
        for value in values:
            # check to see if there are any non-chunked encodings, because
            # that's the only one we ask for.
            if value not in ['chunked', 'identity']:
                self.setMessage(name, rs.TRANSFER_CODING_UNWANTED,
                                encoding=e(value))
                break
        return values

    @GenericHeaderSyntax
    @CheckFieldSyntax(TOKEN, rfc2616 % "sec-14.44")
    def vary(self, name, values):
        values = set([v.lower() for v in values])
        return values

    @GenericHeaderSyntax
    @CheckFieldSyntax(r'(?:%s/)?%s\s+[^,\s]+(?:\s+%s)?' % (TOKEN, TOKEN, COMMENT),
                      rfc2616 % "sec-14.45")
    def via(self, name, values):
        via_list = u"<ul>" + u"\n".join(
               [u"<li><code>%s</code></li>" % e(v) for v in values]
                           ) + u"</ul>"
        self.setMessage(name, rs.VIA_PRESENT, via_list=via_list)

    @GenericHeaderSyntax
    def warning(self, name, values):
        # TODO: check syntax, values?
        pass

    @GenericHeaderSyntax
    def x_cache(self, name, values):
        # TODO: explain
        pass

    @GenericHeaderSyntax
    def x_content_type_options(self, name, values):
        if 'nosniff' in values:
            self.setMessage(name, rs.CONTENT_TYPE_OPTIONS)
        else:
            self.setMessage(name, rs.CONTENT_TYPE_OPTIONS_UNKNOWN)
        return values

    @GenericHeaderSyntax
    def x_download_options(self, name, values):
        if 'noopen' in values:
            self.setMessage(name, rs.DOWNLOAD_OPTIONS)
        else:
            self.setMessage(name, rs.DOWNLOAD_OPTIONS_UNKNOWN)
        return values

    @GenericHeaderSyntax
    def x_frame_options(self, name, values):
        if 'DENY' in values:
            self.setMessage(name, rs.FRAME_OPTIONS_DENY)
        elif 'SAMEORIGIN' in values:
            self.setMessage(name, rs.FRAME_OPTIONS_SAMEORIGIN)
        else:
            self.setMessage(name, rs.FRAME_OPTIONS_UNKNOWN)
        return values

    @GenericHeaderSyntax
    def x_meta_mssmarttagspreventparsing(self, name, values):
        self.setMessage(name, rs.SMART_TAG_NO_WORK)
        return values

    @GenericHeaderSyntax
    @CheckFieldSyntax(PARAMETER, "http://msdn.microsoft.com/en-us/library/cc288325(VS.85).aspx")
    def x_ua_compatible(self, name, values):
        directives = {}
        for directive in values:
            try:
                attr, value = directive.split("=", 1)
            except ValueError:
                attr = directive
                value = None
            if directives.has_key(attr):
                self.setMessage(name, rs.UA_COMPATIBLE_REPEAT)
            directives[attr] = value
        uac_list = u"\n".join([u"<li>%s - %s</li>" % (e(k), e(v)) for
                            k, v in directives.items()])
        self.setMessage(name, rs.UA_COMPATIBLE, uac_list=uac_list)
        return directives


    @GenericHeaderSyntax
    @SingleFieldValue
    @CheckFieldSyntax(DIGITS, 'http://blogs.msdn.com/ie/archive/2008/07/02/ie8-security-part-iv-the-xss-filter.aspx')
    def x_xss_protection(self, name, values):
        if int(values[-1]) == 0:
            self.setMessage(name, rs.XSS_PROTECTION)
        return values[-1]

    @GenericHeaderSyntax
    @SingleFieldValue
    def x_xrds_location(self, name, values):
        pass

    @SingleFieldValue
    def x_pingback(self, name, values):
        #TODO: message, perhaps allow a ping
        pass

class ResponseStatusChecker:
    """
    Given a RED, check out the status
    code and perform appropriate tests on it.
    """
    def __init__(self, red):
        self.red = red
        try:
            getattr(self, "status%s" % red.res_status)()
        except AttributeError:
            self.setMessage('status', rs.STATUS_NONSTANDARD)

    def setMessage(self, name, msg, **vars):
        if name:
            ident = 'status %s' % name
        else:
            ident = 'status'
        self.red.setMessage(ident, msg,
                             status=self.red.res_status,
                             enc_status=e(self.red.res_status),
                             **vars
                             )

    def status100(self):        # Continue
        if not "100-continue" in nbhttp.get_hdr(self.red.req_hdrs, 'expect'):
            self.setMessage('', rs.UNEXPECTED_CONTINUE)
    def status101(self):        # Switching Protocols
        if not 'upgrade' in nbhttp.header_dict(self.red.req_hdrs).keys():
            self.setMessage('', rs.UPGRADE_NOT_REQUESTED)
    def status102(self):        # Processing
        pass
    def status200(self):        # OK
        pass
    def status201(self):        # Created
        if self.red.method in nbhttp.safe_methods:
            self.setMessage('status', rs.CREATED_SAFE_METHOD, method=self.red.method)
        if not self.red.parsed_hdrs.has_key('location'):
            self.setMessage('header-location', rs.CREATED_WITHOUT_LOCATION)
    def status202(self):        # Accepted
        pass
    def status203(self):        # Non-Authoritative Information
        pass
    def status204(self):        # No Content
        pass
    def status205(self):        # Reset Content
        pass
    def status206(self):        # Partial Content
        if not "range" in nbhttp.header_dict(self.red.req_hdrs).keys():
            self.setMessage('', rs.PARTIAL_NOT_REQUESTED)
        if not self.red.parsed_hdrs.has_key('content-range'):
            print self.red.parsed_hdrs.keys()
            self.setMessage('header-location', rs.PARTIAL_WITHOUT_RANGE)
    def status207(self):        # Multi-Status
        pass
    def status226(self):        # IM Used
        pass
    def status300(self):        # Multiple Choices
        pass
    def status301(self):        # Moved Permanently
        if not self.red.parsed_hdrs.has_key('location'):
            self.setMessage('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status302(self):        # Found
        if not self.red.parsed_hdrs.has_key('location'):
            self.setMessage('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status303(self):        # See Other
        if not self.red.parsed_hdrs.has_key('location'):
            self.setMessage('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status304(self):        # Not Modified
        pass # TODO: check to make sure required headers are present, stable
    def status305(self):        # Use Proxy
        self.setMessage('', rs.STATUS_DEPRECATED)
    def status306(self):        # Reserved
        self.setMessage('', rs.STATUS_RESERVED)
    def status307(self):        # Temporary Redirect
        if not self.red.parsed_hdrs.has_key('location'):
            self.setMessage('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status400(self):        # Bad Request
        self.setMessage('', rs.STATUS_BAD_REQUEST)
    def status401(self):        # Unauthorized
        pass # TODO: prompt for credentials
    def status402(self):        # Payment Required
        pass
    def status403(self):        # Forbidden
        self.setMessage('', rs.STATUS_FORBIDDEN)
    def status404(self):        # Not Found
        self.setMessage('', rs.STATUS_NOT_FOUND)
    def status405(self):        # Method Not Allowed
        pass # TODO: show allowed methods?
    def status406(self):        # Not Acceptable
        self.setMessage('', rs.STATUS_NOT_ACCEPTABLE)
    def status407(self):        # Proxy Authentication Required
        pass
    def status408(self):        # Request Timeout
        pass
    def status409(self):        # Conflict
        self.setMessage('', rs.STATUS_CONFLICT)
    def status410(self):        # Gone
        self.setMessage('', rs.STATUS_GONE)
    def status411(self):        # Length Required
        pass
    def status412(self):        # Precondition Failed
        pass # TODO: test to see if it's true, alert if not
    def status413(self):        # Request Entity Too Large
        self.setMessage('', rs.STATUS_REQUEST_ENTITY_TOO_LARGE)
    def status414(self):        # Request-URI Too Long
        self.setMessage('uri', rs.STATUS_URI_TOO_LONG,
                        uri_len=len(self.red.uri))
    def status415(self):        # Unsupported Media Type
        self.setMessage('', rs.STATUS_UNSUPPORTED_MEDIA_TYPE)
    def status416(self):        # Requested Range Not Satisfiable
        pass # TODO: test to see if it's true, alter if not
    def status417(self):        # Expectation Failed
        pass # TODO: explain, alert if it's 100-continue
    def status422(self):        # Unprocessable Entity
        pass
    def status423(self):        # Locked
        pass
    def status424(self):        # Failed Dependency
        pass
    def status426(self):        # Upgrade Required
        pass
    def status500(self):        # Internal Server Error
        self.setMessage('', rs.STATUS_INTERNAL_SERVICE_ERROR)
    def status501(self):        # Not Implemented
        self.setMessage('', rs.STATUS_NOT_IMPLEMENTED)
    def status502(self):        # Bad Gateway
        self.setMessage('', rs.STATUS_BAD_GATEWAY)
    def status503(self):        # Service Unavailable
        self.setMessage('', rs.STATUS_SERVICE_UNAVAILABLE)
    def status504(self):        # Gateway Timeout
        self.setMessage('', rs.STATUS_GATEWAY_TIMEOUT)
    def status505(self):        # HTTP Version Not Supported
        self.setMessage('', rs.STATUS_VERSION_NOT_SUPPORTED)
    def status506(self):        # Variant Also Negotiates
        pass
    def status507(self):        # Insufficient Storage
        pass
    def status510(self):        # Not Extended
        pass


def f_num(instr):
    "Format a number according to the locale."
    return locale.format("%d", instr, grouping=True)


def relative_time(utime, now=None, show_sign=1):
    '''
    Given two times, return a string that explains how far apart they are.
    show_sign can be:
      0 - don't show
      1 - ago / from now  [DEFAULT]
      2 - early / late
     '''

    signs = {
        0:    ('0', '', ''),
        1:    ('now', 'ago', 'from now'),
        2:    ('none', 'behind', 'ahead'),
    }

    if  utime == None:
        return None
    if now == None:
        now = time.time()
    age = int(now - utime)
    if age == 0:
        return signs[show_sign][0]

    a = abs(age)
    yrs = int(a / 60 / 60 / 24 / 7 / 52)
    wks = int(a / 60 / 60 / 24 / 7) % 52
    day = int(a / 60 / 60 / 24) % 7
    hrs = int(a / 60 / 60) % 24
    mnt = int(a / 60) % 60
    sec = int(a % 60)

    if age > 0:
        sign = signs[show_sign][1]
    else:
        sign = signs[show_sign][2]
    if not sign:
        sign = signs[show_sign][0]

    arr = []
    if yrs == 1:
        arr.append(str(yrs) + ' year')
    elif yrs > 1:
        arr.append(str(yrs) + ' years')
    if wks == 1:
        arr.append(str(wks) + ' week')
    elif wks > 1:
        arr.append(str(wks) + ' weeks')
    if day == 1:
        arr.append(str(day) + ' day')
    elif day > 1:
        arr.append(str(day) + ' days')
    if hrs:
        arr.append(str(hrs) + ' hr')
    if mnt:
        arr.append(str(mnt) + ' min')
    if sec:
        arr.append(str(sec) + ' sec')
    arr = arr[:2]        # resolution
    if show_sign:
        arr.append(sign)
    return " ".join(arr)

