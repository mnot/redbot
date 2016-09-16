#!/usr/bin/env python

"""
Formatters for RED output.
"""


from collections import defaultdict
import locale
import time
import unittest

__all__ = ['html', 'text', 'har']

_formatters = defaultdict(list)

class FormatterType(type):
    """
    Type for Formatters that populates _formatters, to keep track
    of names and their mapping to Formatter-derived classes.
    """
    def __new__(mcs, name, bases, attrs):
        cls = super(FormatterType, mcs).__new__(mcs, name, bases, attrs)
        if attrs.get('name', None) != None:
            _formatters[attrs['name']].append(cls)
        return cls

def find_formatter(name, default="html", multiple=False):
    """
    Find the formatter for name, and use default if it can't be found.
    If you need to represent more than one result, set multiple to True.

    Note that you MUST "from redbot.formatter import *" before calling.
    Yes, that's a hack that needs to be fixed.
    """
    if name not in _formatters.keys():
        name = default
    # find single-preferred formatters first
    if not multiple:
        for candidate in _formatters[name]:
            if not candidate.can_multiple:
                return candidate
    for candidate in _formatters[name]:
        if candidate.can_multiple:
            return candidate
    raise RuntimeError, "Can't find a format in %s" % _formatters

def available_formatters():
    """
    Return a list of the available formatter names.

    Note that you MUST "from redbot.formatter import *" before calling.
    Yes, that's a hack that needs to be fixed.
    """
    return _formatters.keys()


class Formatter(object):
    """
    A formatter for RED objects. start_output() is called first,
    followed by zero or more calls to feed() and status(), finishing
    with finish_output().

    Is available to UIs based upon the 'name' attribute.
    """
    __metaclass__ = FormatterType
    media_type = None # the media type of the format.
    name = None # name of the format.
    can_multiple = False # formatter can represent multiple responses.

    def __init__(self, ui_uri, uri, req_hdrs, check_type, lang, output, **kw):
        """
        Formatter for the given URI, writing
        to the callable output(uni_str). Output is Unicode; callee
        is responsible for encoding correctly.
        """
        self.ui_uri = ui_uri         # the URI of the HTML UI itself
        self.uri = uri               # the URI under test
        self.req_hdrs = req_hdrs     # list of (name, value) request headers
        self.check_type = check_type # 'Identity', 'If-None-Match', 'If-Modified-Since', 'Range'
        self.lang = lang
        self.output = output         # output file object
        self.kw = kw                 # extra keyword arguments
        self.state = None

    def set_state(self, state):
        """
        Set the HttpResource to be formatted.
        """
        self.state = state

    def done(self):
        """Clean up. Must be called by finish_output."""
        self.state = None
        self.output = None

    def feed(self, state, sample):
        """
        Feed a body sample to processor(s).
        """
        raise NotImplementedError

    def start_output(self):
        """
        Send preliminary output.
        """
        raise NotImplementedError

    def status(self, status):
        """
        Output a status message.
        """
        raise NotImplementedError

    def finish_output(self):
        """
        Finalise output.
        """
        raise NotImplementedError


def f_num(i, by1024=False):
    "Format a number according to the locale."
    if by1024:
        k = int(i / 1024)
        m = int(k / 1024)
        g = int(m / 1024)
        if g:
            return locale.format("%d", g, grouping=True) + "g"
        elif m:
            return locale.format("%d", m, grouping=True) + "m"
        elif k:
            return locale.format("%d", k, grouping=True) + "k"
    return locale.format("%d", i, grouping=True)


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
    age = round(now - utime)
    if age == 0:
        return signs[show_sign][0]

    a = abs(age)
    yrs = int(a / 60 / 60 / 24 / 365)
    day = int(a / 60 / 60 / 24) % 365
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


class RelativeTimeTester(unittest.TestCase):
    minute = 60
    hour = minute * 60
    day = hour * 24
    year = day * 365
    cases = [
        (+year, "1 year from now"),
        (-year, "1 year ago"),
        (+year+1, "1 year 1 sec from now"),
        (+year+.9, "1 year 1 sec from now"),
        (+year+day, "1 year 1 day from now"),
        (+year+(10*day), "1 year 10 days from now"),
        (+year+(90*day)+(3*hour), "1 year 90 days from now"),
        (+(13*day)-.4, "13 days from now"),
    ]

    def setUp(self):
        self.now = time.time()

    def test_relative_time(self):
        for delta, result in self.cases:
            self.assertEqual(
                relative_time(self.now + delta, self.now),
                result
            )
