#!/usr/bin/env python

"""
A Web UI for RED, the Resource Expert Droid.
"""

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

### Configuration ##########################################################

# FIXME: make language configurable/dynamic
lang = "en"

# HTML header file
header_file = "red_header.html"

# Validator uris, by media type
validators = {
    'text/html': "http://validator.w3.org/check?uri=%s",
    'text/css': "http://jigsaw.w3.org/css-validator/validator?uri=%s&",
    'application/xhtml+xml': "http://validator.w3.org/check?uri=%s",    
    'application/atom+xml': "http://feedvalidator.org/check.cgi?url=%s",
    'application/rss+xml': "http://feedvalidator.org/check.cgi?url=%s",
}

# Media types that browsers can view natively
viewable_types = [
    'text/plain',
    'text/html',
    'application/xhtml+xml',
    'application/pdf',
    'image/gif',
    'image/jpeg',
    'image/jpg',
    'image/png',
    'application/javascript',
    'application/x-javascript',
    'text/javascript',
    'text/x-javascript',
    'text/css',
]

# Where to store exceptions; set to None to disable traceback logging
logdir = 'exceptions'

# any request headers that we want to *always* send.
req_hdrs = []

### End configuration ######################################################

import cgitb; cgitb.enable(logdir=logdir)
import sys
import cgi
import time
import textwrap
from urlparse import urljoin
from cgi import escape as e

assert sys.version_info[0] == 2 and sys.version_info[1] >= 5, "Please use Python 2.5 or greater"

import link_parse
import red
import red_header
import red_speak as rs
import nbhttp.error


# the order of message categories to display
msg_categories = [
    rs.GENERAL, rs.CONNECTION, rs.CONNEG, rs.CACHING, rs.VALIDATION, rs.RANGE
]

# HTML template for the main response body
template = u"""\
<pre>
%(response)s
</pre>

<p class="options">
	%(options)s
</p>

%(messages)s

<!-- p class="stats">%(stats)s</p -->

<div class='hidden_desc' id='link_list'>%(links)s</div>

"""

# HTML template for error bodies
error_template = u"""\

<p class="error">
 %s
</p>
"""

# HTML footer for all generated pages
red_footer = u"""\

<p class="version">this is RED %(version)s.</p>
<p class="navigation"> 
<a href="http://REDbot.org/about/">about RED</a> |
<a href="http://REDbot.org/terms/">terms of use</a> | 
<a href="http://REDbot.org/project">RED project</a> |
<a href="javascript:location%%20=%%20'http://redbot.org/?uri='+escape(location);%%20void%%200" 
title="drag me to your toolbar to use RED any time.">RED</a> bookmarklet 
</p>
</div>


<div id="long_mesg"/>


</body>
</html>
"""

nl = u"\n"

class RedWebUi(object):
    """
    A Web UI for RED.
    
    Given a URI, run RED on it and present the results to STDOUT as HTML.
    """
    def __init__(self, uri):
        print red_header.__doc__ % {
                        'js_uri': uri.replace('"', r'\"'), 
                        'html_uri': e(uri),
                        } 
        sys.stdout.flush()
        self.links = {}
        self.link_droids = []
        self.descend_links = False
        if uri:
            start = time.time()
            link_parser = link_parse.HTMLLinkParser(uri, self.processLink)
            self.red = red.ResourceExpertDroid(
                uri, 
                req_hdrs=req_hdrs,
                status_cb=self.updateStatus,
                body_procs=[link_parser.feed],
            )
            self.updateStatus('Done.')
            self.elapsed = time.time() - start
            if self.red.res_complete:
                self.header_presenter = HeaderPresenter(self.red)
                print self.presentResults()
            else:
                if self.red.res_error['desc'] == nbhttp.error.ERR_CONNECT['desc']:
                    print error_template % "Could not connect to the server (%s)" % \
                        self.red.res_error.get('detail', "unknown")
                elif self.red.res_error['desc'] == nbhttp.error.ERR_URL['desc']:
                    print error_template % self.red.res_error.get(
                                          'detail', "RED can't fetch that URL.")
                else:
                    raise AssertionError, "Unidentified incomplete response error."                
        print red_footer % {'version': red.__version__}
        sys.stdout.flush()            

    def processLink(self, link, tag, title):
        "Handle a link from content"
        if not self.links.has_key(tag):
            self.links[tag] = set()
        self.links[tag].add((link, title))
    
        if self.descend_links:
            self.link_droids.append((
                    red.ResourceExpertDroid(
                            link, 
                            req_hdrs=req_hdrs,
                            status_cb=self.updateStatus
                    ),
                    tag,
                    title
            ))

    def presentResults(self):
        "Fill in the template with RED's results."
        result_strings = {
            'response': self.presentResponse(),
            'options': nl.join(self.presentOptions()),
            'messages': nl.join([self.presentCategory(cat) for cat in msg_categories]),
            'links': nl.join(self.presentLinks()),
            'stats':  u"that took %(elapsed)2.2f seconds" % {'elapsed': self.elapsed}
        }
        return (template % result_strings).encode("utf-8")

    def presentResponse(self):
        "Return the HTTP response line and headers as HTML"
        return \
        u"    <span class='status'>HTTP/%s %s %s</span>\n" % (
            e(str(self.red.res_version)), 
            e(str(self.red.res_status)), 
            e(str(self.red.res_phrase))
        ) + \
        nl.join([self.presentHeader(f,v) for (f,v) in self.red.res_hdrs])

    def presentHeader(self, name, value):
        "Return an individual HTML header as HTML"
        token_name = name.lower()
        return u"    <span class='header-%s hdr'>%s:%s</span>" % (
            e(token_name), e(name), self.header_presenter.Show(name, value))

    def presentCategory(self, category):
        "For a given category, return all of the messages in it as an HTML list"
        messages = [msg for msg in self.red.messages if msg[1][0] == category]
        if not messages:
            return nl
        out = [u"<h3>%s</h3>\n<ul>\n" % category]
        for (s, (c, l, m, lm), sr, v) in messages:
            out.append(u"<li class='%s %s msg'>%s <span class='hidden_desc'>%s</span>" % 
                    (l, e(s), e(m[lang]%v), lm[lang]%v)
            )
            out.append(u"</li>")
            smsgs = [msg for msg in getattr(sr, "messages", []) if msg[1][1] in [rs.BAD]]
            if smsgs: 
                out.append(u"<ul>")
                for (s, (c, l, m, lm), sms, v) in smsgs:
                    out.append(
                        u"<li class='%s %s msg'>%s <span class='hidden_desc'>%s</span></li>" % 
                        (l, e(s), e(m[lang]%v), lm[lang]%v)
                    )
                out.append(u"</ul>")
        out.append(u"</ul>\n")
        return nl.join(out)
        
    def presentOptions(self):
        "Return things that the user can do with the URI as HTML links"
        options = []
        media_type = self.red.parsed_hdrs.get('content-type', [None])[0]
        if media_type in viewable_types:
            options.append(u"<a href='%s'>view</a>" % self.red.uri)
        if len(self.links) > 0:
            options.append(u"<a href='#link_list' class='link_view' title='%s'>links</a>" %
                           self.red.uri)
        if validators.has_key(media_type):
            options.append(u"<a href='%s'>validate body</a>" % 
                           validators[media_type] % self.red.uri)
        return options

    link_order = [
          ('link', 'Head Links'), 
          ('script', 'Script Links'), 
          ('frame', 'Frame Links'),
          ('a', 'Body Links')
    ]
    def presentLinks(self):
        "Return an HTML list of the links in the response, as RED URIs"
        out = []
        for tag, name in self.link_order:
            link_set = self.links.get(tag, set())
            if len(link_set) > 0:
                link_list = list(link_set)
                link_list.sort()
                out.append(u"<h3>%s</h3>" % name)
                out.append(u"<ul>")
                for link, title in link_set:
                    al = u"?uri=%s" % e(link)
                    out.append(u"<li><a href='%s' title='%s'>%s</a></li>" % (
                                 al, e(link), e(title or link)))
                out.append(u"</ul>")
        return out

    def updateStatus(self, message):
        "Update the status bar of the browser"
        print u"""
<script language="JavaScript">
<!--
window.status="%s";
-->
</script>
        """ % \
            e(str(message))
        sys.stdout.flush()


tr = textwrap.TextWrapper(width=65, subsequent_indent=" "*8)
def i(value, sub_width):
    "wrap a line to fit in the header box"
    tr.width = 65 - sub_width
    return tr.fill(value)


class HeaderPresenter(object):
    """
    Present a header in the Web UI. By default, it will:
       - Escape HTML sequences to avoid XSS attacks
       - Wrap long lines
    However if a method is present that corresponds to the header's
    field-name, that method will be run instead to represent the value. 
    """
    
    def __init__(self, red):
        self.red = red
        
    def Show(self, name, value):
        "Return the given header name/value pair after presentation processing"
        name = name.lower()
        name_token = name.replace('-', '_')
        if name_token[0] != "_" and hasattr(self, name_token):
            return getattr(self, name_token)(name, value)
        else:
            return i(e(value), len(name))

    def BARE_URI(self, name, value):
        "Present a bare URI header value"
        value = value.rstrip()
        svalue = value.lstrip()
        space = len(value) - len(svalue)
        return u"%s<a href='?uri=%s'>%s</a>" % ( " " * space,
            e(urljoin(self.red.uri, svalue)), i(e(svalue), len(name)))
    content_location = \
    location = \
    x_xrds_location = \
    BARE_URI


if __name__ == "__main__":
    form = cgi.FieldStorage()
    try:
        test_uri = sys.argv[1]
    except IndexError:
        test_uri = form.getfirst("uri", "")
    print "Content-Type: text/html; charset=utf-8"
    if test_uri:
        print "Cache-Control: max-age=60, must-revalidate"
    else:
        print "Cache-Control: max-age=3600"
    print
    RedWebUi(test_uri)