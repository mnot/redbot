#!/usr/bin/env python

"""
webui.py - A Web UI for RED, the Resource Expert Droid.

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

### Configuration

# FIXME: make language configurable/dynamic
lang = "en"

# header file
header_file = "red_header.html"

# validator uris for media types
validators = {
    'text/html': "http://validator.w3.org/check?uri=%s",
    'text/css': "http://jigsaw.w3.org/css-validator/validator?uri=%s&",
    'application/xhtml+xml': "http://validator.w3.org/check?uri=%s",    
    'application/atom+xml': "http://feedvalidator.org/check.cgi?url=%s",
    'application/rss+xml': "http://feedvalidator.org/check.cgi?url=%s",
}

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

link_parseable_types = [
    'text/html',
    'application/xhtml+xml',
]

logdir = 'exceptions' # set to None to disable traceback logging

### End configuration

import cgitb; cgitb.enable(logdir=logdir)
import sys
import cgi
import time
import textwrap
from HTMLParser import HTMLParser
from urlparse import urljoin
from urllib import quote
from cgi import escape as e

assert sys.version_info[0] == 2 and sys.version_info[1] >= 5, "Please use Python 2.5 or greater"

import red
import red_speak as rs
import red_header

# the order of message categories to display
msg_categories = [
    rs.GENERAL, rs.CONNEG, rs.CONNECTION, rs.CACHING, rs.VALIDATION, rs.RANGE
]

req_headers = []

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

error_template = u"""\

<p class="error">
 %s
</p>
"""

nl = u"\n"

class RedWebUi(object):
    def __init__(self, test_uri):
        print red_header.__doc__ % {'uri': e(test_uri)} 
        sys.stdout.flush()
        self.links = HTMLLinkParser()
        if uri:
            start = time.time()
            try:
                self.red = red.ResourceExpertDroid(uri, 
                    req_headers=req_headers,
                    body_processors=[self.links.feed],
                    status_cb=self.updateStatus
                )
                self.updateStatus('Done.')
                self.elapsed = time.time() - start
                self.header_presenter = HeaderPresenter(self.red)
                print self.presentResults()
            except AssertionError, why:
                print error_template % why
        print red_footer % {'version': red.__version__}
        sys.stdout.flush()            
    
    def presentResults(self):
        result_strings = {
            'uri': e(self.red.response.uri),
            'response': self.presentResponse(),
            'options': nl.join(self.presentOptions()),
            'messages': nl.join([self.presentCategory(cat) for cat in msg_categories]),
            'links': nl.join(self.presentLinks()),
            'stats':  u"that took %(elapsed)2.2f seconds and %(reqs)i request(s)." % {
                'elapsed': self.elapsed, 
                'reqs': red.total_requests                                                                           
                }
        }
        return (template % result_strings).encode("utf-8")

    def presentResponse(self):
        return \
        u"    <span class='response-line'>HTTP/%s %s %s</span>\n" % (
            e(str(self.red.response.version)), 
            e(str(self.red.response.status)), 
            e(str(self.red.response.phrase))
        ) + \
        nl.join([self.presentHeader(f,v) for (f,v) in self.red.response.headers])

    def presentHeader(self, name, value):
        token_name = name.lower()
        return u"    <span class='header-%s hdr'>%s:%s</span>" % (
            e(token_name), e(name), self.header_presenter.Show(name, value))

    def presentCategory(self, category):
        messages = [msg for msg in self.red.messages if msg[1][0] == category]
        if not messages:
            return nl
        return u"<h3>%s</h3>\n<ul>\n" % category \
        + nl.join([
                    u"<li class='%s %s msg'>%s<span class='hidden_desc'>%s</span></li>" % 
                    (l, e(s), e(m[lang]%v), lm[lang]%v) 
                    for (s,(c,l,m,lm),v) in messages
                    ]) \
        + u"</ul>\n"

    def presentOptions(self):
        options = []
        media_type = self.red.response.parsed_hdrs.get('content-type', [None])[0]
        if media_type in viewable_types:
            options.append(u"<a href='%s'>view</a>" % self.red.response.uri)
        if media_type in link_parseable_types:
            if self.links.count > 0:
                options.append(u"<a href='#' class='link_view' title='%s'>links</a>" %
                               self.red.response.uri)
        if validators.has_key(media_type):
            options.append(u"<a href='%s'>validate body</a>" % 
                           validators[media_type] % self.red.response.uri)
        return options

    def presentLinks(self):
        base = self.links.base or self.red.response.uri
        out = []
        for tag, name in self.links.link_order:
            attr, link_set = self.links.links[tag]
            if len(link_set) > 0:
                link_list = list(link_set)
                link_list.sort()
                out.append(u"<h3>%s</h3>" % name)
                out.append(u"<ul>")
                for target in link_set:
                    title = self.links.titles.get(target, target)
                    al = u"?uri=%s" % quote(urljoin(base, target), safe=":;/?#@+$&,")
                    out.append(u"<li><a href='%s' title='%s'>%s</a></li>" % (al, e(target), e(title)))
                out.append(u"</ul>")
        return out

    def updateStatus(self, message):
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
        name = name.lower()
        name_token = name.replace('-', '_')
        if name_token[0] != "_" and hasattr(self, name_token):
            return getattr(self, name_token)(name, value)
        else:
            return i(e(value), len(name))

    def BARE_URI(self, name, value):
        value = value.rstrip()
        svalue = value.lstrip()
        space = len(value) - len(svalue)
        return u"%s<a href='?uri=%s'>%s</a>" % ( " " * space,
            e(urljoin(self.red.response.uri, svalue)), i(e(svalue), len(name)))
    content_location = \
    location = \
    x_xrds_location = \
    BARE_URI


class HTMLLinkParser(HTMLParser):
    def __init__(self):
        self.link_order = (
            ('link', u'Head Links'),
            ('img', u'Images'),
            ('script', u'Scripts'),
            ('frame', u'Frames'),
            ('a', u'Body Links'),
        )
        self.links = {
            'link': ('href', set()),
            'a': ('href', set()),
            'img': ('src', set()),
            'script': ('src', set()),
            'frame': ('src', set()),             
        }
        self.titles = {}
        self.base = None
        self.count = 0
        HTMLParser.__init__(self)

    def feed(self, response, chunk):
        if response.parsed_hdrs.get('content-type', [None])[0] in link_parseable_types:
            try:
                # HTMLParser doesn't like Unicode input, so we assume UTF-8. Not great...
                HTMLParser.feed(self, unicode(chunk, "utf-8", "replace").encode("UTF-8", "ignore"))
            except Exception: # oh, well...
                pass
        
    def handle_starttag(self, tag, attrs):
        title = dict(attrs).get('title', '').strip()
        if tag in self.links.keys():
            target = dict(attrs).get(self.links[tag][0])
            if target:
                target = unicode(target, errors="ignore")
                self.count += 1
                if "#" in target:
                    target = target[:target.index('#')]
                self.links[tag][1].add(target)
                if title:
                    self.titles[target] = title
        elif tag == 'base':
            self.base = dict(attrs).get('href', None)
            return

    def error(self, message):
        return


if __name__ == "__main__":
    form = cgi.FieldStorage()
    try:
        uri = sys.argv[1]
    except IndexError:
        uri = form.getfirst("uri", "")
    print "Content-Type: text/html; charset=utf-8"
    if uri:
        print "Cache-Control: max-age=60, must-revalidate"
    else:
        print "Cache-Control: max-age=3600"
    print
    RedWebUi(uri)