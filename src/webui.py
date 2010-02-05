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

# Where to store exceptions; set to None to disable traceback logging
logdir = 'exceptions'

# how many seconds to allow it to run for
max_runtime = 60

# URI root for static assets (absolute or relative, but no trailing '/')
static_root = 'static'

# file containing news to display on front page; None to disable
news_file = "news.html"

### End configuration ######################################################

import operator
import os
import pprint
import re
import sys
import textwrap
import time
import urllib
from urlparse import urljoin
from cgi import escape as e

assert sys.version_info[0] == 2 and sys.version_info[1] >= 5, "Please use Python 2.5 or greater"

import link_parse
import nbhttp
import red
import red_defns
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

    Given a URI, run RED on it and present the results to output as HTML.
    If descend is true, spider the links and present a summary.
    """
    def __init__(self, test_uri, req_hdrs, base_uri, output, descend=False):
        self.base_uri = base_uri
        self.descend_links = descend
        self.output = output
        self.start = time.time()
        timeout = nbhttp.schedule(max_runtime, self.timeoutError)
        header = red_header.__doc__ % {
            'static': static_root,
            'version': red.__version__,
            'html_uri': e(test_uri),
            'js_uri': clean_js(test_uri),
            'js_req_hdrs': ", ".join(['["%s", "%s"]' % (
                clean_js(n), clean_js(v)) for n,v in req_hdrs])
        }
        self.output(header.encode('utf-8', 'replace'))
        self.links = {}          # {type: set(link...)}
        self.link_count = 0
        self.link_droids = []    # list of REDs for summary output
        self.hidden_text = []    # list of things to hide for popups
        self.body_sample = ""    # sample of the response body
        self.body_sample_size = 1024 * 32 # how big to allow the sample to be
        self.sample_seen = 0
        self.sample_complete = True
        if test_uri:
            self.link_parser = link_parse.HTMLLinkParser(test_uri, self.processLink)
            self.red = red.ResourceExpertDroid(
                test_uri,
                req_hdrs=req_hdrs,
                status_cb=self.updateStatus,
                body_procs=[self.link_parser.feed, self.storeSample],
            )
            self.updateStatus('Done.')
            if self.red.res_complete:
                if self.descend_links and self.link_count > 0:
                    self.output(TablePresenter(self, self.red).presentResults())
                else:
                    self.output(DetailPresenter(self, self.red).presentResults())
                elapsed = time.time() - self.start
                self.updateStatus("RED made %(requests)s requests in %(elapsed)2.2f seconds." % {
                   'requests': red_fetcher.total_requests,
                   'elapsed': elapsed
                });
            else:
                self.output("<div id='main'>")
                if self.red.res_error['desc'] == nbhttp.error.ERR_CONNECT['desc']:
                    self.output(error_template % "Could not connect to the server (%s)" % \
                        self.red.res_error.get('detail', "unknown"))
                elif self.red.res_error['desc'] == nbhttp.error.ERR_URL['desc']:
                    self.output(error_template % self.red.res_error.get(
                                          'detail', "RED can't fetch that URL."))
                elif self.red.res_error['desc'] == nbhttp.error.ERR_READ_TIMEOUT['desc']:
                    self.output(error_template % self.red.res_error['desc'])
                else:
                    raise AssertionError, "Unidentified incomplete response error."
                self.output(self.presentFooter())
                self.output("</div>")
        else:  # no test_uri
            self.output(self.presentNews())
            self.output(self.presentFooter())
            self.output("</div>")
        timeout.delete()
        self.output("</body></html>")

    def processLink(self, link, tag, title):
        "Handle a link from content"
        self.link_count += 1
        if not self.links.has_key(tag):
            self.links[tag] = set()
        if self.descend_links and tag not in ['a'] and \
          link not in self.links[tag]:
            self.link_droids.append((
                red.ResourceExpertDroid(
                    urljoin(self.link_parser.base, link),
                    req_hdrs=req_hdrs,
                    status_cb=self.updateStatus
                ),
                tag
            ))
        self.links[tag].add(link)

    def storeSample(self, response, chunk):
        """store the first self.sample_size bytes of the response"""
        if self.sample_seen + len(chunk) < self.body_sample_size:
            self.body_sample += chunk
            self.sample_seen += len(chunk)
        elif self.sample_seen < self.body_sample_size:
            max_chunk = self.body_sample_size - self.sample_seen
            self.body_sample += chunk[:max_chunk]
            self.sample_seen += len(chunk)
            self.sample_complete = False
        else:
            self.sample_complete = False

    def presentBody(self):
        """show the stored body sample"""
        try:
            uni_sample = unicode(self.body_sample,
                self.link_parser.doc_enc or self.link_parser.http_enc, 'ignore')
        except LookupError:
            uni_sample = self.body_sample
        safe_sample = e(uni_sample)
        message = ""
        for tag, link_set in self.links.items():
            for link in link_set:
                def link_to(matchobj):
                    return r"%s<a href='%s' class='nocode'>%s</a>%s" % (
                        matchobj.group(1),
                        u"?uri=%s" % e(urljoin(self.link_parser.base, link)),
                        e(link),
                        matchobj.group(1)
                    )
                safe_sample = re.sub(r"(['\"])%s\1" % re.escape(link), link_to, safe_sample)
        if not self.sample_complete:
            message = "<p class='note'>RED isn't showing the whole body, because it's so big!</p>"
        return """<pre class="prettyprint">%s</pre>\n%s""" % (safe_sample, message)

    def presentNews(self):
        "Show link to news, if any"
        if news_file:
            try:
                news = open(news_file, 'r').read()
                return news
            except IOError:
                return ""

    def presentHiddenList(self):
        "return a list of hidden items to be used by the UI"
        return "<ul>" + "\n".join(["<li id='%s'>%s</li>" % (id, text) for \
            (id, text) in self.hidden_text]) + "</ul>"

    def presentFooter(self):
        "page footer"
        return """\
<div class="footer">
<p class="version">this is RED %(version)s.</p>
<p class="navigation">
<a href="http://REDbot.org/about/">about</a> |
<a href="http://blog.REDbot.org/">blog</a> |
<a href="http://REDbot.org/project">project</a> |
<a href="javascript:location%%20=%%20'%(baseuri)s?uri='+escape(location);%%20void%%200"
title="drag me to your toolbar to use RED any time.">RED</a> bookmarklet
</p>
</div>

""" % {
       'baseuri': self.base_uri,
       'version': red.__version__,
       }

    def updateStatus(self, message):
        "Update the status bar of the browser"
        msg = u"""
<script>
<!--
window.status="%s";
-->
</script>
        """ % e(message)
        self.output(msg.encode('utf-8', 'replace'))
        sys.stdout.flush()

    def timeoutError(self):
        """ Max runtime reached."""
        self.output(error_template % ("RED timeout."))
        self.output("<!-- Outstanding Connections\n")
        for conn in red_fetcher.outstanding_requests:
            self.output("*** %s" % conn.uri.encode('utf-8', 'replace'))
            pprint.pprint(conn.__dict__)
            if conn._client:
                pprint.pprint(conn._client.__dict__)
            if conn._client._tcp_conn:
                pprint.pprint(conn._client._tcp_conn.__dict__)

        self.output("-->\n")
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
    <pre id='response'>%(response)s</pre>

    <p class="options">
        %(options)s
    </p>

    <div id='details'>
    %(messages)s
    </div>

    <div id='body'>
    %(body)s
    </div>

    %(footer)s

    </div>

    <div class='hidden' id='hidden_list'>%(hidden_list)s</div>

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
            'body': self.ui.presentBody(),
            'footer': self.ui.presentFooter(),
            'hidden_list': self.ui.presentHiddenList(),
        }
        return (self.template % result_strings).encode("utf-8")

    def presentResponse(self):
        "Return the HTTP response line and headers as HTML"
        return \
        u"    <span class='status'>HTTP/%s %s %s</span>\n" % (
            e(str(self.red.res_version)),
            e(str(self.red.res_status)),
            e(self.red.res_phrase)
        ) + \
        nl.join([self.presentHeader(f,v) for (f,v) in self.red.res_hdrs])

    def presentHeader(self, name, value):
        "Return an individual HTML header as HTML"
        token_name = "header-%s" % name.lower()
        py_name = "HDR_" + name.upper().replace("-", "_")
        if hasattr(red_defns, py_name) and token_name not in [i[0] for i in self.ui.hidden_text]:
            defn = getattr(red_defns, py_name)[lang] % {
                'field_name': name,
            }
            self.ui.hidden_text.append((token_name, defn))
        return u"    <span name='%s' class='hdr'>%s:%s</span>" % (
            e(token_name), e(name), self.header_presenter.Show(name, value))

    def presentCategory(self, category):
        "For a given category, return all of the non-detail messages in it as an HTML list"
        messages = [msg for msg in self.red.messages if msg.category == category]
        if not messages:
            return nl
        out = []
        if [msg for msg in messages]:
            out.append(u"<h3>%s</h3>\n<ul>\n" % category)
        for m in messages:
            out.append(u"<li class='%s %s msg' name='msgid-%s'><span>%s</span></li>" %
                    (m.level, e(m.subject), id(m), e(m.summary[lang] % m.vars))
            )
            self.ui.hidden_text.append(("msgid-%s" % id(m), m.text[lang] % m.vars))
            smsgs = [msg for msg in getattr(m.subrequest, "messages", []) if msg.level in [rs.l.BAD]]
            if smsgs:
                out.append(u"<ul>")
                for sm in smsgs:
                    out.append(
                        u"<li class='%s %s msg' name='msgid-%s'><span>%s</span></li>" %
                        (sm.level, e(sm.subject), id(sm), e(sm.summary[lang] % sm.vars))
                    )
                    self.ui.hidden_text.append(("msgid-%s" % id(sm), sm.text[lang] % sm.vars))
                out.append(u"</ul>")
        out.append(u"</ul>\n")
        return nl.join(out)

    def presentOptions(self):
        "Return things that the user can do with the URI as HTML links"
        options = []
        media_type = self.red.parsed_hdrs.get('content-type', [""])[0]
        options.append(u"<a href='#' id='body_view'>view body</a>")
        if self.validators.has_key(media_type):
            options.append(u"<a href='%s'>validate body</a>" %
                           self.validators[media_type] % urllib.quote(self.red.uri))
        if self.ui.link_count > 0:
            options.append(u"<a href='?descend=True&uri=%s'>check assets</a>" %
                           urllib.quote(self.red.uri))
        return nl.join(options)


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
        hdr_sz = 75
        sw = hdr_sz - min(hdr_sz-1, sub_width)
        tr = textwrap.TextWrapper(width=sw, subsequent_indent=" "*8, break_long_words=True)
        return tr.fill(value)


class TablePresenter(object):
    """
    Present a summary of multiple RED responses.
    """
    # HTML template for the main response body
    template = u"""\
    </div>

    <table id='summary'>
    %(table)s
    </table>

    <div id='details'>
    %(problems)s
    </div>

    <div class='hidden' id='hidden_list'>%(hidden_list)s</div>

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
            'footer': self.ui.presentFooter(),
            'hidden_list': self.ui.presentHiddenList(),
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
                out.append("<span class='prob_num'> %s <span class='hidden'>%s</span></span>" % (p + 1, e(m.summary[lang] % m.vars)))
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
            return u'<td><img src="static/icon/accept1.png" alt="yes" title="yes"/></td>'
        elif value is False:
            return u'<td><img src="static/icon/remove-16.png" alt="no" title="no"/></td>'
        elif value is None:
            return u'<td><img src="static/icon/help1.png" alt="?" title="unknown"/></td>'
        else:
            raise AssertionError, 'unknown value'

    def presentProblems(self):
        out = ['<br /><h2>Problems</h2><ol>']
        for m in self.problems:
            out.append(u"<li class='%s %s msg' name='msgid-%s'><span>%s</span></li>" %
                    (m.level, e(m.subject), id(m), e(m.summary[lang] % m.vars))
            )
            self.ui.hidden_text.append(("msgid-%s" % id(m), m.text[lang] % m.vars))
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

def clean_js(instr):
    "Make sure instr is safe for writing into a double-quoted JavaScript string."
    if not instr: return ""
    instr = instr.replace('"', r'\"')
    if instr[-1] == '\\':
        instr += '\\'
    return instr

if __name__ == "__main__":
    import cgi
    def output(o):
        print o
    try:
        test_uri = sys.argv[1]
        descend = True
    except IndexError:
        sys.excepthook = except_handler
        form = cgi.FieldStorage()
        test_uri = form.getfirst("uri", "").decode('utf-8', 'replace')
        req_hdrs = [tuple(rh.split(":", 1))
                    for rh in form.getlist("req_hdr")
                    if rh.find(":") > 0
                   ]
        descend = form.getfirst('descend', False)
    base_uri = "http://%s%s%s" % ( # FIXME: only supports HTTP
      os.environ.get('HTTP_HOST'),
      os.environ.get('SCRIPT_NAME'),
      os.environ.get('PATH_INFO', '')
    )
    output("Content-Type: text/html; charset=utf-8")
    if test_uri:
        output("Cache-Control: max-age=60, must-revalidate")
    else:
        output("Cache-Control: max-age=3600")
    print
    RedWebUi(test_uri, req_hdrs, base_uri, output, descend)