#!/usr/bin/env python2.5

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
    'application/atom+xml': "http://feedvalidator.org/check.cgi?url=%s",
    'application/rss+xml': "http://feedvalidator.org/check.cgi?url=%s",
}

viewable_types = [
    'text/plain',
    'text/html',
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
]

logdir = 'exceptions' # set to None to disable traceback logging

### End configuration


import cgitb; cgitb.enable(logdir=logdir)
import sys
import cgi
import gzip
import StringIO
import textwrap
from HTMLParser import HTMLParser
from urlparse import urljoin
from urllib import quote
from cgi import escape as e

from red import ResourceExpertDroid, __version__
import red_speak as rs
import red_header

# the order of message categories to display
msg_categories = [
    rs.GENERAL, rs.CONNECTION, rs.CACHING, rs.TESTS
]

template = """\
<pre>
%(response)s
</pre>

<p class="options">
	%(options)s
</p>

%(messages)s

"""

red_footer = """\

<p class="version">this is red %(version)s.</p>
<p class="navigation"> 
<a href="http://redbot.org/about/">about red</a> |
<a href="http://redbot.org/terms/">terms of use</a> | 
<a href="http://redbot.org/project">red project</a> |
<a href="javascript:location%%20=%%20'http://redbot.org/?uri='+escape(location);%%20void%%200" 
title="drag me to your toolbar to use RED any time.">red</a> bookmarklet 
</p>
</div>

<div id="long_mesg"/>


</body>
</html>
"""

error_template = """\

<p class="error">
 %s
</p>
"""

class RedWebUi(object):
    def __init__(self, test_uri):
        print red_header.__doc__ % {'uri': e(test_uri)} 
        sys.stdout.flush()
        if uri:
            try:
                self.red = ResourceExpertDroid(uri, self.updateStatus)
                self.updateStatus('Done.')
                self.header_presenter = HeaderPresenter(self.red)
                print self.presentResults()
            except AssertionError, why:
                print error_template % why
        print red_footer % {'version': __version__}
        sys.stdout.flush()            
    
    def presentResults(self):
        result_strings = {
            'uri': e(self.red.response.uri),
            'response': self.presentResponse(),
            'options': "\n".join(self.presentOptions()),
            'messages': "\n".join([self.presentCategory(cat) for cat in msg_categories]),
        }
        return template % result_strings

    def presentResponse(self):
        return \
        "    <span class='response-line'>HTTP/%s %s %s</span>\n" % (
            e(str(self.red.response.version)), 
            e(str(self.red.response.status)), 
            e(str(self.red.response.phrase))
        ) + \
        "\n".join([self.presentHeader(f,v) for (f,v) in self.red.response.headers])

    def presentHeader(self, name, value):
        token_name = name.lower()
        return "    <span class='header-%s hdr'>%s: %s</span>" % (
            e(token_name), e(name), self.header_presenter.Show(name, value))

    def presentCategory(self, category):
        messages = [msg for msg in self.red.messages if msg[1][0] == category]
        if not messages:
            return ""
        return "<h3>%s</h3>\n<ul>\n" % category \
        + "\n".join([
                    "<li class='%s %s msg'>%s<span class='hidden_desc'>%s</span></li>" % 
                    (l, e(s), e(m[lang]%v), lm[lang]%v) 
                    for (s,(c,l,m,lm),v) in messages
                    ]) \
        + "</ul>\n"

    def presentOptions(self):
        options = []
        media_type = self.red.response.parsed_hdrs.get('content-type', [None])[0]
        if media_type in viewable_types:
            options.append("<a href='%s'>view</a>" % self.red.response.uri)
        if media_type in link_parseable_types:
            if 'gzip' in self.red.response.parsed_hdrs.get('content-encoding', []):
                body = gzip.GzipFile(fileobj=StringIO.StringIO(self.red.response.body)).read()
            else:  # TODO: check for gzip errors
                body = self.red.response.body
            links = HTMLLinkParser(body)
            if links.count > 0:
                options.append("<a href='#' class='link_view' title='%s'>links</a>" %
                               self.red.response.uri)
                base = links.base or self.red.response.uri
                options.append("<span class='hidden_desc' id='link_list'>")
                options += self.presentLinks('Scripts', base, links.scripts)
                options += self.presentLinks('Images', base, links.imgs)
                options += self.presentLinks('Frames', base, links.frames)
                options += self.presentLinks('Links', base, links.links)
                options.append("</span>")
        if validators.has_key(media_type):
            options.append("<a href='%s'>validate body</a>" % 
                           validators[media_type] % self.red.response.uri)
        return options

    def presentLinks(self, name, base, links):
        if not links: return []
        out = ["<h3>%s</h3>" % name]
        out.append("<ul>")
        links = list(links)
        links.sort()
        for l in links:
            if "#" in l:
                l = l[:l.index('#')]
            if not l: continue
            al = "?uri=%s" % quote(urljoin(base, l), safe=":;/?#@+$&,")
            out.append("<li><a href='%s'>%s</a></li>" % (al, e(l)))
        out.append("</ul>")
        return out

    def updateStatus(self, message):
        print """
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
            return e(i(value, len(name)))

    def BARE_URI(self, name, value):
        return "<a href='?uri=%s'>%s</a>" % (
            e(urljoin(self.red.response.uri, value)), i(e(value), len(name)))
    content_location = \
    location = \
    x_xrds_location = \
    BARE_URI


class HTMLLinkParser(HTMLParser):
    def __init__(self, content):
        self.links = set()
        self.imgs = set()
        self.scripts = set()
        self.frames = set()
        self.base = None
        self.count = 0
        HTMLParser.__init__(self)
        try:
            self.feed(content)
        except Exception: # oh, well...
            pass
        
    def handle_starttag(self, tag, attrs):
        if tag in ['a', 'link']: # @href
            target = dict(attrs).get('href', None)
            if not target: return
            self.links.add(target)
            self.count += 1
        elif tag in ['img', 'script', 'frame', 'iframe']: # @src
            target = dict(attrs).get('src', None)
            if not target: return
            if tag == 'img': self.imgs.add(target)
            elif tag == 'script': self.scripts.add(target)
            else: self.frames.add(target)
            self.count += 1
        elif tag == 'base':
            self.base = dict(attrs).get('href', None)

    def error(self, message):
            return


if __name__ == "__main__":
    form = cgi.FieldStorage()
    try:
        uri = sys.argv[1]
    except IndexError:
        uri = form.getfirst("uri", "")
    print "Content-Type: text/html"
    if uri:
        print "Cache-Control: max-age=60, must-revalidate"
    else:
        print "Cache-Control: max-age=3600"
    print
    RedWebUi(uri)