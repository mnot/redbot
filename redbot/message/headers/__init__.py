#!/usr/bin/env python

"""
The Resource Expert Droid header checks.

process_headers() will process a list of (key, val) tuples.
"""

import re
import sys
import unittest

from redbot.message import http_syntax as syntax
from redbot.formatter import f_num
import redbot.speak as rs

from ._decorators import *
from ._utils import parse_date, unquote_string, split_string, parse_params


# base URLs for references
rfc2616 = "http://tools.ietf.org/html/rfc2616.html#%s"
rfc5988 = "http://tools.ietf.org/html/rfc5988.html#section-5"
rfc6265 = "http://tools.ietf.org/html/rfc6265.html#%s"
rfc6266 = "http://tools.ietf.org/html/rfc6266.html#section-4"

### configuration
MAX_HDR_SIZE = 4 * 1024
MAX_TTL_HDR = 8 * 1000

# map of header name aliases, lowercase-normalised
header_aliases = {
    'x-pad-for-netscrape-bug': 'x-pad',
    'xx-pad': 'x-pad',
    'x-browseralignment': 'x-pad',
    'nncoection': 'connectiox',
    'cneonction': 'connectiox',
    'yyyyyyyyyy': 'connectiox',
    'xxxxxxxxxx': 'connectiox',
    'x_cnection': 'connectiox',
    '_onnection': 'connectiox',
}


def process_headers(msg):
    """
    Parse and check the message for obvious syntactic errors,
    as well as semantic errors that are self-contained (i.e.,
    it can be determined without examining other headers, etc.).

    Using msg.headers, it populates:
      - .headers with a Unicode version of the input
      - .parsed_headers with a dictionary of parsed header values
    """

    hdr_dict = {}
    header_block_size = len(msg.version)
    if msg.is_request:
        header_block_size += len(msg.method) + len(msg.uri) + 2
    else:
        header_block_size += len(msg.status_phrase) + 5
    clean_hdrs = []      # unicode version of the header tuples
    parsed_hdrs = {}     # dictionary of parsed header values
    offset = 0
    for name, value in msg.headers:
        offset += 1
        subject = "offset-%s" % offset
        hdr_size = len(name) + len(value)
        if hdr_size > MAX_HDR_SIZE:
            msg.add_note(subject, rs.HEADER_TOO_LARGE,
               header_name=name, header_size=f_num(hdr_size))
        header_block_size += hdr_size
        
        # decode the header to make it unicode clean
        try:
            name = name.decode('ascii', 'strict')
        except UnicodeError:
            name = name.decode('ascii', 'ignore')
            msg.add_note(subject, rs.HEADER_NAME_ENCODING,
                header_name=name)
        try:
            value = value.decode('ascii', 'strict')
        except UnicodeError:
            value = value.decode('iso-8859-1', 'replace')
            msg.add_note(subject, rs.HEADER_VALUE_ENCODING,
                header_name=name)
        clean_hdrs.append((name, value))
        msg.set_context(field_name=name)
        
        # check field name syntax
        if not re.match("^\s*%s\s*$" % syntax.TOKEN, name, re.VERBOSE):
            msg.add_note(subject, rs.FIELD_NAME_BAD_SYNTAX)
            continue

        norm_name = name.lower()
        value = value.strip()
        
        hdr_parse = load_header_func(norm_name, 'parse')
        if hdr_parse:
            if hasattr(hdr_parse, 'pre_parse'):
                values = hdr_parse.pre_parse(value)
            else:
                values = [value]
            for value in values:
                if not hdr_dict.has_key(norm_name):
                    hdr_dict[norm_name] = (name, [])
                parsed_value = hdr_parse(subject, value, msg)
                if parsed_value != None:
                    hdr_dict[norm_name][1].append(parsed_value)
        
    # replace the original header tuple with ones that are clean unicode
    msg.headers = clean_hdrs

    # join parsed header values
    for norm_name, (orig_name, values) in hdr_dict.items():
        msg.set_context(field_name=orig_name)
        hdr_join = load_header_func(norm_name, 'join')
        if hdr_join:
            subject = "header-%s" % norm_name
            joined_value = hdr_join(subject, values, msg)
            if joined_value == None:
                continue
            parsed_hdrs[norm_name] = joined_value
    msg.parsed_headers = parsed_hdrs

    # check the total header block size
    if header_block_size > MAX_TTL_HDR:
        msg.add_note('header', rs.HEADER_BLOCK_TOO_LARGE,
            header_block_size=f_num(header_block_size))


def load_header_func(header_name, func=None):
    """
    Return a header parser for the given field name. If function isn't specified, 
    just return the module.
    """
    name_token = header_name.replace('-', '_').lower().encode('ascii', 'ignore')
    # anything starting with an underscore won't match
    if name_token[0] == '_':
        return
    # TODO: aliases
    try:
        module_name = "redbot.message.headers.%s" % name_token
        __import__(module_name)
        hdr_module = sys.modules[module_name]
    except (ImportError, KeyError, TypeError):
        return # we don't recognise the header.
    if func == None:
        return hdr_module
    try:
        return getattr(hdr_module, func)
    except AttributeError:
        return # we can't find the requested function.



# TODO: allow testing of request headers
class HeaderTest(unittest.TestCase):
    """
    Testing machinery for headers.
    """
    name = None
    inputs = None
    expected_out = None
    expected_err = None

    def setUp(self):
        "Test setup."
        from redbot.message import DummyMsg
        self.msg = DummyMsg()

    def test_header(self):
        "Test the header."
        if not self.name:
            return self.skipTest('')
        self.msg.headers = [(self.name, inp) for inp in self.inputs]
        process_headers(self.msg)
        out = self.msg.parsed_headers.get(self.name.lower(), None)
        self.assertEqual(self.expected_out, out,
            "%s != %s" % (str(self.expected_out), str(out)))
        diff = set(
            [n.__name__ for n in self.expected_err]).symmetric_difference(
            set(self.msg.note_classes)
        )
        for msg in self.msg.notes: # check formatting
            msg.vars.update({'field_name': self.name, 'response': 'response'})
            self.assertTrue(msg.text % msg.vars)
            self.assertTrue(msg.summary % msg.vars)
        self.assertEqual(len(diff), 0, "Mismatched notes: %s" % diff)

