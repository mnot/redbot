#!/usr/bin/env python

"""
A Web UI for RED, the Resource Expert Droid.
"""
import types

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

# Where to store exceptions; set to None to disable traceback logging
logdir = 'exceptions'

# any request headers that we want to *always* send.
req_hdrs = []

# how many seconds to allow it to run for
max_runtime = 60

# file containing news to display on front page
news_file = "news.html"

### End configuration ######################################################

import cgi
import operator
import os
import pprint
import sys
import textwrap
import time
from urlparse import urljoin
from cgi import escape as e

assert sys.version_info[0] == 2 and sys.version_info[1] >= 5, "Please use Python 2.5 or greater"

import link_parse
import nbhttp
import red
import red_fetcher
import red_header
import red_speak as rs
from response_analyse import relative_time

# HTML template for error bodies
error_template = u"""\

<p class="error">
 %s
</p>
"""

nl = u"\n"

class RedWebUi(object):
    """
    A Web UI for RED.

    Given a URI, run RED on it and present the results to STDOUT as HTML.
    """
    def __init__(self, uri, descend=False):
        self.descend_links = descend
        self.start = time.time()
        timeout = nbhttp.schedule(max_runtime, self.timeoutError)
        header = red_header.__doc__ % {
            'html_uri': e(uri),
            'js_uri': uri.replace('"', r'\"'),
        }
        print header.encode('utf-8', 'replace')
        self.links = {}          # {type: set(link...)}
        self.link_count = 0
        self.link_droids = []    # list of REDs
        self.base_uri = "http://%s%s%s" % ( # FIXME: only supports HTTP
          os.environ.get('HTTP_HOST'),
          os.environ.get('SCRIPT_NAME'),
          os.environ.get('PATH_INFO', '')
        )
        if uri:
            link_parser = link_parse.HTMLLinkParser(uri, self.processLink)
            self.red = red.ResourceExpertDroid(
                uri,
                req_hdrs=req_hdrs,
                status_cb=self.updateStatus,
                body_procs=[link_parser.feed],
            )
            self.updateStatus('Done.')
            if self.red.res_complete:
                if self.descend_links and self.link_count > 0:
                    print TablePresenter(self, self.red).presentResults()
                else:
                    print DetailPresenter(self, self.red).presentResults()
            else:
                print "<div id='main'>"
                if self.red.res_error['desc'] == nbhttp.error.ERR_CONNECT['desc']:
                    print error_template % "Could not connect to the server (%s)" % \
                        self.red.res_error.get('detail', "unknown")
                elif self.red.res_error['desc'] == nbhttp.error.ERR_URL['desc']:
                    print error_template % self.red.res_error.get(
                                          'detail', "RED can't fetch that URL.")
                elif self.red.res_error['desc'] == nbhttp.error.ERR_READ_TIMEOUT['desc']:
                    print error_template % self.red.res_error['desc']
                else:
                    raise AssertionError, "Unidentified incomplete response error."
                print self.presentFooter()
                print "</div>"
        else:
            print "<div id='main'>"
            print self.presentNews()
            print self.presentFooter()
            print "</div>"
        timeout.delete()
        print "</body></html>"

    def processLink(self, link, tag, title):
        "Handle a link from content"
        self.link_count += 1
        if not self.links.has_key(tag):
            self.links[tag] = set()
        if self.descend_links and tag not in ['a'] and \
          link not in self.links[tag]:
            self.link_droids.append((
                red.ResourceExpertDroid(
                    link,
                    req_hdrs=req_hdrs,
                    status_cb=self.updateStatus
                ),
                tag
            ))
        self.links[tag].add(link)

    def presentNews(self):
        if news_file:
            try:
                news = open(news_file, 'r').read()
                return news
            except IOError:
                return ""

    def presentFooter(self):
        elapsed = time.time() - self.start
        return """\
<div class="footer">
<p class="version">this is RED %(version)s.</p>
<p class="navigation">
<a href="http://REDbot.org/about/">about</a> |
<a href="http://blog.REDbot.org/">blog</a> |
<a href="http://REDbot.org/project">project</a> |
<a href="http://REDbot.org/terms/">terms of use</a> |
<a href="javascript:location%%20=%%20'%(baseuri)s?uri='+escape(location);%%20void%%200"
title="drag me to your toolbar to use RED any time.">RED</a> bookmarklet
</p>
</div>

<!--
That took %(requests)s requests and %(elapsed)2.2f seconds.
-->
""" % {
       'baseuri': self.base_uri,
       'version': red.__version__,
       'requests': red_fetcher.total_requests,
       'elapsed': elapsed
       }

    @staticmethod
    def updateStatus(message):
        "Update the status bar of the browser"
        msg = u"""
<script language="JavaScript">
<!--
window.status="%s";
-->
</script>
        """ % e(message)
        print msg.encode('utf-8', 'replace')
        sys.stdout.flush()

    def timeoutError(self):
        """ Max runtime reached."""
        print error_template % ("RED timeout.")
        print """
<!--
*** Outstanding Connections
"""
        for conn in red_fetcher.outstanding_requests:
            print "***", conn.uri.encode('utf-8', 'replace')
            pprint.pprint(conn.__dict__)
            if conn._client:
                pprint.pprint(conn._client.__dict__)
            if conn._client._tcp_conn:
                pprint.pprint(conn._client._tcp_conn.__dict__)

        print """
-->
        """
        nbhttp.stop()


class DetailPresenter(object):
    """
    Present a single RED response in detail.
    """
    # the order of message categories to display
    msg_categories = [
        rs.c.GENERAL, rs.c.CONNECTION, rs.c.CONNEG, rs.c.CACHING, rs.c.VALIDATION, rs.c.RANGE
    ]

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

    # Validator uris, by media type
    validators = {
        'text/html': "http://validator.w3.org/check?uri=%s",
        'text/css': "http://jigsaw.w3.org/css-validator/validator?uri=%s&",
        'application/xhtml+xml': "http://validator.w3.org/check?uri=%s",
        'application/atom+xml': "http://feedvalidator.org/check.cgi?url=%s",
        'application/rss+xml': "http://feedvalidator.org/check.cgi?url=%s",
    }

    # HTML template for the main response body
    template = u"""\
    <div id="main">

    <pre>%(response)s</pre>

    <p class="options">
        %(options)s
    </p>

    %(messages)s

    %(footer)s

    <div class='hidden_desc' id='link_list'>%(links)s</div>

    </div>

    <div class="mesg_sidebar" id="long_mesg"></div>

    """

    def __init__(self, ui, red):
        self.ui = ui
        self.red = red
        self.header_presenter = HeaderPresenter(self.red)

    def presentResults(self):
        "Fill in the template with RED's results."
        result_strings = {
            'response': self.presentResponse(),
            'options': self.presentOptions(),
            'messages': nl.join([self.presentCategory(cat) for cat in self.msg_categories]),
            'links': self.presentLinks(),
            'footer': self.ui.presentFooter(),
        }
        return (self.template % result_strings).encode("utf-8")

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
        "For a given category, return all of the non-detail messages in it as an HTML list"
        messages = [msg for msg in self.red.messages if msg.category == category]
        if not messages:
            return nl
        out = []
        if [msg for msg in messages if msg.level != rs.l.DETAIL]:
            out.append(u"<h3>%s</h3>\n<ul>\n" % category)
        for m in messages:
            out.append(u"<li class='%s %s msg'>%s<span class='hidden_desc'>%s</span>" %
                    (m.level, e(m.subject), e(m.summary[lang] % m.vars), m.text[lang] % m.vars)
            )
            out.append(u"</li>")
            smsgs = [msg for msg in getattr(m.subrequest, "messages", []) if msg.level in [rs.l.BAD]]
            if smsgs:
                out.append(u"<ul>")
                for sm in smsgs:
                    out.append(
                        u"<li class='%s %s msg'>%s<span class='hidden_desc'>%s</span></li>" %
                        (sm.level, e(sm.subject), e(sm.summary[lang] % sm.vars), sm.text[lang] % sm.vars)
                    )
                out.append(u"</ul>")
        out.append(u"</ul>\n")
        return nl.join(out)

    def presentOptions(self):
        "Return things that the user can do with the URI as HTML links"
        options = []
        media_type = self.red.parsed_hdrs.get('content-type', [""])[0]
        if media_type in self.viewable_types:
            if media_type[:6] == 'image/':
                cl = " class='preview'"
            else:
                cl = ""
            options.append(u"<a href='%s'%s>view</a>" % (self.red.uri, cl))
        if self.ui.link_count > 0:
            options.append(u"<a href='#link_list' class='link_view' title='%s'>view links</a>" %
                           self.red.uri)
            options.append(u"<a href='?descend=True&uri=%s'>check links</a>" %
                           self.red.uri)
        if self.validators.has_key(media_type):
            options.append(u"<a href='%s'>validate body</a>" %
                           self.validators[media_type] % self.red.uri)
        return nl.join(options)

    link_order = [
          ('link', 'Head Links'),
          ('script', 'Script Links'),
          ('frame', 'Frame Links'),
          ('iframe', 'IFrame links'),
          ('img', 'Image Links'),
          ('a', 'Body Links')
    ]
    def presentLinks(self):
        "Return an HTML list of the links in the response, as RED URIs"
        out = []
        for tag, name in self.link_order:
            link_set = self.ui.links.get(tag, set())
            if len(link_set) > 0:
                link_list = list(link_set)
                link_list.sort()
                out.append(u"<h3>%s</h3>" % name)
                out.append(u"<ul>")
                for link in link_list:
                    al = u"?uri=%s" % e(link)
                    out.append(u"<li><a href='%s'>%s</a></li>" % (
                                 al, e(link)))
                out.append(u"</ul>")
        return nl.join(out)


class HeaderPresenter(object):
    """
    Present a HTTP header in the Web UI. By default, it will:
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
            return self.I(e(value), len(name))

    def BARE_URI(self, name, value):
        "Present a bare URI header value"
        value = value.rstrip()
        svalue = value.lstrip()
        space = len(value) - len(svalue)
        return u"%s<a href='?uri=%s'>%s</a>" % ( " " * space,
            e(urljoin(self.red.uri, svalue)), self.I(e(svalue), len(name)))
    content_location = \
    location = \
    x_xrds_location = \
    BARE_URI

    @staticmethod
    def I(value, sub_width):
        "wrap a line to fit in the header box"
        hdr_sz = 65
        sw = 65 - min(hdr_sz-1, sub_width)
        tr = textwrap.TextWrapper(width=sw, subsequent_indent=" "*8, break_long_words=True)
        return tr.fill(value)


class TablePresenter(object):
    # HTML template for the main response body
    template = u"""\

    <table>
    %(table)s
    </table>

    %(problems)s

    <div class="mesg_banner" id="long_mesg"> </div>

    %(footer)s

    """
    def __init__(self, ui, red):
        self.ui = ui
        self.red = red
        self.problems = []

    def presentResults(self):
        "Fill in the template with RED's results."
        result_strings = {
            'table': self.presentTables(),
            'problems': self.presentProblems(),
            'footer': self.ui.presentFooter()
        }
        return (self.template % result_strings).encode("utf-8")

    link_order = [
          ('link', 'Head Links'),
          ('script', 'Script Links'),
          ('frame', 'Frame Links'),
          ('iframe', 'IFrame Links'),
          ('img', 'Image Links'),
    ]
    def presentTables(self):
        out = [self.presentTableHeader()]
        out.append(self.presentDroid(self.red))
        for hdr_tag, heading in self.link_order:
            droids = [d[0] for d in self.ui.link_droids if d[1] == hdr_tag]
            if droids:
                droids.sort(key=operator.attrgetter('uri'))
                out.append(self.presentTableHeader(heading + " (%s)" % len(droids)))
                out += [self.presentDroid(d) for d in droids]
        return nl.join(out)

    def presentDroid(self, red):
        out = [u'<tr class="droid %s">']
        m = 50
        if red.parsed_hdrs.get('content-type', [""])[0][:6] == 'image/':
            cl = " class='preview'"
        else:
            cl = ""
        if len(red.uri) > m:
            out.append(u"""<td class="uri"><a href="%s" title="%s"%s>
                %s<span class="fade1">%s</span><span class="fade2">%s</span><span class="fade3">%s</span>
                </a></td>""" % (
                        u"?uri=%s" % e(red.uri), e(red.uri), cl, e(red.uri[:m-2]),
                        e(red.uri[m-2]), e(red.uri[m-1]), e(red.uri[m]),
                        )
            )
        else:
            out.append(u'<td class="uri"><a href="%s" title="%s"%s>%s</a></td>' % (
                        u"?uri=%s" % e(red.uri), e(red.uri), cl, e(red.uri)))
        if red.res_complete:
            if red.res_status in ['301', '302', '303', '307'] and \
              red.parsed_hdrs.has_key('location'):
                out.append(u'<td><a href="?descend=True&uri=%s">%s</a></td>' % (
                   urljoin(red.uri, red.parsed_hdrs['location']), red.res_status))
            elif red.res_status in ['400', '404', '410']:
                out.append(u'<td class="bad">%s</td>' % red.res_status)
            else:
                out.append(u'<td>%s</td>' % red.res_status)
    # pconn
            out.append(self.presentYesNo(red.store_shared))
            out.append(self.presentYesNo(red.store_private))
            out.append(self.presentTime(red.age))
            out.append(self.presentTime(red.freshness_lifetime))
            out.append(self.presentYesNo(red.stale_serveable))
            out.append(self.presentYesNo(red.ims_support))
            out.append(self.presentYesNo(red.inm_support))
            if red.gzip_support:
                out.append(u"<td>%s%%</td>" % red.gzip_savings)
            else:
                out.append(self.presentYesNo(red.gzip_support))
            out.append(self.presentYesNo(red.partial_support))
            problems = [m for m in red.messages if m.level in [rs.l.WARN, rs.l.BAD]]
    # TODO:        problems += sum([m[2].messages for m in red.messages if m[2] != None], [])
            out.append(u"<td>")
            pr_enum = []
            for problem in problems:
                if problem not in self.problems:
                    self.problems.append(problem)
                pr_enum.append(self.problems.index(problem))
            # add the problem number to the <tr> so we can highlight appropriately
            out[0] = out[0] % u" ".join(["%d" % p for p in pr_enum])
            # append the actual problem numbers to the final <td>
            for p in pr_enum:
                m = self.problems[p]
                out.append("<span class='prob_num'> %s <span class='prob_title'>%s</span></span>" % (p + 1, e(m.summary[lang] % m.vars)))
        else:
            out.append('<td colspan="11">%s' % red.res_error['desc'])
        out.append(u"</td>")
        out.append(u'</tr>')
        return nl.join(out)

    def presentTableHeader(self, heading=None):
        return u"""
        <tr>
        <th title="The URI tested. Click to run a detailed analysis.">%s</th>
        <th title="The HTTP status code returned.">status</th>
        <th title="Whether a shared (e.g., proxy) cache can store the response.">shared<br>cache</th>
        <th title="Whether a private (e.g., browser) cache can store the response.">private<br>cache</th>
        <th title="How long the response had been cached before RED got it.">age</th>
        <th title="How long a cache can treat the response as fresh.">fresh</th>
        <th title="Whether a cache can serve the response once it becomes stale (e.g., when it can't contact the origin server).">serve<br>stale</th>
        <th title="Whether If-Modified-Since validation is supported, using Last-Modified.">IMS</th>
        <th title="Whether If-None-Match vaidation is supported, using ETags.">INM</th>
        <th title="Whether negotiation for gzip compression is supported; if so, the percent of the original size saved.">gzip</th>
        <th title="Whether partial responses are supported.">partial<br>content</th>
        <th title="Issues encountered.">problems</th>
        </tr>
        """ % (heading or "URI")

    def presentTime(self, value):
        if value is None:
            return u'<td>-</td>'
        else:
            return u'<td>%s</td>' % relative_time(value, 0, 0)

    def presentYesNo(self, value):
        if value is True:
            return u'<td><img src="icon/accept1.png" alt="yes" title="yes"/></td>'
        elif value is False:
            return u'<td><img src="icon/remove-16.png" alt="no" title="no"/></td>'
        elif value is None:
            return u'<td><img src="icon/help1.png" alt="?" title="unknown"/></td>'
        else:
            raise AssertionError, 'unknown value'

    def presentProblems(self):
        out = ['<br /><h2>Problems</h2><ol>']
        for m in self.problems:
            out.append(u"<li class='%s %s msg'>%s<span class='hidden_desc'>%s</span>" %
                    (m.level, e(m.subject), e(m.summary[lang] % m.vars), m.text[lang] % m.vars)
            )
            out.append(u"</li>")
        out.append(u"</ol>\n")
        return nl.join(out)

# adapted from cgitb.Hook
def except_handler(etype, evalue, etb):
    "Log uncaught exceptions and display a friendly error."
    import cgitb
    print cgitb.reset()
    if logdir is None:
            print error_template % """
A problem has occurred, but it probably isn't your fault.
"""
    else:
        import os
        import tempfile
        import traceback
        try:
            doc = cgitb.html((etype, evalue, etb), 5)
        except:                         # just in case something goes wrong
            doc = ''.join(traceback.format_exception(etype, evalue, etb))
        try:
            (fd, path) = tempfile.mkstemp(suffix='.html', dir=logdir)
            fh = os.fdopen(fd, 'w')
            fh.write(doc)
            fh.write("<h2>Outstanding Connections</h2>\n<pre>")
            for conn in red_fetcher.outstanding_requests:
                fh.write("*** %s\n" % conn.uri.encode('utf-8', 'replace'))
                pprint.pprint(conn.__dict__, fh)
                if conn._client:
                    pprint.pprint(conn._client.__dict__, fh)
                if conn._client._tcp_conn:
                    pprint.pprint(conn._client._tcp_conn.__dict__, fh)
            fh.write("</pre>\n")
            fh.close()
            print error_template % """
A problem has occurred, but it probably isn't your fault.
RED has remembered it, and we'll try to fix it soon."""
        except:
            print error_template % """\
A problem has occurred, but it probably isn't your fault.
RED tried to save it, but it couldn't! Oops.<br>
Please e-mail the information below to
<a href='mailto:red@redbot.org'>red@redbot.org</a>
and we'll look into it."""
            print "<pre>"
            print ''.join(traceback.format_exception(etype, evalue, etb))
            print "</pre>"
    sys.stdout.flush()

if __name__ == "__main__":
    try:
        test_uri = sys.argv[1]
        descend = True
    except IndexError:
        sys.excepthook = except_handler
        form = cgi.FieldStorage()
        test_uri = form.getfirst("uri", "").decode('utf-8', 'replace')
        descend = form.getfirst('descend', False)
    print "Content-Type: text/html; charset=utf-8"
    if test_uri:
        print "Cache-Control: max-age=60, must-revalidate"
    else:
        print "Cache-Control: max-age=3600"
    print
    RedWebUi(test_uri, descend)