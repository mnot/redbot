#!/usr/bin/env python

"""
red.py - the Resource Expert Droid. See webui.py for the Web front-end.

Copyright (c) 2008-2009 Mark Nottingham

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

__version__ = "1"

import re
import time
import calendar 
import socket
import base64
import hashlib
import zlib
from email.utils import parsedate as lib_parsedate
from cgi import escape as e

import http_client
import red_speak as rs


# generic syntax regexen
TOKEN = r'(?:[^\(\)<>@,;:\\"/\[\]\?={} \t]+?)'
STRING = r'(?:[^,]+)'
QUOTED_STRING = r'(?:"(?:\\"|[^"])*")'
PARAMETER = r'(?:%(TOKEN)s(?:=(?:%(TOKEN)s|%(QUOTED_STRING)s))?)' % locals()
STRPARAM = r'(?:\S+(?:\s*;\s*%(PARAMETER)s)*)' % locals()
PRODUCT = r'(?:%(TOKEN)s(?:/%(TOKEN)s)?)' % locals()
COMMENT = r'(?:\((?:[^\(\)]|\\\(|\\\))*\))' # does not handle nesting
URI = r'(?:(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?)'  # RFC3986
COMMA = r'(?:\s*(?:,\s*)+)'
DIGITS = r'(?:\d+)'
DATE = r'(?:\w{3}, \d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2} GMT|\w{6,9}, \d{2}\-\w{3}\-\d{2} \d{2}:\d{2}:\d{2} GMT|\w{3} \w{3} [\d ]\d \d{2}:\d{2}:\d{2} \d{4})'

### configuration
cacheable_methods = ['GET']
heuristic_cacheable_status = ['200', '203', '206', '300', '301', '410']
max_uri = 8 * 1024
max_hdr_size = 4 * 1024
max_ttl_hdr = 20 * 1024
max_clock_skew = 5  # seconds
connect_timeout = 5 # seconds

# TODO: resource limits
# TODO: special case for content-* headers and HEAD responses, partial responses.

class ResourceExpertDroid(object):
    def __init__(self, uri, method="GET", req_headers=None, 
                 body_processors=[], status_cb=None):
        self.status_cb = status_cb     # tells caller how we're doing
        self.method = method
        if req_headers != None:
            self.req_headers = req_headers
        else:
            self.req_headers = []
        self.messages = []             # holds messages
        self.response = None           # holds the "main" response

        # check the URI
        if not re.match("^\s*%s\s*$" % URI, uri):
            self.setMessage('uri', rs.URI_BAD_SYNTAX)
        if len(uri) > max_uri:
            self.setMessage('uri', rs.URI_TOO_LONG, uri_len=len(uri))
            
        # make the primary request
        def primary_response_done(response):
            self.response = response
            ResponseStatusChecker(self.response, self.setMessage)
            # TODO: make this into a plug-in system
            self.checkClock()
            self.checkBody()
            self.checkCaching()
            self.checkConneg()
            self.checkEtagValidation()
            self.checkLmValidation()
            self.checkRanges()
        self.req_headers.append(('Accept-Encoding', 'gzip'))
        try:
            makeRequest(uri, method=self.method, req_headers=self.req_headers,
                done_cb=primary_response_done, status_cb=status_cb, set_message=self.setMessage,
                body_processors=body_processors, reason=self.method)
            http_client.run()
        except socket.gaierror:
            raise AssertionError, "Hostname not found."

    def checkRanges(self):
        if 'bytes' in self.response.parsed_hdrs.get('accept-ranges', []):
            range_status = None
            range_start = int(len(self.response.body) * 0.5)
            range_end = int(len(self.response.body) * 0.75)
            if range_start == range_end: return # wow, that's a small body.
            def range_done(range_res):
                if range_res.status == '206':
                    # TODO: check entity headers
                    # TODO: check content-range
                    if ('gzip' in self.response.parsed_hdrs.get('accept-ranges', [])) == \
                       ('gzip' not in range_res.parsed_hdrs.get('accept-ranges', [])):
                        self.setMessage('header-accept-ranges header-content-encoding', 
                                        rs.RANGE_NEG_MISMATCH)
                        return
                    if range_res.body == self.response.body[range_start:range_end+1]:
                        self.setMessage('header-accept-ranges', rs.RANGE_CORRECT)
                    else:
                        self.setMessage('header-accept-ranges', rs.RANGE_INCORRECT,
                            range_expected=e(self.response.body[range_start:range_end+1]),
                            range_received=e(range_res.body)
                        ) 
                elif range_res.status == self.response.status:
                    self.setMessage('header-accept-ranges', rs.RANGE_FULL)
                else:
                    self.setMessage('header-accept-ranges', rs.RANGE_STATUS, 
                                    range_status=range_res.status)
            makeRequest(self.response.uri, req_headers=[
                ('Range', "bytes=%s-%s" % (range_start, range_end)), 
                ('Accept-Encoding', 'gzip')
                ], 
                done_cb=range_done, status_cb=self.status_cb, 
                reason="Range")

    def checkBody(self):
        if self.response.parsed_hdrs.has_key('content-length'):
            if self.response.body_len == self.response.parsed_hdrs['content-length']:
                self.setMessage('header-content-length', rs.CL_CORRECT)
            else:
                self.setMessage('header-content-length', rs.CL_INCORRECT, 
                                body_length=self.response.body_len)
                
        if self.response.parsed_hdrs.has_key('content-md5'):
            c_md5_calc = base64.encodestring(self.response.body_md5)[:-1]
            if self.response.parsed_hdrs['content-md5'] == c_md5_calc:
                self.setMessage('header-content-md5', rs.CMD5_CORRECT)
            else:
                self.setMessage('header-content-md5', rs.CMD5_INCORRECT, 
                                calc_md5=c_md5_calc)


    def checkConneg(self):
        if "gzip" in self.response.parsed_hdrs.get('content-encoding', []):
            self.setMessage('header-content-encoding', rs.CONNEG_GZIP)
            vary_headers = self.response.parsed_hdrs.get('vary', [])
            if (not "accept-encoding" in vary_headers) and (not "*" in vary_headers):
                self.setMessage('header-vary header-%s', rs.CONNEG_NO_VARY)
            def conneg_done(conneg_res):
                # FIXME: verify that the status/body/hdrs are the same; if it's different, alert
                conneg_vary_headers = conneg_res.parsed_hdrs.get('vary', [])
                if 'gzip' in conneg_res.parsed_hdrs.get('content-encoding', []):
                    self.setMessage('header-vary header-content-encoding', 
                                    rs.CONNEG_GZIP_WITHOUT_ASKING)
                if conneg_vary_headers != vary_headers:
                    self.setMessage('header-vary', rs.VARY_INCONSISTENT,
                        conneg_vary=", ".join(conneg_vary_headers),
                        no_conneg_vary=", ".join(vary_headers)
                    )
                if conneg_res.parsed_hdrs.get('etag', 1) == self.response.parsed_hdrs.get('etag', 2):
                    self.setMessage('header-etag', rs.ETAG_DOESNT_CHANGE)
            makeRequest(self.response.uri, 
                        done_cb=conneg_done, status_cb=self.status_cb, 
                        reason="conneg")


    def checkClock(self):
        if not self.response.parsed_hdrs.has_key('date'):
            self.setMessage('', rs.DATE_CLOCKLESS)
            if self.response.parsed_hdrs.has_key('expires') or \
              self.response.parsed_hdrs.has_key('last-modified'):
                self.setMessage('header-expires header-last-modified', rs.DATE_CLOCKLESS_BAD_HDR)
            return
        skew = self.response.parsed_hdrs['date'] - \
          self.response.header_timestamp + self.response.parsed_hdrs.get('age', 0)
        if abs(skew) > max_clock_skew:
            self.setMessage('header-date', rs.DATE_INCORRECT, 
                            clock_skew_string=relative_time(
                                self.response.parsed_hdrs.get('date', 0), 
                                self.response.header_timestamp, 2
                            )
            )
        else:
            self.setMessage('header-date', rs.DATE_CORRECT)


    def checkCaching(self):
        # TODO: check URI for query string, message about HTTP/1.0 if so
        # TODO: assure that there aren't any dup standard directives
        # TODO: check for spurious 'public' directive (e.g., sun.com)
        cc_dict = dict(self.response.parsed_hdrs.get('cache-control', []))

        # can it be stored? If not, get out of here.
        if self.method not in cacheable_methods:
            self.setMessage('method', rs.METHOD_UNCACHEABLE, method=self.method)
            return
        if cc_dict.has_key('no-store'):
            self.setMessage('header-cache-control', rs.NO_STORE)
            return 

        # is it private?
        if cc_dict.has_key('private'):
            self.setMessage('header-cache-control', rs.PRIVATE_CC)
        if 'authorization' in [k.lower() for k, v in self.req_headers] and \
          not cc_dict.has_key('public'):
            self.setMessage('header-cache-control', rs.PRIVATE_AUTH)

        # no-cache?
        if cc_dict.has_key('no-cache'):
            self.setMessage('header-cache-control', rs.NO_CACHE)
            return

        # calculate age
        if self.response.parsed_hdrs.has_key('date'):
            apparent_age = max(0, 
              int(self.response.header_timestamp - self.response.parsed_hdrs['date']))
        else:
            apparent_age = 0
        age = self.response.parsed_hdrs.get('age', 0)
        current_age = max(apparent_age, self.response.parsed_hdrs.get('age', 0))
        current_age_str = relative_time(current_age, 0, 0)
        if age >= 1:
            self.setMessage('header-age header-date', rs.CURRENT_AGE, 
                            current_age=current_age_str)
        
        # calculate freshness
        freshness_lifetime = 0
        has_explicit_freshness = False
        freshness_hdrs = ['header-date', 'header-expires']
        if cc_dict.has_key('s-maxage'): # TODO: differentiate message for s-maxage
            freshness_lifetime = cc_dict['s-maxage']
            freshness_hdrs.append('header-cache-control')
            has_explicit_freshness = True
        elif cc_dict.has_key('max-age'):
            freshness_lifetime = cc_dict['max-age']
            freshness_hdrs.append('header-cache-control')
            has_explicit_freshness = True
        elif self.response.parsed_hdrs.has_key('expires'):
            has_explicit_freshness = True
            if self.response.parsed_hdrs.has_key('date'):
                freshness_lifetime = self.response.parsed_hdrs['expires'] - \
                    self.response.parsed_hdrs['date']
            else:
                freshness_lifetime = self.response.parsed_hdrs['expires'] - \
                    self.response.header_timestamp # ?

        freshness_left = freshness_lifetime - current_age
        freshness_left_str = relative_time(abs(int(freshness_left)), 0, 0)
        freshness_lifetime_str = relative_time(int(freshness_lifetime), 0, 0)

        if freshness_left > 0:
            self.setMessage(" ".join(freshness_hdrs), rs.FRESHNESS_FRESH, 
                            freshness_lifetime=freshness_lifetime_str,
                            freshness_left=freshness_left_str,
                            current_age = current_age_str
                            )
        else:
            self.setMessage(" ".join(freshness_hdrs), rs.FRESHNESS_STALE, 
                            freshness_lifetime=freshness_lifetime_str,
                            freshness_left=freshness_left_str,
                            current_age = current_age_str
                            )

        # can heuristic freshness be used?
        if self.response.status in heuristic_cacheable_status and \
          not has_explicit_freshness:
            self.setMessage('last-modified', rs.HEURISTIC_FRESHNESS)

        # can stale responses be served?
        if cc_dict.has_key('must-revalidate'):
            self.setMessage('cache-control', rs.STALE_MUST_REVALIDATE) 
        elif cc_dict.has_key('proxy-revalidate') or cc_dict.has_key('s-maxage'):
            self.setMessage('cache-control', rs.STALE_PROXY_REVALIDATE) 
        else:
            self.setMessage('cache-control', rs.STALE_SERVABLE)

                
    def checkEtagValidation(self):
        if self.response.parsed_hdrs.has_key('etag'):
            def inm_done(inm_response):
                if inm_response.status == '304':
                    self.setMessage('header-etag', rs.INM_304)
                elif inm_response.status == self.response.status:
                    if inm_response.body_md5 == self.response.body_md5:
                        self.setMessage('header-etag', rs.INM_FULL)
                    else:
                        self.setMessage('header-etag', rs.INM_UNKNOWN)
                else:
                    self.setMessage('header-etag', rs.INM_STATUS, 
                                    inm_status=inm_response.status)
                # TODO: check entity headers
            weak, etag = self.response.parsed_hdrs['etag']
            if weak:
                weak_str = "W/"
                # TODO: message on weak etag
            else:
                weak_str = ""
            etag_str = '%s"%s"' % (weak_str, etag)
            makeRequest(self.response.uri, 
                req_headers=[
                    ('If-None-Match', etag_str),
                    ('Accept-Encoding', 'gzip')
                ], 
                done_cb=inm_done, status_cb=self.status_cb,
                reason="ETag validation")
                
    def checkLmValidation(self):
        if self.response.parsed_hdrs.has_key('last-modified'):
            def ims_done(ims_response):
                if ims_response.status == '304':
                    self.setMessage('header-last-modified', rs.IMS_304)
                elif ims_response.status == self.response.status:
                    if ims_response.body_md5 == self.response.body_md5:
                        self.setMessage('header-last-modified', rs.IMS_FULL)
                    else:
                        self.setMessage('header-last-modified', rs.IMS_UNKNOWN)
                else:
                    self.setMessage('header-last-modified', rs.IMS_STATUS, 
                                    ims_status=ims_response.status)
                # TODO: check entity headers
            date_str = time.strftime('%a, %d %b %Y %H:%M:%S GMT', 
                                     time.gmtime(self.response.parsed_hdrs['last-modified']))
            makeRequest(self.response.uri,  
                req_headers=[
                    ('If-Modified-Since', date_str),
                    ('Accept-Encoding', 'gzip')
                ], 
                done_cb=ims_done, status_cb=self.status_cb,
                reason="Last-Modified validation")
                
    def setMessage(self, subject, msg, **vars):
        self.messages.append((subject, msg, vars))


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
        )
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

def CheckFieldSyntax(exp):
    """
    Decorator to check each header field-value to conform to the regex exp.
    """
    def wrap(meth):
        def new(self, name, values):
            for value in values:
                if not re.match(r"^\s*(?:%s)?\s*$" % exp, value):
                    self.setMessage(name, rs.BAD_SYNTAX)
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
    def __init__(self, response, setMessage=None):
        self.response = response
        self._setMessage = setMessage
        hdr_dict = {}
        header_block_size = len(response.phrase) + 13
        for name, value in response.headers:
            hdr_size = len(name) + len(value)
            if hdr_size > max_hdr_size:
                self.setMessage(name.lower(), rs.HEADER_TOO_LARGE,
                                header_name=name, header_size=hdr_size)
            header_block_size += hdr_size
            if not re.match("^\s*%s\s*$" % TOKEN, name):
                self.setMessage(name, rs.FIELD_NAME_BAD_SYNTAX)
            name = name.lower()
            if hdr_dict.has_key(name):
                hdr_dict[name].append(value)
            else:
                hdr_dict[name] = [value]
        if header_block_size > max_ttl_hdr:
            self.setMessage('header', rs.HEADER_BLOCK_TOO_LARGE, 
                            header_block_size=header_block_size)
        for fn, values in hdr_dict.items():
            name_token = fn.replace('-', '_')
            # anything starting with an underscore or with any caps won't match
            if name_token[0] != '_' and hasattr(self, name_token):
                parsed_value = getattr(self, name_token)(fn, values)
                if parsed_value != None:
                    self.response.parsed_hdrs[fn] = parsed_value

    def setMessage(self, name, msg, **vars):
        if self._setMessage:
            ident = 'header-%s' % name.lower()
            self._setMessage(ident, msg, field_name=name, **vars)

    @GenericHeaderSyntax
    def accept_ranges(self, name, values):
        # TODO: syntax check, parse
        return values

    @GenericHeaderSyntax
    @SingleFieldValue
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
    def allow(self, name, values):
        return values

    @GenericHeaderSyntax
    @CheckFieldSyntax(PARAMETER)
    def cache_control(self, name, values):
        directives = []
        for directive in values:
            try:
                attr, value = directive.split("=", 1)
                value = unquotestring(value)
            except ValueError:
                attr = directive
                value = None
            attr = attr.lower()
            if attr in ['max-age', 's-maxage']:
                try:
                    value = int(value)
                except ValueError:
                    self.setMessage(name, rs.BAD_CC_SYNTAX, bad_cc_attr=attr)
                    continue
            directives.append((attr, value))
        return directives

    @SingleFieldValue
    @CheckFieldSyntax(URI)
    def content_base(self, name, values):
        return values[-1]
        
    def content_disposition(self, name, values):
        pass
        
    @GenericHeaderSyntax
    def content_encoding(self, name, values):
        values = [v.lower() for v in values]
        return values
        
    @GenericHeaderSyntax
    @SingleFieldValue
    @CheckFieldSyntax(DIGITS)
    def content_length(self, name, values):
        return int(values[-1])

    @SingleFieldValue
    def content_md5(self, name, values):
        return values[-1]

    def content_range(self, name, values):
        pass

    @GenericHeaderSyntax
    @SingleFieldValue
    def content_type(self, name, values):
        try:
            media_type, params = values[-1].split(";", 1)
        except ValueError:
            media_type, params = values[-1], ''
        media_type = media_type.lower()
        param_dict = {}
        for param in splitstring(params, PARAMETER, "\s*;\s*"):
            try:
                a, v = param.split("=", 1)
                param_dict[a.lower()] = unquotestring(v)
            except ValueError:
                param_dict[param.lower()] = None
        return media_type, param_dict

    @SingleFieldValue
    def date(self, name, values):
        try:
            date = parse_date(values)
        except ValueError, why:
            self.setMessage(name, rs.BAD_DATE_SYNTAX)
            return None
        return date

    @SingleFieldValue
    def expires(self, name, values):
        try:
            date = parse_date(values)
        except ValueError, why:
            self.setMessage(name, rs.BAD_DATE_SYNTAX)
            return None
        return date

    @GenericHeaderSyntax
    @SingleFieldValue
    @CheckFieldSyntax(r'(?:(?:W/)?%s|\*)' % QUOTED_STRING)
    def etag(self, name, values):
        instr = values[-1]
        if instr[:2] == 'W/':
            return (True, unquotestring(instr[2:]))
        else:
            return (False, unquotestring(instr))

    @GenericHeaderSyntax
    def keep_alive(self, name, values):
        values = [v.lower() for v in values]
        return values
        
    @SingleFieldValue
    def last_modified(self, name, values):
        try:
            date = parse_date(values)
        except ValueError, why:
            self.setMessage(name, rs.BAD_DATE_SYNTAX)
            return None
        if date > self.response.header_timestamp:
            self.setMessage(name, rs.LM_FUTURE)
            return
        else:
            self.setMessage(name, rs.LM_PRESENT, 
              last_modified_string=relative_time(date, self.response.header_timestamp))
        return date

    @GenericHeaderSyntax
    def link(self, name, values):
        pass

    @CheckFieldSyntax(URI)
    @SingleFieldValue
    def location(self, name, values):
        return values[-1]

    def mime_version(self, name, values):
        self.setMessage(name, rs.MIME_VERSION)
        return values

    @GenericHeaderSyntax
    def nnCoection(self, name, values):
        pass
        
    @GenericHeaderSyntax
    def p3p(self, name, values):
        pass
                
    @GenericHeaderSyntax
    def pragma(self, name, values):
        values = [v.lower() for v in values]
        if "no-cache" in values:
            self.setMessage(name, rs.PRAGMA_NO_CACHE)
        others = [True for v in values if v != "no-cache"]
        if others:
            self.setMessage(name, rs.PRAGMA_OTHER)
        return values
                
    @GenericHeaderSyntax
    @SingleFieldValue
    def retry_after(self, name, values):
        pass

    def server(self, name, values):
        pass
        
    @CheckFieldSyntax(URI)
    @SingleFieldValue
    def soapaction(self, name, values):
        return values[-1]
        
    def set_cookie(self, name, values):
        pass

    @GenericHeaderSyntax
    def transfer_encoding(self, name, values):
        values = [v.lower() for v in values]
        return values

    @GenericHeaderSyntax
    def vary(self, name, values):
        values = [v.lower() for v in values]
        values.sort()
        if "*" in values:
            self.setMessage(name, rs.VARY_ASTERISK)
        elif 'user-agent' in values:
            self.setMessage(name, rs.VARY_USER_AGENT)
        return values
        
    @GenericHeaderSyntax
    @CheckFieldSyntax(r'(?:%s/)?%s\s+[^,\s]+(?:\s+%s)?' % (TOKEN, TOKEN, COMMENT))
    def via(self, name, values):
        self.setMessage(name, rs.VIA_PRESENT, via_string=values)
        
    @GenericHeaderSyntax
    def warning(self, name, values):
        pass

    @GenericHeaderSyntax
    @CheckFieldSyntax(URI)
    @SingleFieldValue
    def x_xrds_location(self, name, values):
        pass

    @GenericHeaderSyntax
    def x_pad(self, name, values):
        pass
    
class ResponseStatusChecker:
    """
    Given a response and a setMessage function, check out the status
    code and perform appropriate tests on it.
    """
    def __init__(self, response, setMessage):
        self.response = response
        self._setMessage = setMessage
        try:
            getattr(self, "status%s" % response.status)()
        except AttributeError:
            self.setMessage('status', rs.NONSTANDARD_STATUS)

    def setMessage(self, name, msg, **vars):
        if self._setMessage:
            ident = 'status %s' % name
            self._setMessage(ident, msg, status=self.response.status, **vars)

    def status100(self):        # Continue
        pass # TODO: check to make sure expectation sent
    def status101(self):        # Switching Protocols
        pass # TODO: make sure upgrade sent
    def status102(self):        # Processing
        pass
    def status200(self):        # OK
        pass
    def status201(self):        # Created
        pass # TODO: make sure appropriate method used, Location present
    def status202(self):        # Accepted
        pass
    def status203(self):        # Non-Authoritative Information
        pass
    def status204(self):        # No Content
        pass
    def status205(self):        # Reset Content
        pass
    def status206(self):        # Partial Content
        pass # TODO: check partial content
    def status207(self):        # Multi-Status
        pass
    def status226(self):        # IM Used
        pass
    def status300(self):        # Multiple Choices
        pass
    def status301(self):        # Moved Permanently
        if not self.response.parsed_hdrs.has_key('location'):
            self.setMessage('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status302(self):        # Found
        if not self.response.parsed_hdrs.has_key('location'):
            self.setMessage('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status303(self):        # See Other
        if not self.response.parsed_hdrs.has_key('location'):
            self.setMessage('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status304(self):        # Not Modified
        pass # TODO: check to make sure required headers are present, stable
    def status305(self):        # Use Proxy
        self.setMessage('', rs.DEPRECATED_STATUS)
    def status306(self):        # Reserved
        self.setMessage('', rs.RESERVED_STATUS)
    def status307(self):        # Temporary Redirect
        if not self.response.parsed_hdrs.has_key('location'):
            self.setMessage('header-location', rs.REDIRECT_WITHOUT_LOCATION)
    def status400(self):        # Bad Request
        pass # TODO: ?
    def status401(self):        # Unauthorized
        pass # TODO: prompt for credentials
    def status402(self):        # Payment Required
        pass
    def status403(self):        # Forbidden
        pass # TODO: explain
    def status404(self):        # Not Found
        pass # TODO: explain
    def status405(self):        # Method Not Allowed
        pass # TODO: show allowed methods?
    def status406(self):        # Not Acceptable
        pass # TODO: warn that the client may still want something
    def status407(self):        # Proxy Authentication Required
        pass
    def status408(self):        # Request Timeout
        pass
    def status409(self):        # Conflict
        pass # TODO: explain
    def status410(self):        # Gone
        pass # TODO: explain
    def status411(self):        # Length Required
        pass
    def status412(self):        # Precondition Failed
        pass # TODO: test to see if it's true, alert if not
    def status413(self):        # Request Entity Too Large
        pass # TODO: explain 
    def status414(self):        # Request-URI Too Long
        self.setMessage('uri', rs.SERVER_URI_TOO_LONG, 
                        uri_len=len(self.response.uri))
    def status415(self):        # Unsupported Media Type
        pass # TODO: explain
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
        pass # TODO: explain
    def status501(self):        # Not Implemented
        pass # TODO: explain
    def status502(self):        # Bad Gateway
        pass # TODO: explain
    def status503(self):        # Service Unavailable
        pass # TODO: explain
    def status504(self):        # Gateway Timeout
        pass # TODO: explain
    def status505(self):        # HTTP Version Not Supported
        pass # TODO: warn
    def status506(self):        # Variant Also Negotiates
        pass
    def status507(self):        # Insufficient Storage
        pass
    def status510(self):        # Not Extended
        pass

    
################################################################################


class Response: 
    "Holds a HTTP response message."
    def __init__(self, uri=None):
        self.uri = uri
        self.version = ""
        self.status = None
        self.phrase = ""
        self.headers = []
        self.parsed_hdrs = {}
        self.body = ""
        self.body_len = 0
        self.body_md5 = None
        self.body_sample = ""
        self.complete = False
        self.header_timestamp = None
        self._in_gzip_body = False
        self._gzip_header_buffer = ""

outstanding_requests = 0 # how many requests we have left
def makeRequest(uri, method="GET", req_headers=None, body=None, 
                done_cb=None, status_cb=None, set_message=None,
                body_processors=[], reason=None):
    """
    Make an asynchronous HTTP request to uri, calling status_cb as it's updated and
    done_cb when it's done. Reason is used to explain what the request is in the
    status callback.
    """
    global outstanding_requests
    if req_headers == None:
        req_headers = []
    response = Response(uri)
    md5_processor = hashlib.md5()
    decompress = zlib.decompressobj(-zlib.MAX_WBITS)
    outstanding_requests += 1
    req_headers.append(("User-Agent", "RED/%s (http://redbot.org/about)" % __version__))
    def response_start(version, status, phrase, res_headers):
        response.header_timestamp = time.time()
        response.version = version
        response.status = status
        response.phrase = phrase
        response.headers = res_headers
        ResponseHeaderParser(response, set_message)

    def response_body(chunk):
        md5_processor.update(chunk)
        response.body_len += len(chunk)
        if not response.complete:
            response.body += chunk # TODO: get rid of this
        # TODO: deflate support
        if 'gzip' in response.parsed_hdrs.get('content-encoding', []):
            if not response._in_gzip_body:
                response._gzip_header_buffer += chunk
                try:
                    chunk = read_gzip_header(response._gzip_header_buffer)
                    response._in_gzip_body = True
                except IndexError:
                    return # not a full header yet
                except IOError:
                    return # TODO: flag bad gzip
            chunk = decompress.decompress(chunk) # TODO: flag bad zlib
        for processor in body_processors:
            processor(chunk)
                
    def response_done(complete):
        global outstanding_requests
        response.complete = complete
        response.body_md5 = md5_processor.digest()
        # TODO: move status parsing, other checks here too
        if status_cb and reason:
            status_cb("fetched %s (%s)" % (uri, reason))
        if done_cb:
            done_cb(response)
        outstanding_requests -= 1
        if outstanding_requests == 0:
            http_client.stop()

    c = http_client.HttpClient(response_start, response_body, response_done, timeout=connect_timeout)
    if status_cb and reason:
        status_cb("fetching %s (%s)" % (uri, reason))
    req_body_write, req_body_done = c.start_request(method, uri, req_headers=req_headers)
    if body != None:
        req_body_write(body)
        req_body_done()


# adapted from gzip.py
def read_gzip_header(content):
    FTEXT, FHCRC, FEXTRA, FNAME, FCOMMENT = 1, 2, 4, 8, 16
    if len(content) < 10: 
        raise IndexError, "Header not complete yet"
    magic = content[:2]
    if magic != '\037\213':
        raise IOError, 'Not a gzipped file'
    method = ord( content[2:3] )
    if method != 8:
        raise IOError, 'Unknown compression method'
    flag = ord( content[3:4] )
    content_l = list(content[10:])
    if flag & FEXTRA:
        # Read & discard the extra field, if present
        xlen = ord(content_l.pop())
        xlen = xlen + 256*ord(content_l.pop())
        content_l = content_l[xlen:]
    if flag & FNAME:
        # Read and discard a null-terminated string containing the filename
        while True:
            s = content_l.pop()
            if not s or s == '\000':
                break
    if flag & FCOMMENT:
        # Read and discard a null-terminated string containing a comment
        while True:
            s = content_l.pop()
            if not s or s == '\000':
                break
    if flag & FHCRC:
        content_l = content_l[2:]   # Read & discard the 16-bit header CRC
    return "".join(content_l)



def parse_date(values):
    """Parse a HTTP date. Raises ValueError if it's bad."""
    value = values[-1]
    if not re.match(r"%s$" % DATE, value):
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


def relative_time(utime, now=None, show_sign=1):
    ''' 
    Given two times, return a string that explains how far apart they are.
    show_sign can be:
      0 - don't show
      1 - ago / from now  [DEFAULT]
      2 - early / late
     '''

    signs = {
        0:	('none', '', ''),
        1:	('now', 'ago', 'from now'),
        2:	('none', 'behind', 'ahead'),
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
    arr = arr[:2]		# resolution
    if show_sign: 
        arr.append(sign)
    return " ".join(arr)

def unquotestring(instr):
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
        

def splitstring(instr, item, split):
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
