#!/usr/bin/env python

"""
The Resource Expert Droid Fetcher.

RedFetcher fetches a single URI and analyses that response for common
problems and other interesting characteristics. It only makes one request,
based upon the provided headers.

See red.py for the main RED engine and webui.py for the Web front-end.
"""

__version__ = "1"
__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
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

import base64
import calendar
import hashlib
import re
import socket
import time
import zlib
from cgi import escape as e
from email.utils import parsedate as lib_parsedate

import nbhttp
import red_speak as rs 

# base URL for RFC2616 references
rfc2616 = "http://www.apps.ietf.org/rfc/rfc2616.html#%s"

### configuration
max_hdr_size = 4 * 1024
max_ttl_hdr = 20 * 1024

# generic syntax regexen
TOKEN = r'(?:[^\(\)<>@,;:\\"/\[\]\?={} \t]+?)'
STRING = r'(?:[^,]+)'
QUOTED_STRING = r'(?:"(?:\\"|[^"])*")'
PARAMETER = r'(?:%(TOKEN)s(?:=(?:%(TOKEN)s|%(QUOTED_STRING)s))?)' % locals()
TOK_PARAM = r'(?:%(TOKEN)s(?:\s*;\s*%(PARAMETER)s)*)' % locals()
PRODUCT = r'(?:%(TOKEN)s(?:/%(TOKEN)s)?)' % locals()
COMMENT = r'(?:\((?:[^\(\)]|\\\(|\\\))*\))' # does not handle nesting
URI = r'(?:(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?)'  # RFC3986
COMMA = r'(?:\s*(?:,\s*)+)'
DIGITS = r'(?:\d+)'
DATE = r'(?:\w{3}, \d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2} GMT|\w{6,9}, \d{2}\-\w{3}\-\d{2} \d{2}:\d{2}:\d{2} GMT|\w{3} \w{3} [\d ]\d \d{2}:\d{2}:\d{2} \d{4})'


outstanding_requests = 0 # how many requests we have left

class RedFetcher: 
    """
    Fetches the given URI (with the provided method, headers and body) and calls:
      - status_cb as it progresses, and
      - every function in the body_procs list with each chunk of the body, and
      - done when it's done.
    If provided, type indicates the type of the request, and is used to
    help set messages and status_cb appropriately. 
    
    Messages is a list of messages, each of which being a tuple that 
    follows the following form:
      (
       subject,     # The subject(s) of the msg, as a space-separated string.
                    # e.g., "header-cache-control header-expires"
       message,     # The message structure; see red.speak.py
       subrequest,  # Optionally, a RedFetcher object representing a
                    # request with additional details about another request
                    # made in order to generate the message
       **variables  # Optionally, key=value pairs intended for interpolation
                    # into the message; e.g., time_left="5d3h"
      )
    """

    def __init__(self, uri, method="GET", req_hdrs=None, req_body=None,
                 status_cb=None, body_procs=None, type=None):
        self.uri = uri
        self.method = method
        self.req_hdrs = req_hdrs or []
        self.req_body = req_body
        self.status_cb = status_cb
        self.body_procs = body_procs or []
        self.type = type
        self.res_version = ""
        self.res_status = None
        self.res_phrase = ""
        self.res_hdrs = []
        self.parsed_hdrs = {}
        self.res_body = "" # note: only partial responses get this populated; bytes, not unicode
        self.res_body_len = 0
        self.res_body_md5 = None
        self.res_body_sample = [] # array of (offset, chunk), max size 4. Bytes, not unicode.
        self.res_complete = False
        self.timestamp = None # when the request was started
        self.res_error = None # any parse errors encountered; see nbhttp.error
        self.messages = []
        self._md5_processor = hashlib.md5()
        self._decompress = zlib.decompressobj(-zlib.MAX_WBITS).decompress
        self._in_gzip_body = False
        self._gzip_header_buffer = ""
        self._gzip_ok = True # turn False if we have a problem
        try:
            self._makeRequest()
        except socket.gaierror:
            raise DroidError, "Hostname not found."
        
    def setMessage(self, subject, msg, subreq=None, **vrs):
        "Set a message."
        vrs['response'] = rs.response.get(self.type, rs.response['this'])['en']
        self.messages.append((subject, msg, subreq, vrs))

    def done(self):
        "Callback for when the response is complete and analysed."
        raise NotImplementedError

    def _makeRequest(self):
        """
        Make an asynchronous HTTP request to uri, calling status_cb as it's updated and
        done_cb when it's done. Reason is used to explain what the request is in the
        status callback.
        """
        global outstanding_requests
        outstanding_requests += 1
        c = nbhttp.Client(self._response_start)
        if self.status_cb and self.type:
            self.status_cb("fetching %s (%s)" % (self.uri, self.type))
        req_body, req_done = c.req_start(self.method, self.uri, self.req_hdrs, nbhttp.dummy)
        if outstanding_requests == 1:
            nbhttp.run()
        if self.req_body != None:
            req_body(self.req_body)
        req_done(None)

    def _response_start(self, version, status, phrase, res_headers, res_pause):
        "Process the response start-line and headers."
        self.timestamp = time.time()
        self.res_version = version
        self.res_status = status
        self.res_phrase = phrase
        self.res_hdrs = res_headers
        ResponseHeaderParser(self)
        ResponseStatusChecker(self)
        return self._response_body, self._response_done

    def _response_body(self, chunk):
        "Process a chunk of the response body."
        self._md5_processor.update(chunk)
        self.res_body_sample.append((self.res_body_len, chunk))
        if len(self.res_body_sample) > 4:
            self.res_body_sample.pop(0)
        self.res_body_len += len(chunk)
        if self.res_status == "206":
            # Store only partial responses completely, for error reporting
            self.res_body += chunk
            # Don't actually try to make sense of a partial body...
            return
        content_codings = self.parsed_hdrs.get('content-encoding', [])
        content_codings.reverse()
        for coding in content_codings:
            # TODO: deflate support
            if coding == 'gzip' and self._gzip_ok:
                if not self._in_gzip_body:
                    self._gzip_header_buffer += chunk
                    try:
                        chunk = self._read_gzip_header(self._gzip_header_buffer)
                        self._in_gzip_body = True
                    except IndexError:
                        return # not a full header yet
                    except IOError, gzip_error:
                        self.setMessage('header-content-encoding', rs.BAD_GZIP,
                                        gzip_error=e(str(gzip_error))
                                        )
                        self._gzip_ok = False
                        return
                try:
                    chunk = self._decompress(chunk)
                except zlib.error, zlib_error:
                    self.setMessage('header-content-encoding', rs.BAD_ZLIB,
                                    zlib_error=e(str(zlib_error)),
                                    ok_zlib_len=self.res_body_sample[-1][0],
                                    chunk_sample=e(chunk[:20].encode('string_escape'))
                                    )
                    self._gzip_ok = False
                    return
            else:
                # we can't really process the rest, so punt on body processing.
                return
        if self._gzip_ok:
            for processor in self.body_procs:
                processor(self, chunk)

    def _response_done(self, err):
        "Finish anaylsing the response, handling any parse errors."
        global outstanding_requests
        self.res_complete = True
        self.res_error = err
        if self.status_cb and self.type:
            self.status_cb("fetched %s (%s)" % (self.uri, self.type))
        self.res_body_md5 = self._md5_processor.digest()
        if err == None:
            pass
        elif err['desc'] == nbhttp.error.ERR_BODY_FORBIDDEN['desc']:
            self.setMessage('header-none', rs.BODY_NOT_ALLOWED)
        elif err['desc'] == nbhttp.error.ERR_EXTRA_DATA['desc']:
            self.res_body_len += len(err.get('detail', ''))
        elif err['desc'] == nbhttp.error.ERR_CHUNK['desc']:
            self.setMessage('header-transfer-encoding', rs.BAD_CHUNK,
                                chunk_sample=e(err.get('detail', '')[:20]))
        elif err['desc'] == nbhttp.error.ERR_CONNECT['desc']:
            raise DroidError, "Could not connect to the server (%s)." % \
                err.get('detail', "unknown problem")
        elif err['desc'] == nbhttp.error.ERR_LEN_REQ['desc']:
            pass # FIXME: length required
        elif err['desc'] == nbhttp.error.ERR_URL['desc']:
            raise DroidError, err.get('detail', "RED can't fetch that URL.")
        else:
            raise AssertionError, "Unknown response error: %s" % err

        # check payload basics
        if self.parsed_hdrs.has_key('content-length'):
            if self.res_body_len == self.parsed_hdrs['content-length']:
                self.setMessage('header-content-length', rs.CL_CORRECT)
            else:
                self.setMessage('header-content-length', rs.CL_INCORRECT, 
                                         body_length=self.res_body_len)                    
        if self.parsed_hdrs.has_key('content-md5'):
            c_md5_calc = base64.encodestring(self.res_body_md5)[:-1]
            if self.parsed_hdrs['content-md5'] == c_md5_calc:
                self.setMessage('header-content-md5', rs.CMD5_CORRECT)
            else:
                self.setMessage('header-content-md5', rs.CMD5_INCORRECT, 
                                         calc_md5=c_md5_calc)
        # analyse, check to see if we're done
        self.done()
        outstanding_requests -= 1
        if outstanding_requests == 0:
            nbhttp.stop()

    @staticmethod
    def _read_gzip_header(content):
        "Parse a GZIP header"
        # adapted from gzip.py
        FTEXT, FHCRC, FEXTRA, FNAME, FCOMMENT = 1, 2, 4, 8, 16
        if len(content) < 10: 
            raise IndexError, "Header not complete yet"
        magic = content[:2]
        if magic != '\037\213':
            raise IOError, u'Not a gzip header (magic is hex %s, should be 1f8b)' % magic.encode('hex-codec')
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
                if not content_l or s == '\000':
                    break
        if flag & FCOMMENT:
            # Read and discard a null-terminated string containing a comment
            while True:
                s = content_l.pop()
                if not content_l or s == '\000':
                    break
        if flag & FHCRC:
            content_l = content_l[2:]   # Read & discard the 16-bit header CRC
        return "".join(content_l)



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
                if not re.match(r"^\s*(?:%s)\s*$" % exp, value):
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
        for name, value in red.res_hdrs:
            hdr_size = len(name) + len(value)
            if hdr_size > max_hdr_size:
                self.setMessage(name.lower(), rs.HEADER_TOO_LARGE,
                                header_name=name, header_size=hdr_size)
            header_block_size += hdr_size
            if not re.match("^\s*%s\s*$" % TOKEN, name):
                self.setMessage(name, rs.FIELD_NAME_BAD_SYNTAX)
            norm_name = name.lower()
            value = value.strip()
            if hdr_dict.has_key(norm_name):
                hdr_dict[norm_name][1].append(value)
            else:
                hdr_dict[norm_name] = (name, [value])
        if header_block_size > max_ttl_hdr:
            self.setMessage('header', rs.HEADER_BLOCK_TOO_LARGE, 
                            header_block_size=header_block_size)
        for fn, (nn, values) in hdr_dict.items():
            name_token = fn.replace('-', '_')
            # anything starting with an underscore or with any caps won't match
            if name_token[0] != '_' and hasattr(self, name_token):
                parsed_value = getattr(self, name_token)(nn, values)
                if parsed_value != None:
                    self.red.parsed_hdrs[fn] = parsed_value

    def setMessage(self, name, msg, **vars):
        ident = 'header-%s' % name.lower()
        self.red.setMessage(ident, msg, field_name=name, **vars)

    @staticmethod
    def _parse_date(values):
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

    @staticmethod
    def _unquotestring(instr):
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
    def _splitstring(instr, item, split):
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
                value = self._unquotestring(value)
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
            directives.add((attr, value))
        return directives

    @SingleFieldValue
    def content_base(self, name, values):
        # TODO: alert that it's deprecated
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
                self.setMessage('header-content-encoding', rs.ENCODING_UNWANTED,
                                encoding=e(value))
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
        pass

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
        for param in self._splitstring(params, PARAMETER, "\s*;\s*"):
            try:
                a, v = param.split("=", 1)
                param_dict[a.lower()] = self._unquotestring(v)
            except ValueError:
                param_dict[param.lower()] = None
        return media_type, param_dict

    @SingleFieldValue
    def date(self, name, values):
        try:
            date = self._parse_date(values)
        except ValueError:
            self.setMessage(name, rs.BAD_DATE_SYNTAX)
            return None
        return date

    @SingleFieldValue
    def expires(self, name, values):
        try:
            date = self._parse_date(values)
        except ValueError:
            self.setMessage(name, rs.BAD_DATE_SYNTAX)
            return None
        return date

    @GenericHeaderSyntax
    @SingleFieldValue
    @CheckFieldSyntax(r'(?:(?:W/)?%s|\*)' % QUOTED_STRING, rfc2616 % "sec-14.19")
    def etag(self, name, values):
        instr = values[-1]
        if instr[:2] == 'W/':
            return (True, self._unquotestring(instr[2:]))
        else:
            return (False, self._unquotestring(instr))

    @GenericHeaderSyntax
    def keep_alive(self, name, values):
        # TODO: check values?
        values = set([v.lower() for v in values])
        return values
        
    @SingleFieldValue
    def last_modified(self, name, values):
        try:
            date = self._parse_date(values)
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

    @CheckFieldSyntax(URI, rfc2616 % "sec-14.30")
    @SingleFieldValue
    def location(self, name, values):
        return values[-1]

    def mime_version(self, name, values):
        self.setMessage(name, rs.MIME_VERSION)
        return values

    @GenericHeaderSyntax
    def nnCoection(self, name, values):
        # TODO: flag this, others?
        pass
        
    @GenericHeaderSyntax
    def p3p(self, name, values):
        # TODO: check synta, values
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
    @CheckFieldSyntax(TOK_PARAM, rfc2616 % "sec-14.41")
    def transfer_encoding(self, name, values):
        # TODO: check values?
        values = [v.lower() for v in values]
        return values

    @GenericHeaderSyntax
    @CheckFieldSyntax(TOKEN, rfc2616 % "sec-14.44")
    def vary(self, name, values):
        values = set([v.lower() for v in values])
        if len(values) > 3:
            self.setMessage(name, rs.VARY_COMPLEX, vary_count=len(values))
        elif "*" in values:
            self.setMessage(name, rs.VARY_ASTERISK)
        else:
            if 'user-agent' in values:
                self.setMessage(name, rs.VARY_USER_AGENT)
            if 'host' in values:
                self.setMessage(name, rs.VARY_HOST)
        return values
        
    @GenericHeaderSyntax
    @CheckFieldSyntax(r'(?:%s/)?%s\s+[^,\s]+(?:\s+%s)?' % (TOKEN, TOKEN, COMMENT),
                      rfc2616 % "sec-14.45")
    def via(self, name, values):
        self.setMessage(name, rs.VIA_PRESENT, via_string=values)
        
    @GenericHeaderSyntax
    def warning(self, name, values):
        # TODO: check syntax, values?
        pass

    @GenericHeaderSyntax
    @SingleFieldValue
    def x_xrds_location(self, name, values):
        pass

    @GenericHeaderSyntax
    def x_pad(self, name, values):
        # TODO: message
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
            self.setMessage('status', rs.NONSTANDARD_STATUS)

    def setMessage(self, name, msg, **vars):
        ident = 'status %s' % name
        self.red.setMessage(ident, msg, 
                             status=self.red.status,
                             enc_status=e(self.red.status), 
                             **vars
                             )

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
        self.setMessage('', rs.DEPRECATED_STATUS)
    def status306(self):        # Reserved
        self.setMessage('', rs.RESERVED_STATUS)
    def status307(self):        # Temporary Redirect
        if not self.red.parsed_hdrs.has_key('location'):
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
                        uri_len=len(self.red.uri))
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


class DroidError(Exception):
    "An exception raised by RED."
    pass


def relative_time(utime, now=None, show_sign=1):
    ''' 
    Given two times, return a string that explains how far apart they are.
    show_sign can be:
      0 - don't show
      1 - ago / from now  [DEFAULT]
      2 - early / late
     '''

    signs = {
        0:    ('none', '', ''),
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
    