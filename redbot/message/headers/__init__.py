#!/usr/bin/env python

"""
The Resource Expert Droid header checks.

process_headers() will process a list of (key, val) tuples.
"""

from copy import copy
from functools import partial
import re
import sys
from typing import Any, Callable, List, Dict, Optional, Tuple, Type, Union, TYPE_CHECKING
import unittest

from redbot.syntax import rfc7230, rfc7231
from redbot.formatter import f_num
from redbot.type import StrHeaderListType, RawHeaderListType, HeaderDictType, AddNoteMethodType

from ._utils import RE_FLAGS, parse_date, unquote_string, split_string, parse_params
from ._notes import *

if TYPE_CHECKING:
    from redbot.message import HttpMessage # pylint: disable=cyclic-import,unused-import

# base URLs for references
rfc2616 = "http://tools.ietf.org/html/rfc2616.html#%s"
rfc6265 = "http://tools.ietf.org/html/rfc6265.html#%s"
rfc6266 = "http://tools.ietf.org/html/rfc6266.html#section-4"

### configuration
MAX_HDR_SIZE = 4 * 1024
MAX_TTL_HDR = 8 * 1000


class HttpHeader(object):
    """A HTTP Header handler."""
    canonical_name = None # type: str
    description = None # type: str
    reference = None # type: str
    syntax = None # type: Union[str, rfc7230.list_rule, bool] # Verbose regular expression to match.
    list_header = None # type: bool                     # Can be split into values on commas.
    nonstandard_syntax = False # type: bool             # Don't check for a single value at the end.
    deprecated = None # type: bool
    valid_in_requests = None # type: bool
    valid_in_responses = None # type: bool
    no_coverage = False  # type: bool                   # Turns off coverage checks.

    def __init__(self, wire_name: str, message: 'HttpMessage') -> None:
        self.wire_name = wire_name.strip()
        self.message = message
        self.norm_name = self.wire_name.lower()
        if self.canonical_name is None:
            self.canonical_name = self.wire_name
        self.value = [] # type: Any

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Any:
        """
        Given a string value and an add_note function, parse and return the result."""
        return field_value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        """
        Called once header processing is done; typically used to evaluate an entire
        header's values.
        """
        pass

    def handle_input(self, field_value: str, add_note: AddNoteMethodType) -> None:
        """
        Basic input processing on a new field value.
        """

        # split before processing if a list header
        if self.list_header:
            values = self.split_list_header(field_value)
        else:
            values = [field_value]
        for value in values:
          # check field value syntax
            if self.syntax:
                element_syntax = isinstance(self.syntax, rfc7230.list_rule) \
                  and self.syntax.element or self.syntax
                if not re.match(r"^\s*(?:%s)\s*$" % element_syntax, value, RE_FLAGS):
                    add_note(BAD_SYNTAX, ref_uri=self.reference)
            try:
                parsed_value = self.parse(value.strip(), add_note)
            except ValueError:
                continue # we assume that the parser made a note of the problem.
            self.value.append(parsed_value)

    @staticmethod
    def split_list_header(field_value: str) -> List[str]:
        "Split a header field value on commas. needs to conform to the #rule."
        return [f.strip() for f in
                re.findall(r'((?:[^",]|%s)+)(?=%s|\s*$)' % (
                    rfc7230.quoted_string,
                    r"(?:\s*(?:,\s*)+)"
                ), field_value, RE_FLAGS)
                if f] or []

    def finish(self, message: 'HttpMessage', add_note: AddNoteMethodType) -> None:
        """
        Called when all headers are available.
        """

        # check field name syntax
        if not re.match("^%s$" % rfc7230.token, self.wire_name, RE_FLAGS):
            add_note(FIELD_NAME_BAD_SYNTAX)
        if self.deprecated:
            deprecation_ref = getattr(self, 'deprecation_ref', self.reference)
            add_note(HEADER_DEPRECATED, deprecation_ref=deprecation_ref)
        if not self.list_header and not self.nonstandard_syntax:
            if len(self.value) == 0:
                self.value = None
            elif len(self.value) == 1:
                self.value = self.value[-1]
            elif len(self.value) > 1:
                add_note(SINGLE_HEADER_REPEAT)
                self.value = self.value[-1]
        if message.is_request:
            if not self.valid_in_requests:
                add_note(RESPONSE_HDR_IN_REQUEST)
        else:
            if not self.valid_in_responses:
                add_note(REQUEST_HDR_IN_RESPONSE)
        self.evaluate(add_note)



class UnknownHttpHeader(HttpHeader):
    """A HTTP header that we don't recognise."""
    list_header = True
    valid_in_requests = True
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> Any:
        return field_value

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        return


class HeaderProcessor(object):
    """
    Parses and runs checks on a set of headers.
    """
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

    def __init__(self, message: 'HttpMessage') -> None:
        self.message = message
        self._header_handlers = {}  # type: Dict[str, HttpHeader]

    def process(self, headers: RawHeaderListType) -> Tuple[StrHeaderListType, HeaderDictType]:
        """
        Given a list of (bytes name, bytes value) headers and:
         - calculate the total header block size
         - call msg.add_note as appropriate
        Returns:
         - a list of unicode header tuples
         - a dict of parsed header values
        """
        unicode_headers = []   # unicode version of the header tuples
        parsed_headers = {}    # dictionary of parsed header values
        offset = 0             # what number header we're on

        # estimate the start-lines size
        header_block_size = len(self.message.version)
        if self.message.is_request:
            header_block_size += len(self.message.method) + len(self.message.uri) + 2
        else:
            header_block_size += len(self.message.status_phrase) + 5

        for name, value in headers:
            offset += 1
            add_note = partial(self.message.add_note, "offset-%s" % offset)

            # track header size
            header_size = len(name) + len(value)
            header_block_size += header_size

            # decode the header to make it unicode clean
            try:
                str_name = name.decode('ascii', 'strict')
            except UnicodeError:
                str_name = name.decode('ascii', 'ignore')
                add_note(HEADER_NAME_ENCODING, field_name=str_name)
            try:
                str_value = value.decode('ascii', 'strict')
            except UnicodeError:
                str_value = value.decode('iso-8859-1', 'replace')
                add_note(HEADER_VALUE_ENCODING, field_name=str_name)
            unicode_headers.append((str_name, str_value))

            header_handler = self.get_header_handler(str_name)
            field_add_note = partial(add_note, # type: ignore
                                     field_name=header_handler.canonical_name)
            header_handler.handle_input(str_value, field_add_note)

            if header_size > MAX_HDR_SIZE:
                add_note(HEADER_TOO_LARGE, field_name=header_handler.canonical_name,
                         header_size=f_num(header_size))

        # check each of the complete header values and get the parsed value
        for header_name, header_handler in list(self._header_handlers.items()):
            header_add_note = partial(self.message.add_note,
                                      "header-%s" % header_handler.canonical_name.lower(),
                                      field_name=header_handler.canonical_name)
            header_handler.finish(self.message, header_add_note) # type: ignore
            parsed_headers[header_handler.norm_name] = header_handler.value

        return unicode_headers, parsed_headers

    def get_header_handler(self, header_name: str) -> HttpHeader:
        """
        If a header handler has already been instantiated for header_name, return it;
        otherwise, instantiate and return a new one.
        """
        norm_name = header_name.lower()
        if norm_name in self._header_handlers:
            return self._header_handlers[norm_name]
        else:
            handler = self.find_header_handler(header_name)(header_name, self.message)
            self._header_handlers[norm_name] = handler
            return handler

    @staticmethod
    def find_header_handler(header_name: str, default: bool=True) -> Optional[Type[HttpHeader]]:
        """
        Return a header handler class for the given field name.

        If default is true, return a dummy if one isn't found; otherwise, None.
        """

        name_token = HeaderProcessor.name_token(header_name)
        hdr_module = HeaderProcessor.find_header_module(name_token)
        if hdr_module and hasattr(hdr_module, name_token):
            return getattr(hdr_module, name_token)
        if default:
            return UnknownHttpHeader
        return None

    @staticmethod
    def find_header_module(header_name: str) -> Any:
        """
        Return a module for the given field name, or None if it can't be found.
        """
        name_token = HeaderProcessor.name_token(header_name)
        if name_token[0] == '_':  # these are special
            return
        if name_token in HeaderProcessor.header_aliases:
            name_token = HeaderProcessor.header_aliases[name_token]
        try:
            module_name = "redbot.message.headers.%s" % name_token
            __import__(module_name)
            return sys.modules[module_name]
        except (ImportError, KeyError, TypeError):
            return

    @staticmethod
    def name_token(header_name: str) -> str:
        """
        Return a tokenised, python-friendly name for a header.
        """
        return header_name.replace('-', '_').lower()


class HeaderTest(unittest.TestCase):
    """
    Testing machinery for headers.
    """
    name = None # type: str
    inputs = [] # type: list[bytes]
    expected_out = None # type: Any
    expected_err = [] # type: List[Type[Note]]

    def setUp(self) -> None:
        "Test setup."
        from redbot.message import DummyMsg
        self.message = DummyMsg()
        self.set_context(self.message)

    def test_header(self) -> Any:
        "Test the header."
        if not self.name:
            return self.skipTest('')
        if not isinstance(self.name, bytes):
            name = self.name.encode('utf-8')
        else:
            name = self.name
        inputs = []
        for val in self.inputs:
            if not isinstance(val, bytes):
                val = val.encode('utf-8')
            inputs.append(val)
        hp = HeaderProcessor(self.message)
        self.message.headers, self.message.parsed_headers = \
            hp.process([(name, inp) for inp in inputs])
        out = self.message.parsed_headers.get(self.name.lower(), 'HEADER HANDLER NOT FOUND')
        self.assertEqual(self.expected_out, out)
        diff = set(
            [n.__name__ for n in self.expected_err]).symmetric_difference( # type: ignore
                set(self.message.note_classes))
        for message in self.message.notes: # check formatting
            message.vars.update({'field_name': self.name, 'response': 'response'})
            self.assertTrue(message.text % message.vars)
            self.assertTrue(message.summary % message.vars)
        self.assertEqual(len(diff), 0, "Mismatched notes: %s" % diff)

    def set_context(self, message: 'HttpMessage') -> None:
        pass
