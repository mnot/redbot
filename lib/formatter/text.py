#!/usr/bin/env python

"""
HAR Formatter for REDbot.
"""

__author__ = "Jerome Renard <jerome.renard@gmail.com>"
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

import operator

import nbhttp.error as nberror
import redbot.speak as rs

from redbot.formatter import Formatter

nl = u"\n"

# TODO: errors and status on stderr with CLI?

class BaseTextFormatter(Formatter):
    """
    Base class for text formatters."""
    name = "txt"
    media_type = "text/plain"

    msg_categories = [
        rs.c.GENERAL, rs.c.CONNECTION, rs.c.CONNEG, 
        rs.c.CACHING, rs.c.VALIDATION, rs.c.RANGE
    ]

    link_order = [
          ('link', 'Head Links'),
          ('script', 'Script Links'),
          ('frame', 'Frame Links'),
          ('iframe', 'IFrame Links'),
          ('img', 'Image Links'),
    ]

    error_template = "Error: %s\n"

    def __init__(self, *args, **kw):
        Formatter.__init__(self, *args, **kw)

    def start_output(self):
        pass

    def feed(self, red, chunk):
        pass

    def status(self, msg):
        pass

    def finish_output(self, red):
        "Fill in the template with RED's results."
        if red.res_complete:
            self.output(self.format_headers(red) + nl + nl)
            self.output(self.format_recommendations(red) + nl)
        else:
            if red.res_error['desc'] == nberror.ERR_CONNECT['desc']:
                self.output(self.error_template % "Could not connect to the server (%s)" % \
                    red.res_error.get('detail', "unknown"))
            elif red.res_error['desc'] == nberror.ERR_URL['desc']:
                self.output(self.error_template % red.res_error.get(
                    'detail', "RED can't fetch that URL."))
            elif red.res_error['desc'] == nberror.ERR_READ_TIMEOUT['desc']:
                self.output(self.error_template % red.res_error['desc'])
            elif red.res_error['desc'] == nberror.ERR_HTTP_VERSION['desc']:
                self.output(self.error_template % "<code>%s</code> isn't HTTP." % \
                    red.res_error.get('detail', '')[:20])
            else:
                raise AssertionError, "Unidentified incomplete response error."

    def format_headers(self, red):
        out = [u"HTTP/%s %s %s" % (
            red.res_version, red.res_status, red.res_phrase)]
        return nl.join(out + [u"%s:%s" % h for h in red.res_hdrs])

    def format_recommendations(self, red):
        return "".join([self.format_recommendation(red, category) \
            for category in self.msg_categories])

    def format_recommendation(self, red, category):
        messages = [msg for msg in red.messages if msg.category == category]
        if not messages:
            return ""
        out = []
        if [msg for msg in messages]:
            out.append(u"* %s:" % category)
        for m in messages:
            out.append(
                u"  * %s" % (self.colorize(m.level, m.summary["en"] % m.vars))
            )
            smsgs = [msg for msg in getattr(m.subrequest, "messages", []) if msg.level in [rs.l.BAD]]
            if smsgs:
                out.append("")
                for sm in smsgs:
                    out.append(
                        u"    * %s" %
                        (self.colorize(sm.level, sm.summary["en"] % sm.vars))
                    )
                out.append(nl)
        out.append(nl)
        return nl.join(out)

    @staticmethod
    def colorize(level, string):
        # info
        color_start = u"\033[0;32m"
        color_end   = u"\033[0;39m"

        if level == "good":
            color_start = u"\033[1;32m"
            color_end   = u"\033[0;39m"

        if level == "bad":
            color_start = u"\033[1;31m"
            color_end   = u"\033[0;39m"

        if level == "warning":
            color_start = u"\033[1;33m"
            color_end   = u"\033[0;39m"

        if level == "uri":
            color_start = u"\033[1;34m"
            color_end   = u"\033[0;39m"

        return color_start + string + color_end



class TextFormatter(BaseTextFormatter):
    """
    Format a RED object as text.
    """
    name = "txt"
    media_type = "text/plain"

    def __init__(self, *args, **kw):
        BaseTextFormatter.__init__(self, *args, **kw)



class TextListFormatter(BaseTextFormatter):
    """
    Format multiple RED responses as a textual list.
    """
    name = "txt"
    media_type = "text/plain"
    can_multiple = True


    def __init__(self, *args, **kw):
        BaseTextFormatter.__init__(self, *args, **kw)

    def start_output(self):
        pass

    def finish_output(self, red):
        "Fill in the template with RED's results."
        for hdr_tag, heading in self.link_order:
            droids = [d[0] for d in red.link_droids if d[1] == hdr_tag]
            self.output("%s\n%s (%d)\n%s\n" % ("="*80, heading, len(droids), "="*80))
            if droids:
                droids.sort(key=operator.attrgetter('uri'))
                for droid in droids:
                    self.output(self.format_uri(droid) + nl + nl)
                    self.output(self.format_headers(droid) + nl + nl)
                    self.output(self.format_recommendations(droid) + nl + nl)


    def format_uri(self, red):
        return self.colorize("uri", red.uri)
