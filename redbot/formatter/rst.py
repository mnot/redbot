#!/usr/bin/env python

"""
RST formatter for REDbot.
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

### FIXME: This code is NOT yet converted to the new Formatter.

import redbot.speak as rs

nl = u"\n"

class RstOutputFormatter(object):
    
    msg_categories = [
        rs.c.GENERAL, rs.c.CONNECTION, rs.c.CONNEG, rs.c.CACHING, rs.c.VALIDATION, rs.c.RANGE
    ]

    def __init__(self, red):
        self.red = red

    def print_headers(self):
        print "HTTP/%s %s %s" % (self.red.res_version,
            self.red.res_status, self.red.res_phrase)
        print "Response headers"
        print "----------------"
        print ""
        print "::"
        print ""
        print nl.join([ "\t%s:%s" % header for header in self.red.res_hdrs])
        #declaring flag definitions
        print RstOutputFormatter.flag_definition()

    def print_recommendations(self):
        print ""
        nl.join([str(self.print_recommendation(str(category))) for category in self.msg_categories])
        
    def print_recommendation(self, category):
        messages = [msg for msg in self.red.messages if msg.category == category]
        if not messages:
            return nl
        out = []
        if [msg for msg in messages]:
            out.append("%s:\n" % category)
        for m in messages:
            out.append(
                "- %s" %
                (self.flagize(m.level, m.summary["en"] % m.vars))
            )
            smsgs = [msg for msg in getattr(m.subrequest, "messages", []) if msg.level in [rs.l.BAD]]
            if smsgs:
                out.append("")
                for sm in smsgs:
                    out.append(
                        "%s" %
                        (self.flagize(sm.level, sm.summary["en"] % sm.vars))
                    )
                out.append("")
        out.append("")
        print nl.join(out)

    def flagize(self, level, string):
        # info
        flag = "|flag-info|"

        if level == "good":
            flag = "|flag-good|"

        if level == "bad":
            flag = "|flag-bad|"

        if level == "warning":
            flag = "|flag-warning|"

        return flag + " " + string

    @staticmethod
    def flag_definition():
        flag_dir = "web/icon/"
        flag_definition_list = {
            "good":"accept1.png", "bad":"remove-16.png", "warning":"yellowflag1.png", "info":"infomation-16.png"
        }

        out = []
        out.append("")
       
        for flag, icon in flag_definition_list.items():
            out.append(".. |flag-" + flag + "| image:: " + flag_dir + icon + nl + "             :width: 16px")

        return nl.join(out)
