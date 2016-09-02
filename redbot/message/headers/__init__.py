#!/usr/bin/env python

"""
The Resource Expert Droid header checks.

process_headers() will process a list of (key, val) tuples.
"""

from copy import copy
from functools import partial
import re
import sys
import unittest

from redbot.message import http_syntax as syntax
from redbot.formatter import f_num
import redbot.speak as rs

from ._decorators import *
from ._utils import parse_date, unquote_string, split_string, parse_params
from ._notes import SINGLE_HEADER_REPEAT, BAD_SYNTAX, BAD_DATE_SYNTAX, PARAM_REPEATS, PARAM_STAR_QUOTED

# base URLs for references
rfc2616 = u"http://tools.ietf.org/html/rfc2616.html#%s"
rfc5988 = u"http://tools.ietf.org/html/rfc5988.html#section-5"
rfc6265 = u"http://tools.ietf.org/html/rfc6265.html#%s"
rfc6266 = u"http://tools.ietf.org/html/rfc6266.html#section-4"

### configuration
MAX_HDR_SIZE = 4 * 1024
MAX_TTL_HDR = 8 * 1000


class HttpHeader(object):
    """A HTTP Header handler."""
    canonical_name = None
    description = None
    reference = None
    syntax = None
    list_header = None
    deprecated = None
    valid_in_requests = None
    valid_in_responses = None
    no_coverage = False  # turns off coverage checks for syntax and tests.

    def __init__(self, wire_name):
        self.wire_name = wire_name.strip()
        self.norm_name = self.wire_name.lower()
        if self.canonical_name is None:
            self.canonical_name = self.wire_name
        if self.list_header:
            self.value = []
        else:
            self.value = None

    def parse(self, field_value, add_note):
        """
        Given a string value and a subject indicating an anchor that messages can
        refer to, parse and return the result."""
        raise NotImplementedError()

    def evaluate(self, add_note):
        """
        Called once header processing is done; typically used to evaluate an entire
        header's values.
        """
        raise NotImplementedError()

    def handle_input(self, field_value, add_note):
        """
        XXX
        """

        # check field value syntax
        if self.syntax and not re.match(r"^\s*(?:%s)\s*$" % self.syntax, field_value, re.VERBOSE):
            add_note(rs.BAD_SYNTAX, ref_uri=self.reference)
        # split before processing if a list header
        if self.list_header:
            values = self.split_list_header(field_value)
        else:
            values = [field_value]
        for value in values:
            parsed_value = self.parse(value.strip(), add_note)
            if self.list_header:
                self.value.append(parsed_value)
            else:
                self.value = parsed_value

    @staticmethod
    def split_list_header(field_value):
        "Split a header field value on commas. needs to conform to the #rule."
        return [f.strip() for f in re.findall(r'((?:[^",]|%s)+)(?=%s|\s*$)' %
            (syntax.QUOTED_STRING, syntax.COMMA), field_value)] or ['']

    def finish(self, message, add_note):
        """
        Called when all headers are available.
        """

        # check field name syntax
        if not re.match("^%s$" % syntax.TOKEN, name, re.VERBOSE):
            add_note(rs.FIELD_NAME_BAD_SYNTAX)
        if self.deprecated:
            pass ###
        if not self.list_value and XXX:
            add_note(rs.SINGLE_HEADER_REPEAT)
        if message.is_request:
            if not self.valid_in_requests:
                pass ###
        else:
            if not self.valid_in_responses:
                pass ###
        self.evaluate(add_note)



class DummyHttpHeader(HttpHeader):
    """A HTTP header that we don't recognise."""
    list_header = True
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, value, add_note):
        return value

    def evaluate(self, add_note):
        return


class HeaderProcessor(object):

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

    def __init__(self, message):
        print "I'm processing!"
        self.message = message
        self._header_handlers = {}
        unicode_headers, parsed_headers = self.process()
        message.headers = unicode_headers
        message.parsed_headers = parsed_headers

    def process(self):
        """
        Given a message, parse its headers and:
         - calculate the total header block size
         - call msg.add_note as appropriate
        Returns:
         - a list of unicode header tuples
         - a dict of parsed header values
        """
        import sys
        sys.stderr.write("BOO!\n")
        unicode_headers = []   # unicode version of the header tuples
        parsed_headers = {}    # dictionary of parsed header values
        offset = 0             # what number header we're on

        # estimate the start-lines size
        header_block_size = len(self.message.version)
        if self.message.is_request:
            header_block_size += len(self.message.method) + len(self.message.uri) + 2
        else:
            header_block_size += len(self.message.status_phrase) + 5

        for name, value in self.message.headers:
            offset += 1
            add_note = partial(self.message.add_note, subject="offset-%s" % offset)

            # track header size
            header_size = len(name) + len(value)
            if header_size > MAX_HDR_SIZE:
                add_note(rs.HEADER_TOO_LARGE, field_name=name, header_size=f_num(header_size))
            header_block_size += header_size

            # decode the header to make it unicode clean
            try:
                name = name.decode('ascii', 'strict')
            except UnicodeError:
                name = name.decode('ascii', 'ignore')
                add_note(rs.HEADER_NAME_ENCODING, field_name=name)
            try:
                value = value.decode('ascii', 'strict')
            except UnicodeError:
                value = value.decode('iso-8859-1', 'replace')
                add_note(rs.HEADER_VALUE_ENCODING, field_name=name)
            unicode_headers.append((name, value))

            header_handler = self.get_header_handler(name)
            field_add_note = partial(add_note, field_name=header_handler.canonical_name)
            header_handler.handle_input(value, field_add_note)

        # check each of the complete header values and get the parsed value
        for header_handler in self._header_handlers:
            header_add_note = partial(self.message.add_note,
                                        subject="header-%s" % header_handler.norm_name,
                                        field_name=header_handler.canonical_name
            )
            header_handler.finish(msg, header_add_note)
            parsed_headers[header_handler.norm_name] = header_handler.value

        return unicode_headers, parsed_headers

    def get_header_handler(self, header_name):
        """
        If a header handler has already been instantiated for header_name, return it;
        otherwise, instantiate and return a new one.
        """
        norm_name = header_name.lower()        
        if self._header_handlers.has_key(norm_name):
            return self._header_handlers[norm_name]
        else:
            handler = self.find_header_handler(header_name)(header_name)
            self._header_handlers[norm_name] = handler
            return handler
            
    @staticmethod
    def find_header_handler(header_name, default=True):
        """
        Return a header handler class for the given field name.

        If default is true, return a dummy if one isn't found; otherwise, None.
        """

        name_token = header_name.replace('-', '_').lower().encode('ascii', 'ignore')
        hdr_module = HeaderProcessor.find_header_module(name_token)
        if hdr_module and hasattr(hdr_module, name_token):
            return getattr(hdr_module, name_token)
        if default:
            return DummyHttpHeader

    @staticmethod
    def find_header_module(header_name):
        """
        Return a module for the given field name, or None if it can't be found.
        """
        name_token = header_name.replace('-', '_').lower().encode('ascii', 'ignore')
        if name_token[0] == '_':  # these are special
            return
        if HeaderProcessor.header_aliases.has_key(name_token):
            name_token = HeaderProcessor.header_aliases[name_token]
        try:
            module_name = "redbot.message.headers.%s" % name_token
            __import__(module_name)
            return sys.modules[module_name]
        except (ImportError, KeyError, TypeError):
            return


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

