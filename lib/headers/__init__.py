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

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2011 Mark Nottingham

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
from email.utils import parsedate as lib_parsedate
import locale
import re
import sys
import time
import urllib

import redbot.http_syntax as syntax
import redbot.speak as rs

# base URLs for references
rfc2616 = "http://www.apps.ietf.org/rfc/rfc2616.html#%s"
rfc5988 = "http://www.apps.ietf.org/rfc/rfc5988.html#section-5"
rfc6266 = "http://www.apps.ietf.org/rfc/rfc6266.html#section-4"

### configuration
max_hdr_size = 4 * 1024
max_ttl_hdr = 20 * 1024

#FIXME: need to be function decorators now
def GenericHeaderSyntax(func):
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
    def new(name, values, red):
        values = sum(
            [[f.strip() for f in re.findall(r'((?:[^",]|%s)+)(?=%s|\s*$)' %
             (syntax.QUOTED_STRING, syntax.COMMA), v)] for v in values], []
        ) or ['']
        return func(name, values, red)
    return new


def SingleFieldValue(func):
    """
    Decorator to make sure that there's only one value.
    """
    def new(name, values, red):
        if len(values) > 1:
            red.set_message(name, rs.SINGLE_HEADER_REPEAT)
        return func(name, values, red)
    return new


def CheckFieldSyntax(exp, ref):
    """
    Decorator to check each header field-value to conform to the regex exp,
    and if not to point users to url ref.
    """
    def wrap(func):
        def new(name, values, red):
            for value in values:
                if not re.match(r"^\s*(?:%s)\s*$" % exp, value, re.VERBOSE):
                    red.set_message(name, rs.BAD_SYNTAX, ref_uri=ref)
                    def bad_syntax(name, values, red):
                        return None
                    return bad_syntax(name, values, red)
            return func(name, values, red)
        return new
    return wrap

def process_headers(red):
    """
    Parse and check the response for obvious syntactic errors,
    as well as semantic errors that are self-contained (i.e.,
    it can be determined without examining other headers, etc.).
    
    Populates parsed_hdrs, and replaces res_hdrs with unicode-cleaned one
    """

    # TODO: clean up this hack
    old_set_message = red.set_message
    def set_message(name, msg, **kw):
        ident = 'header-%s' % name.lower()
        old_set_message(ident, msg, field_name=name, **kw)
    red.set_message = set_message

    hdr_dict = {}
    header_block_size = len(red.res_phrase) + 13
    clean_res_hdrs = []
    parsed_hdrs = {}
    for name, value in red.res_hdrs:
        hdr_size = len(name) + len(value)
        if hdr_size > max_hdr_size:
            set_message(name.lower(), rs.HEADER_TOO_LARGE,
                       header_name=name, header_size=f_num(hdr_size))
        header_block_size += hdr_size
        try:
            name = name.decode('ascii', 'strict')
        except UnicodeError:
            name = name.decode('ascii', 'ignore')
            set_message('%s' % name.lower(), rs.HEADER_NAME_ENCODING,
                       header_name=name)
        try:
            value = value.decode('ascii', 'strict')
        except UnicodeError:
            value = value.decode('iso-8859-1', 'replace')
            set_message('%s' % name.lower(), rs.HEADER_VALUE_ENCODING,
                       header_name=name)
        clean_res_hdrs.append((name, value))
        if not re.match("^\s*%s\s*$" % syntax.TOKEN, name):
                        set_message(name, rs.FIELD_NAME_BAD_SYNTAX)
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
        set_message('header', rs.HEADER_BLOCK_TOO_LARGE,
                   header_block_size=f_num(header_block_size))
    # Build a dictionary of header values
    for nn, (fn, values) in hdr_dict.items():
        name_token = nn.replace('-', '_')
        # anything starting with an underscore or with any caps won't match
        try:
            __import__("redbot.headers.%s" % name_token)
            hdr_module = sys.modules["redbot.headers.%s" % name_token]
        except ImportError: 
            continue # we don't recognise the header.
        try:
            hdr_parse = getattr(hdr_module, name_token)
        except AttributeError:
            raise
        parsed_value = hdr_parse(fn, values, red)
        if parsed_value != None:
            parsed_hdrs[nn] = parsed_value
    red.parsed_hdrs = parsed_hdrs
    red.set_message = old_set_message


def parse_date(values):
    """Parse a HTTP date. Raises ValueError if it's bad."""
    value = values[-1]
    if not re.match(r"%s$" % syntax.DATE, value, re.VERBOSE):
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

def unquote_string(instr):
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
        ninstr = instr[1:-1]
        instr = re.sub(r'\\(.)', r'\1', ninstr)
    return instr

def split_string(instr, item, split):
    """
    Split instr as a list of items separated by splits.

    @param instr: string to be split
    @param item: regex for item to be split out
    @param split: regex for splitter
    @return: list of strings
    """
    if not instr:
        return []
    return [h.strip() for h in re.findall(
        r'%s(?=%s|\s*$)' % (item, split), instr
    )]

def parse_params(red, name, instr, nostar=None):
    """
    Parse parameters into a dictionary.
    
    @param red: the red instance to use
    @param name: the header field name
    @param instr: string to be parsed
    @param nostar: list of parameters that definitely don't get a star
    @return: dictionary of {name: value}
    """
    param_dict = {}
    instr = instr.encode('ascii')
    for param in split_string(instr, syntax.PARAMETER, r"\s*;\s*"):
        try:
            k, v = param.split("=", 1)
        except ValueError:
            param_dict[param.lower()] = None
            continue
        k_norm = k.lower()
        if param_dict.has_key(k_norm):
            red.set_message(name, rs.PARAM_REPEATS, param=e(k_norm))
        if v[0] == v[-1] == "'":
            red.set_message(name, 
                rs.PARAM_SINGLE_QUOTED,
                param=e(k_norm),
                param_val=e(v),
                param_val_unquoted=e(v[1:-1])
            )
        if k[-1] == '*':
            if nostar and k_norm[:-1] in nostar:
                red.set_message(name, rs.PARAM_STAR_BAD,
                                param=e(k_norm[:-1]))
            else:
                if v[0] == '"' and v[-1] == '"':
                    red.set_message(name, rs.PARAM_STAR_QUOTED,
                                    param=e(k_norm))
                    v = unquote_string(v)
                try:
                    enc, lang, esc_v = v.split("'", 3)
                except ValueError:
                    red.set_message(name, rs.PARAM_STAR_ERROR,
                                    param=e(k_norm))
                    continue
                enc = enc.lower()
                lang = lang.lower()
                if enc == '':
                    red.set_message(name, 
                        rs.PARAM_STAR_NOCHARSET, param=e(k_norm))
                    continue
                elif enc not in ['utf-8']:
                    red.set_message(name, 
                        rs.PARAM_STAR_CHARSET, 
                        param=e(k_norm), 
                        enc=e(enc)
                    )
                    continue
                # TODO: catch unquoting errors, range of chars, charset
                unq_v = urllib.unquote(esc_v)
                dec_v = unq_v.decode(enc) # ok, because we limit enc above
                param_dict[k_norm] = dec_v
        else:
            param_dict[k_norm] = unquote_string(v)
    return param_dict


def f_num(instr): # TODO: does this really belong here?
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

