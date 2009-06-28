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

# Media types to look for links in
link_parseable_types = [
    'text/html',
    'application/xhtml+xml',
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
        print red_header.__doc__ % {'uri': e(uri)} 
        sys.stdout.flush()
        self.links = HTMLLinkParser()
        if uri:
            start = time.time()
            try:
                self.red = red.ResourceExpertDroid(
                    uri, 
                    req_hdrs=req_hdrs,
                    status_cb=self.updateStatus,
                    body_procs=[self.links.feed],
                )
                self.updateStatus('Done.')
                self.elapsed = time.time() - start
                self.header_presenter = HeaderPresenter(self.red)
                print self.presentResults()
            except red.DroidError, why:
                print error_template % why
        print red_footer % {'version': red.__version__}
        sys.stdout.flush()            
    
    def presentResults(self):
        "Fill in the template with RED's results."
        result_strings = {
            'uri': e(self.red.uri),
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
            out.append(u"<li class='%s %s msg'>%s<span class='hidden_desc'>%s</span>" % 
                    (l, e(s), e(m[lang]%v), lm[lang]%v)
            )
            out.append(u"</li>")
            smsgs = [msg for msg in getattr(sr, "messages", []) if msg[1][1] in [rs.BAD]]
            if smsgs: 
                out.append(u"<ul>")
                for (s, (c, l, m, lm), sms, v) in smsgs:
                    out.append(
                        u"<li class='%s %s msg'>%s<span class='hidden_desc'>%s</span></li>" % 
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
        if media_type in link_parseable_types:
            if self.links.count > 0:
                options.append(u"<a href='#' class='link_view' title='%s'>links</a>" %
                               self.red.uri)
        if validators.has_key(media_type):
            options.append(u"<a href='%s'>validate body</a>" % 
                           validators[media_type] % self.red.uri)
        return options

    def presentLinks(self):
        "Return an HTML list of the links in the response, as RED URIs"
        base = self.links.base or self.red.uri
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
                    al = u"?uri=%s" % e(urljoin(base, target))
                    out.append(u"<li><a href='%s' title='%s'>%s</a></li>" % (
                                 al, e(target), e(title)))
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


class HTMLLinkParser(HTMLParser):
    """
    Parse the links out of an HTML document in a very forgiving way.
    
    After feed()ing is done, the links dictionary will be populated with 
    sets of links. Additionally, the titles dictionary will be a mapping of URI
    to title (if present). Finally, the base attribute will hold the HTML base
    URI, if present.
    """
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
        "Feed a given chunk of HTML data to the parser"
        if response.parsed_hdrs.get('content-type', [None])[0] in link_parseable_types:
            try:
                # HTMLParser doesn't like Unicode input, so we assume UTF-8. FIXME: look at c-t, sniff content
                if chunk.__class__.__name__ != 'unicode':
                    chunk = unicode(chunk, 'utf-8', 'ignore')
                HTMLParser.feed(self, chunk.encode('utf-8', 'ignore'))
            except: # oh, well...
                pass
        
    def handle_starttag(self, tag, attrs):
        title = dict(attrs).get('title', '').strip()
        if tag in self.links.keys():
            target = dict(attrs).get(self.links[tag][0], "")
            if target:
                target = unicode(target, 'utf-8', errors="ignore")
                self.count += 1
                if "#" in target:
                    target = target[:target.index('#')]
                self.links[tag][1].add(target)
                if title:
                    self.titles[target] = unicode(title, 'utf-8', errors="ignore")
        elif tag == 'base':
            self.base = dict(attrs).get('href', None)
            return

    def error(self, message):
        return


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