#!/usr/bin/env python

"""
HTML Formatter for REDbot.
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

import codecs
import operator
import os
import re
import textwrap
import time
import urllib

from cgi import escape as e
from functools import partial
from urlparse import urljoin

import redbot.speak as rs
from redbot import defns, html_header, link_parse, droid
from redbot.formatter import Formatter
from redbot.response_analyse import relative_time, f_num

nl = u"\n"

static_root = 'static'  #FIXME: config
extra_dir = 'extra'

class BaseHtmlFormatter(Formatter):
    """
    Base class for HTML formatters."""
    media_type = "text/html"
    descend_links = False
    
    def __init__(self, uri, lang, output):
        Formatter.__init__(self, uri, lang, output)
        self.link_parser = link_parse.HTMLLinkParser(uri, self.status, self.descend_links)
        self.hidden_text = []
        self.start = time.time()

    def feed(self, red, chunk):
        self.link_parser.feed(red, chunk)

    def start_output(self):
        self.output(html_header.__doc__ % {
            'static': static_root,
            'version': droid.__version__,
            'html_uri': e(self.uri),
            'js_uri': e_js(self.uri),
# FIXME                'js_req_hdrs': ", ".join(['["%s", "%s"]' % (
#                    e_js(n), e_js(v)) for n,v in red.req_hdrs]),
            'js_req_hdrs': '',
            'extra_js': self.format_extra('.js')
        })

    def finish_output(self, red):
        """
        Default to no input. 
        """
        self.output(self.format_extra())
        self.output(self.format_footer())
        self.output("</div></body></html>\n")

 
    def status(self, message):
        "Update the status bar of the browser"
        self.output(u"""
<script>
<!-- %3.3f
window.status="%s";
-->
</script>
        """ % (time.time() - self.start, e(message)))

    def format_extra(self, type='.html'):
        """
        Show extra content from the extra_dir, if any. MUST be UTF-8.
        Type controls the extension included; currently supported:
          - '.html': shown only on start page, after input block
          - '.js': javascript block (with script tag surrounding)
            included on every page view. 
        """
        o = []
        if extra_dir and os.path.isdir(extra_dir):
            extra_files = [p for p in os.listdir(extra_dir) if os.path.splitext(p)[1] == type]
            for extra_file in extra_files:
                extra_path = os.path.join(extra_dir, extra_file)
                try:
                    o.append(codecs.open(extra_path, mode='r', encoding='utf-8', errors='replace').read())
                except IOError, why:
                    o.append("<!-- error opening %s: %s -->" % (extra_file, why))
        return nl.join(o)

    def format_hidden_list(self):
        "return a list of hidden items to be used by the UI"
        return "<ul>" + "\n".join(["<li id='%s'>%s</li>" % (id, text) for \
            (id, text) in self.hidden_text]) + "</ul>"

    def format_footer(self):
        "page footer"
        return """\
<br clear="all"/> <!-- FIXME -->
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
       'baseuri': self.link_parser.base, # FIXME: NOOOOOOOOOO
       'version': droid.__version__,
       }
       

class SingleEntryHtmlFormatter(BaseHtmlFormatter):
    """
    Present a single RED response in detail.
    """
    # the order of message categories to display
    msg_categories = [
        rs.c.GENERAL, rs.c.CONNECTION, rs.c.CONNEG, 
        rs.c.CACHING, rs.c.VALIDATION, rs.c.RANGE
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
    <div id="left_column">
    <pre id='response'>%(response)s</pre>

    <p class="options">
        %(options)s
    </p>
    </div>

    <div id="right_column">
    <div id='details'>
    %(messages)s
    </div>
    </div>

    <br clear="all"/> <!-- FIXME -->
    
    <div id='body'>
    %(body)s
    </div>
    
    %(footer)s

    <div class='hidden' id='hidden_list'>%(hidden_list)s</div>
    </body></html>
    """

    def __init__(self, uri, lang, output):
        BaseHtmlFormatter.__init__(self, uri, lang, output)
        self.body_sample = ""    # sample of the response body
        self.body_sample_size = 1024 * 128 # how big to allow the sample to be
        self.sample_seen = 0
        self.sample_complete = True

    def feed(self, red, chunk):
        self.link_parser.feed(red, chunk)
        self.store_body_sample(red, chunk)
        
    def finish_output(self, red):
        self.header_presenter = HeaderPresenter(red.uri)
        self.output(self.template % {
            'response': self.format_response(red),
            'options': self.format_options(red),
            'messages': nl.join([self.format_category(cat, red) for cat in self.msg_categories]),
            'body': self.format_body_sample(),
            'footer': self.format_footer(),
            'hidden_list': self.format_hidden_list(),
        })
        self.status("Done.")

    def format_response(self, red):
        "Return the HTTP response line and headers as HTML"
        return \
        u"    <span class='status'>HTTP/%s %s %s</span>\n" % (
            e(str(red.res_version)),
            e(str(red.res_status)),
            e(red.res_phrase)
        ) + \
        nl.join([self.format_header(f,v) for (f,v) in red.res_hdrs])

    def format_header(self, name, value):
        "Return an individual HTML header as HTML"
        token_name = "header-%s" % name.lower()
        py_name = "HDR_" + name.upper().replace("-", "_")
        if hasattr(defns, py_name) and token_name not in [i[0] for i in self.hidden_text]:
            defn = getattr(defns, py_name)[self.lang] % {
                'field_name': name,
            }
            self.hidden_text.append((token_name, defn))
        return u"    <span name='%s' class='hdr'>%s:%s</span>" % (
            e(token_name), e(name), self.header_presenter.Show(name, value))

    def format_body_sample(self):
        """show the stored body sample"""
        try:
            uni_sample = unicode(self.body_sample,
                self.link_parser.doc_enc or self.link_parser.http_enc, 'ignore')
        except LookupError:
            uni_sample = unicode(self.body_sample, 'utf-8', 'ignore')
        safe_sample = e(uni_sample)
        message = ""
        for tag, link_set in self.link_parser.links.items():
            for link in link_set:
                def link_to(matchobj):
                    return r"%s<a href='%s' class='nocode'>%s</a>%s" % (
                        matchobj.group(1),
                        u"?uri=%s" % e_query_arg(urljoin(self.link_parser.base, link)),
                        e(link),
                        matchobj.group(1)
                    )
                safe_sample = re.sub(r"(['\"])%s\1" % re.escape(link), link_to, safe_sample)
        if not self.sample_complete:
            message = "<p class='note'>RED isn't showing the whole body, because it's so big!</p>"
        return """<pre class="prettyprint">%s</pre>\n%s""" % (safe_sample, message)

    def format_category(self, category, red):
        "For a given category, return all of the non-detail messages in it as an HTML list"
        messages = [msg for msg in red.messages if msg.category == category]
        if not messages:
            return nl
        out = []
        if [msg for msg in messages]:
            out.append(u"<h3>%s</h3>\n<ul>\n" % category)
        for m in messages:
            out.append(u"<li class='%s %s msg' name='msgid-%s'><span>%s</span></li>" %
                    (m.level, e(m.subject), id(m), e(m.summary[self.lang] % m.vars))
            )
            self.hidden_text.append(("msgid-%s" % id(m), m.text[self.lang] % m.vars))
            smsgs = [msg for msg in getattr(m.subrequest, "messages", []) if msg.level in [rs.l.BAD]]
            if smsgs:
                out.append(u"<ul>")
                for sm in smsgs:
                    out.append(
                        u"<li class='%s %s msg' name='msgid-%s'><span>%s</span></li>" %
                        (sm.level, e(sm.subject), id(sm), e(sm.summary[self.lang] % sm.vars))
                    )
                    self.hidden_text.append(("msgid-%s" % id(sm), sm.text[self.lang] % sm.vars))
                out.append(u"</ul>")
        out.append(u"</ul>\n")
        return nl.join(out)

    def format_options(self, red):
        "Return things that the user can do with the URI as HTML links"
        options = []
        media_type = red.parsed_hdrs.get('content-type', [""])[0]
        options.append((u"response headers: %s bytes" % f_num(red.client.input_header_length), 
            "how large the response header block is, including the status line"))
        options.append((u"body: %s bytes" % f_num(red.res_body_len),
            "how large the response body is"))
        transfer_overhead = red.client.input_transfer_length - red.res_body_len
        if transfer_overhead > 0:
            options.append((u"transfer overhead: %s bytes" % f_num(transfer_overhead),
            "how much using chunked encoding adds to the response size"))
        options.append(None)
        options.append((u"<a href='#' id='body_view'>view body</a>", ""))
        if self.validators.has_key(media_type):
            options.append((u"<a href='%s'>validate body</a>" %
                           self.validators[media_type] % e_query_arg(red.uri), ""))
        if self.link_parser.link_count > 0:
            options.append((u"<a href='?descend=True&uri=%s'>check assets</a>" %
                           e_query_arg(red.uri), "run RED on images, frames and embedded links"))
        return nl.join([o and "<span class='option' title='%s'>%s</span>" % (o[1], o[0]) or "<br>" for o in options])

    def store_body_sample(self, red, chunk):
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



class HeaderPresenter(object):
    """
    Present a HTTP header in the Web UI. By default, it will:
       - Escape HTML sequences to avoid XSS attacks
       - Wrap long lines
    However if a method is present that corresponds to the header's
    field-name, that method will be run instead to represent the value.
    """

    def __init__(self, uri):
        self.uri = uri

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
            e_query_arg(urljoin(self.uri, svalue)), self.I(e(svalue), len(name)))
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



class TableHtmlFormatter(BaseHtmlFormatter):
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
    descend_links = True
    
    def __init__(self, uri, lang, output):
        BaseHtmlFormatter.__init__(self, uri, lang, output)
        self.problems = []

    def finish_output(self, red):
        "Fill in the template with RED's results."
        self.output(self.template % {
            'table': self.format_tables(red),
            'problems': self.format_problems(),
            'footer': self.format_footer(),
            'hidden_list': self.format_hidden_list(),
        })
        self.status("Done.")

    link_order = [
          ('link', 'Head Links'),
          ('script', 'Script Links'),
          ('frame', 'Frame Links'),
          ('iframe', 'IFrame Links'),
          ('img', 'Image Links'),
    ]
    def format_tables(self, red):
        out = [self.format_table_header()]
        out.append(self.format_droid(red))
        for hdr_tag, heading in self.link_order:
            droids = [d[0] for d in self.link_parser.link_droids if d[1] == hdr_tag]
            if droids:
                droids.sort(key=operator.attrgetter('uri'))
                out.append(self.format_table_header(heading + " (%s)" % len(droids)))
                out += [self.format_droid(d) for d in droids]
        return nl.join(out)

    def format_droid(self, red):
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
                        u"?uri=%s" % e_query_arg(red.uri), e(red.uri), cl, e(red.uri[:m-2]),
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
            out.append(self.format_yes_no(red.store_shared))
            out.append(self.format_yes_no(red.store_private))
            out.append(self.format_time(red.age))
            out.append(self.format_time(red.freshness_lifetime))
            out.append(self.format_yes_no(red.stale_serveable))
            out.append(self.format_yes_no(red.ims_support))
            out.append(self.format_yes_no(red.inm_support))
            if red.gzip_support:
                out.append(u"<td>%s%%</td>" % red.gzip_savings)
            else:
                out.append(self.format_yes_no(red.gzip_support))
            out.append(self.format_yes_no(red.partial_support))
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
                out.append("<span class='prob_num'> %s <span class='hidden'>%s</span></span>" % (p + 1, e(m.summary[self.lang] % m.vars)))
        else:
            out.append('<td colspan="11">%s' % red.res_error['desc'])
        out.append(u"</td>")
        out.append(u'</tr>')
        return nl.join(out)

    def format_table_header(self, heading=None):
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
        <th title="Whether If-None-Match validation is supported, using ETags.">INM</th>
        <th title="Whether negotiation for gzip compression is supported; if so, the percent of the original size saved.">gzip</th>
        <th title="Whether partial responses are supported.">partial<br>content</th>
        <th title="Issues encountered.">problems</th>
        </tr>
        """ % (heading or "URI")

    def format_time(self, value):
        if value is None:
            return u'<td>-</td>'
        else:
            return u'<td>%s</td>' % relative_time(value, 0, 0)

    def format_yes_no(self, value):
        if value is True:
            return u'<td><img src="static/icon/accept1.png" alt="yes" title="yes"/></td>'
        elif value is False:
            return u'<td><img src="static/icon/remove-16.png" alt="no" title="no"/></td>'
        elif value is None:
            return u'<td><img src="static/icon/help1.png" alt="?" title="unknown"/></td>'
        else:
            raise AssertionError, 'unknown value'

    def format_problems(self):
        out = ['<br /><h2>Problems</h2><ol>']
        for m in self.problems:
            out.append(u"<li class='%s %s msg' name='msgid-%s'><span>%s</span></li>" %
                    (m.level, e(m.subject), id(m), e(m.summary[self.lang] % m.vars))
            )
            self.hidden_text.append(("msgid-%s" % id(m), m.text[self.lang] % m.vars))
        out.append(u"</ol>\n")
        return nl.join(out)


# Escaping functions. 
uri_gen_delims = r":/?#[]@"
uri_sub_delims = r"!$&'()*+,;="
def unicode_url_escape(url, safe):
    "URL esape a unicode string. Assume that anything already encoded is to be left alone."
    # also include "~" because it doesn't need to be encoded, but Python does anyway :/
    return urllib.quote(url.encode('utf-8', 'replace'), safe + '%~')
e_url = partial(unicode_url_escape, safe=uri_gen_delims + uri_sub_delims)
e_authority = partial(unicode_url_escape, safe=uri_sub_delims + r"[]:@")
e_path = partial(unicode_url_escape, safe=uri_sub_delims + r":@/")
e_path_seg = partial(unicode_url_escape, safe=uri_sub_delims + r":@") 
e_query = partial(unicode_url_escape, safe=uri_sub_delims + r":@/?")
e_query_arg = partial(unicode_url_escape, safe=r"!$'()*+,;:@/?")

def e_js(instr):
    "Make sure instr is safe for writing into a double-quoted JavaScript string."
    if not instr: return ""
    instr = instr.replace('"', r'\"')
    if instr[-1] == '\\':
        instr += '\\'
    return instr
