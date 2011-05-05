#!/usr/bin/env python

"""
Formatters for RED output.
"""

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

from collections import defaultdict

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
    
    def __init__(self, ui_uri, uri, req_hdrs, lang, output, **kw):
        """
        Formatter for the given URI, writing
        to the callable output(uni_str). Output is Unicode; callee
        is responsible for encoding correctly.
        """
        self.ui_uri = ui_uri
        self.uri = uri
        self.req_hdrs = req_hdrs
        self.lang = lang
        self.output = output
        self.kw = kw
        self.red = None

    def set_red(self, red):
        """
        Set the RED state to format.
        """
        self.red = red
        
    def done(self):
        """Clean up. Must be called by finish_output."""
        self.red = None
        self.output = None
    
    def feed(self, red, sample):
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

from redbot.formatter import *
