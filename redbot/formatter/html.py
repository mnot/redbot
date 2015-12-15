#!/usr/bin/env python

"""
HTML Formatter for REDbot.
"""

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2013 Mark Nottingham

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
import json
import operator
import os
import re
import textwrap
import urllib

from cgi import escape as e_html
from functools import partial
from urlparse import urljoin
e_html = partial(e_html, quote=True)

import thor
import thor.http.error as httperr

import redbot.speak as rs
from redbot import defns, __version__
from redbot.formatter import Formatter, html_header, relative_time, f_num

nl = u"\n"

# Configuration; override to change.
static_root = u'static' # where status resources are located
extra_dir = u'extra' # where extra resources are located

# TODO: make subrequests explorable

class BaseHtmlFormatter(Formatter):
    """
    Base class for HTML formatters."""
    media_type = "text/html"
    
    def __init__(self, *args, **kw):
        Formatter.__init__(self, *args, **kw)
        self.hidden_text = []
        self.start = thor.time()

    def feed(self, state, chunk):
        pass

    def start_output(self):
        extra_title = u" <span class='save'>"
        if self.kw.get('is_saved', None):
            extra_title += u" saved "
        if self.check_type:
            extra_title += "%s response" % e_html(self.check_type)
        extra_title += u"</span>"
        if self.kw.get('is_blank', None):
            extra_body_class = u"blank"
        else:
            extra_body_class = u""
        if self.kw.get('descend', False):
            descend = u"&descend=True"
        else:
            descend = u''
        self.output(html_header.__doc__ % {
            u'static': static_root,
            u'version': __version__,
            u'html_uri': e_html(self.uri),
            u'js_uri': e_js(self.uri),
            u'config': e_fragment(json.dumps({
              u'redbot_uri': self.uri,
              u'redbot_req_hdrs': self.req_hdrs,
              u'redbot_version': __version__
            }, ensure_ascii=False)),
            u'js_req_hdrs': u", ".join([u'["%s", "%s"]' % (
                e_js(n), e_js(v)) for n,v in self.req_hdrs]),
            u'extra_js': self.format_extra(u'.js'),
            u'test_id': self.kw.get('test_id', u""),
            u'extra_title': extra_title,
            u'extra_body_class': extra_body_class,
            u'descend': descend
        })

    def finish_output(self):
        """
        Default to no input. 
        """
        self.output(self.format_extra())
        self.output(self.format_footer())
        self.output(u"</body></html>\n")
        self.done()

 
    def status(self, message):
        "Update the status bar of the browser"
        self.output(u"""
<script>
<!-- %3.3f
window.status="%s";
-->
</script>
        """ % (thor.time() - self.start, e_html(message)))

    def final_status(self):
#        See issue #51
#        self.status("RED made %(reqs)s requests in %(elapse)2.3f seconds." % {
#            'reqs': fetch.total_requests,
        self.status(u"RED finished in %(elapse)2.3f seconds." % {
           u'elapse': thor.time() - self.start
        })

    def format_extra(self, etype='.html'):
        """
        Show extra content from the extra_dir, if any. MUST be UTF-8.
        Type controls the extension included; currently supported:
          - '.html': shown only on start page, after input block
          - '.js': javascript block (with script tag surrounding)
            included on every page view. 
        """
        o = []
        if extra_dir and os.path.isdir(extra_dir):
            extra_files = [
                p for p in os.listdir(extra_dir) if \
                os.path.splitext(p)[1] == etype
            ]
            for extra_file in extra_files:
                extra_path = os.path.join(extra_dir, extra_file)
                try:
                    o.append(
                        codecs.open(extra_path, mode='r', 
                            encoding='utf-8', errors='replace').read()
                    )
                except IOError, why:
                    o.append("<!-- error opening %s: %s -->" % (
                        extra_file, why))
        return nl.join(o)

    def format_hidden_list(self):
        "return a list of hidden items to be used by the UI"
        return u"<ul>" + u"\n".join([u"<li id='%s'>%s</li>" % (lid, text) for \
            (lid, text) in self.hidden_text]) + u"</ul>"

    def format_footer(self):
        "page footer"
        return u"""\
<br />
<div class="footer">
<p class="version">this is RED %(version)s.</p>
<p class="navigation">
<a href="https://REDbot.org/about/">about</a> |
<script type="text/javascript">
   document.write('<a href="#help" id="help"><strong>help</strong></a> |')
</script>
<a href="https://REDbot.org/project">project</a> |
<span class="help">Drag the bookmarklet to your bookmark bar - it makes
checking easy!</span>
<a href="javascript:location%%20=%%20'%(baseuri)s?uri='+encodeURIComponent(location);%%20void%%200"
title="drag me to your toolbar to use RED any time.">RED</a> bookmarklet
</p>
</div>

""" % {
       'baseuri': e_html(self.ui_uri),
       'version': __version__,
       }

    def req_qs(self, link=None, check_type=None, res_format=None, use_stored=True, referer=True):
        """
        Format a query string to refer to another RED resource.
        
        "link" is the resource to test; it is evaluated relative to the current context
        If blank, it is the same resource.
        
        "check_type" is the request type to show; see active_check/__init__.py. If not specified, 
        that of the current context will be used.
        
        "res_format" is the response format; see formatter/*.py. If not specified, HTML will be
        used.
        
        If "use_stored" is true, we'll refer to the test_id, rather than make a new request.
        
        If 'referer" is true, we'll strip any existing Referer and add our own.
        
        Request headers are copied over from the current context.
        """
        out = []
        if use_stored and self.kw.get('test_id', None):
            out.append(u"id=%s" % e_query_arg(self.kw['test_id']))
        else:
            out.append(u"uri=%s" % e_query_arg(urljoin(self.uri, link or "")))
        if self.req_hdrs:
            for k,v in self.req_hdrs:
                if referer and k.lower() == 'referer': continue
                out.append(u"req_hdr=%s%%3A%s" % (
                    e_query_arg(k), 
                    e_query_arg(v)
                ))
        if referer:
            out.append(u"req_hdr=Referer%%3A%s" % e_query_arg(self.uri))
        if check_type:
            out.append(u"request=%s" % e_query_arg(check_type))
        elif self.check_type != None:
            out.append(u"request=%s" % e_query_arg(self.check_type))
        if res_format:
            out.append(u"format=%s" % e_query_arg(res_format))
        return "&".join(out)
       

class SingleEntryHtmlFormatter(BaseHtmlFormatter):
    """
    Present a single RED response in detail.
    """
    # the order of note categories to display
    note_categories = [
        rs.c.GENERAL, 
        rs.c.SECURITY, 
        rs.c.CONNECTION, 
        rs.c.CONNEG, 
        rs.c.CACHING, 
        rs.c.VALIDATION, 
        rs.c.RANGE
    ]

    # associating categories with subrequests
    note_responses = {
        rs.c.CONNEG: ["Identity"],
        rs.c.VALIDATION: ['If-None-Match', 'If-Modified-Since'],
        rs.c.RANGE: ['Range']
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
    <span class="help">These are the response headers; hover over each one
    for an explanation of what it does.</span>
    <pre id='response'>%(response)s</pre>

    <p class="options">
        <span class='help'>Here, you can see the response body, a HAR document for the request, and when appropriate, validate the response or check its assets (such as referenced images, stylesheets and scripts).</span>
        %(options)s
    </p>
    </div>

    <div id="right_column">
    <div id='details'>
    <span class='help right'>These notes explain what REDbot has found
    about your URL; hover over each one for a detailed explanation.</span>
    %(notes)s
    </div>
    </div>

    <br />
    
    <div id='body'>
    %(body)s
    </div>
    
    %(footer)s

    <div class='hidden' id='hidden_list'>%(hidden_list)s</div>
    </body></html>
    """

    error_template = u"""\

    <p class="error">
     %s
    </p>
    """    
    
    name = "html"

    def __init__(self, *args, **kw):
        BaseHtmlFormatter.__init__(self, *args, **kw)
        
    def finish_output(self):
        self.final_status()
        if self.state.response.complete:
            self.header_presenter = HeaderPresenter(self)
            self.output(self.template % {
                'response': self.format_response(self.state),
                'options': self.format_options(self.state),
                'notes': nl.join([self.format_category(cat, self.state) \
                    for cat in self.note_categories]),
                'body': self.format_body_sample(self.state),
                'footer': self.format_footer(),
                'hidden_list': self.format_hidden_list(),
            })
        else:
            if self.state.response.http_error == None:
                pass # usually a global timeout...
            elif isinstance(self.state.response.http_error, httperr.HttpError):
                if self.state.response.http_error.detail:
                    self.output(self.error_template % u"%s (%s)" % (
                        self.state.response.http_error.desc,
                        self.state.response.http_error.detail
                    )
                )
                else:
                    self.output(self.error_template % (
                      self.state.response.http_error.desc
                    ))
            else:
                raise AssertionError, \
                  "Unknown incomplete response error %s" % (
                     self.state.response.http_error
                )
        self.done()

    def format_response(self, state):
        "Return the HTTP response line and headers as HTML"
        offset = 0
        headers = []
        for (name, value) in state.response.headers:
            offset += 1
            headers.append(self.format_header(name, value, offset))
            
        return \
        u"    <span class='status'>HTTP/%s %s %s</span>\n" % (
            e_html(state.response.version),
            e_html(state.response.status_code),
            e_html(state.response.status_phrase)
        ) + \
        nl.join(headers)

    def format_header(self, name, value, offset):
        "Return an individual HTML header as HTML"
        token_name = "header-%s" % name.lower()
        py_name = "HDR_" + name.upper().replace("-", "_").encode('ascii', 'ignore')
        if hasattr(defns, py_name) and token_name not in \
          [i[0] for i in self.hidden_text]:
            defn = getattr(defns, py_name)[self.lang] % {
                'field_name': name,
            }
            self.hidden_text.append((token_name, defn))
        return u"""\
    <span data-offset='%s' data-name='%s' class='hdr'>%s:%s</span>""" % (
            offset, 
            e_html(name.lower()), 
            e_html(name), 
            self.header_presenter.Show(name, value)
        )

    def format_body_sample(self, state):
        """show the stored body sample"""
        try:
            uni_sample = unicode(state.response.decoded_sample,
                                 state.response.character_encoding, 
                                 'ignore'
            )
        except LookupError:
            uni_sample = unicode(state.response.decoded_sample, 'utf-8', 'ignore')
        safe_sample = e_html(uni_sample)
        message = ""
        if hasattr(state, "links"):
            for tag, link_set in state.links.items():
                for link in link_set:
                    def link_to(matchobj):
                        try:
                            qlink = urljoin(state.response.base_uri, link)
                        except ValueError, why:
                            pass # TODO: pass link problem upstream?
                                 # e.g., ValueError("Invalid IPv6 URL")
                        return r"%s<a href='?%s' class='nocode'>%s</a>%s" % (
                            matchobj.group(1),
                            self.req_qs(link),
                            e_html(link),
                            matchobj.group(1)
                        )
                    safe_sample = re.sub(r"(['\"])%s\1" % \
                        re.escape(link), link_to, safe_sample)
        if not state.response.decoded_sample_complete:
            message = \
"<p class='btw'>RED isn't showing the whole body, because it's so big!</p>"
        return """<pre class="prettyprint">%s</pre>\n%s""" % (
            safe_sample, message)

    def format_category(self, category, state):
        """
        For a given category, return all of the non-detail 
        notes in it as an HTML list.
        """
        notes = [note for note in state.notes if note.category == category]
        if not notes:
            return nl
        out = []
        out.append(u"<h3>%s\n" % category)
        if category in self.note_responses.keys():
            for check_type in self.note_responses[category]:
                if not state.subreqs.has_key(check_type): continue
                out.append(u'<span class="req_link"> (<a href="?%s">%s response</a>' % \
                  (self.req_qs(check_type=check_type), check_type)
                )
                smsgs = [note for note in getattr(state.subreqs[check_type], "notes", []) if \
                  note.level in [rs.l.BAD]]
                if len(smsgs) == 1:
                    out.append(" - %i warning\n" % len(smsgs))
                elif smsgs:
                    out.append(" - %i warnings\n" % len(smsgs))                    
                out.append(u')</span>\n')
        out.append(u"</h3>\n")
        out.append(u"<ul>\n")
        for note in notes:
            out.append(
             u"""\
    <li class='%s note' data-subject='%s' data-name='noteid-%s'>
        <span>%s</span>
    </li>"""
            % (
                note.level, 
                e_html(note.subject), 
                id(note), 
                e_html(note.show_summary(self.lang)),
             )
            )
            self.hidden_text.append(
                ("noteid-%s" % id(note), note.show_text(self.lang))
            )
        out.append(u"</ul>\n")
        return nl.join(out)

    def format_options(self, state):
        "Return things that the user can do with the URI as HTML links"
        options = []
        media_type = state.response.parsed_headers.get('content-type', [""])[0]
        options.append(
            (u"response headers: %s bytes" % \
             f_num(state.response.header_length), 
             u"how large the response headers are, including the status line"
            )
        )
        options.append((u"body: %s bytes" % f_num(state.response.payload_len),
            u"how large the response body is"))
        transfer_overhead = state.response.transfer_length - \
            state.response.payload_len
        if transfer_overhead > 0:
            options.append(
                (
                 u"transfer overhead: %s bytes" % f_num(transfer_overhead),
                 u"how much using chunked encoding adds to the response size"
                )
            )
        options.append(None)
        options.append((u"""\
<script type="text/javascript">
   document.write("<a href='#' id='body_view' accesskey='b'>view body</a>")
</script>""", 
    "View this response body (with any gzip compression removed)"
        ))
        options.append(
            (u"""\
    <a href='?%s' accesskey='h'>view har</a>""" % self.req_qs(res_format='har'), 
            "View a HAR (HTTP ARchive, a JSON format) file for this response"
        ))
        if not self.kw.get('is_saved', False):
            if self.kw.get('allow_save', False):
                options.append((
                    u"<a href='#' id='save' accesskey='s'>save</a>", 
                    "Save these results for future reference"
                ))
            if self.validators.has_key(media_type):
                options.append(
                    (
                    u"<a href='%s' accesskey='v'>validate body</a>" %
                        self.validators[media_type] % 
                        e_query_arg(state.request.uri), 
                     ""
                    )
                )
            if hasattr(state, "link_count") and state.link_count > 0:
                options.append((
                    u"<a href='?descend=True&%s' accesskey='a'>" \
                    u"check embedded</a>" % self.req_qs(use_stored=False), 
                    "run RED on images, frames and embedded links"
                ))
        return nl.join(
            [o and u"<span class='option' title='%s'>%s</span>" % (o[1], o[0])
             or u"<br>" for o in options]
        )


class HeaderPresenter(object):
    """
    Present a HTTP header in the Web UI. By default, it will:
       - Escape HTML sequences to avoid XSS attacks
       - Wrap long lines
    However if a method is present that corresponds to the header's
    field-name, that method will be run instead to represent the value.
    """

    def __init__(self, formatter):
        self.formatter = formatter

    def Show(self, name, value):
        """
        Return the given header name/value pair after 
        presentation processing.
        """
        name = name.lower()
        name_token = name.replace('-', '_').encode('ascii', 'ignore')
        if name_token[0] != "_" and hasattr(self, name_token):
            return getattr(self, name_token)(name, value)
        else:
            return self.I(e_html(value), len(name))

    def BARE_URI(self, name, value):
        "Present a bare URI header value"
        value = value.rstrip()
        svalue = value.lstrip()
        space = len(value) - len(svalue)
        return u"%s<a href='?%s'>%s</a>" % (
            " " * space,
            self.formatter.req_qs(svalue, use_stored=False),
            self.I(e_html(svalue), len(name))
        )
    content_location = \
    location = \
    x_xrds_location = \
    BARE_URI

    @staticmethod
    def I(value, sub_width):
        "wrap a line to fit in the header box"
        hdr_sz = 75
        sw = hdr_sz - min(hdr_sz-1, sub_width)
        tr = textwrap.TextWrapper(
            width=sw, subsequent_indent=" "*8, break_long_words=True
        )
        return tr.fill(value)



class TableHtmlFormatter(BaseHtmlFormatter):
    """
    Present a summary of multiple RED responses.
    """
    # HTML template for the main response body
    template = u"""\
    <table id='summary'>
    %(table)s
    </table>
    <p class="options">
        %(options)s
    </p>

    <div id='details'>
    %(problems)s
    </div>

    <div class='hidden' id='hidden_list'>%(hidden_list)s</div>

    %(footer)s

    </body></html>
    """
    can_multiple = True
    name = "html"

    
    def __init__(self, *args, **kw):
        BaseHtmlFormatter.__init__(self, *args, **kw)
        self.problems = []

    def finish_output(self):
        self.final_status()
        self.output(self.template % {
            'table': self.format_tables(self.state),
            'problems': self.format_problems(),
            'options': self.format_options(self.state),
            'footer': self.format_footer(),
            'hidden_list': self.format_hidden_list(),
        })
        self.done()

    link_order = [
          ('link', u'Head Links'),
          ('script', u'Script Links'),
          ('frame', u'Frame Links'),
          ('iframe', u'IFrame Links'),
          ('img', u'Image Links'),
    ]
    def format_tables(self, state):
        out = [self.format_table_header()]
        out.append(self.format_droid(state))
        for hdr_tag, heading in self.link_order:
            droids = [d[0] for d in state.linked if d[1] == hdr_tag]
            if droids:
                droids.sort(key=operator.attrgetter('response.base_uri'))
                out.append(
                    self.format_table_header(heading + u" (%s)" % len(droids))
                )
                out += [self.format_droid(d) for d in droids]
        return nl.join(out)

    def format_droid(self, state):
        out = [u'<tr class="droid %s">']
        m = 50
        ct = state.response.parsed_headers.get('content-type', [""])
        if ct[0][:6] == 'image/':
            cl = u" class='preview'"
        else:
            cl = u""
        if len(state.request.uri) > m:
            out.append(u"""\
    <td class="uri">
        <a href="%s" title="%s"%s>%s<span class="fade1">%s</span><span class="fade2">%s</span><span class="fade3">%s</span>
        </a>
    </td>""" % (
                    u"?%s" % self.req_qs(state.request.uri, use_stored=False), 
                    e_html(state.request.uri), 
                    cl, 
                    e_html(state.request.uri[:m-2]),
                    e_html(state.request.uri[m-2]), 
                    e_html(state.request.uri[m-1]), 
                    e_html(state.request.uri[m]),
                )
            )
        else:
            out.append(
                u'<td class="uri"><a href="%s" title="%s"%s>%s</a></td>' % (
                    u"?%s" % self.req_qs(state.request.uri, use_stored=False), 
                    e_html(state.request.uri), 
                    cl, 
                    e_html(state.request.uri)
                )
            )
        if state.response.complete:
            if state.response.status_code in ['301', '302', '303', '307', '308'] and \
              state.response.parsed_headers.has_key('location'):
                out.append(
                    u'<td><a href="?descend=True&%s">%s</a></td>' % (
                        self.req_qs(state.response.parsed_headers['location'], use_stored=False),
                        state.response.status_code
                    )
                )
            elif state.response.status_code in ['400', '404', '410']:
                out.append(u'<td class="bad">%s</td>' % (
                    state.response.status_code
                ))
            else:
                out.append(u'<td>%s</td>' % state.response.status_code)
    # pconn
            out.append(self.format_size(state.response.payload_len))
            out.append(self.format_yes_no(state.response.store_shared))
            out.append(self.format_yes_no(state.response.store_private))
            out.append(self.format_time(state.response.age))
            out.append(self.format_time(state.response.freshness_lifetime))
            out.append(self.format_yes_no(state.ims_support))
            out.append(self.format_yes_no(state.inm_support))
            if state.gzip_support:
                out.append(u"<td>%s%%</td>" % state.gzip_savings)
            else:
                out.append(self.format_yes_no(state.gzip_support))
            out.append(self.format_yes_no(state.partial_support))
            problems = [m for m in state.notes if \
                m.level in [rs.l.WARN, rs.l.BAD]]
    # TODO:        problems += sum([m[2].notes for m in state.notes if  
    # m[2] != None], [])
            out.append(u"<td>")
            pr_enum = []
            for problem in problems:
                if problem not in self.problems:
                    self.problems.append(problem)
                pr_enum.append(self.problems.index(problem))
            # add the problem number to the <tr> so we can highlight
            out[0] = out[0] % u" ".join([u"%d" % p for p in pr_enum])
            # append the actual problem numbers to the final <td>
            for p in pr_enum:
                m = self.problems[p]
                out.append(u"<span class='prob_num'>" \
                           u" %s <span class='hidden'>%s</span></span>" % (
                    p + 1, e_html(m.show_summary(self.lang))
                    )
                )
        else:
            if state.response.http_error == None:
                err = u"response incomplete"
            else:
                err = state.response.http_error.desc or u'unknown problem'
            out.append(u'<td colspan="11">%s' % err)
        out.append(u"</td>")
        out.append(u'</tr>')
        return nl.join(out)

    def format_table_header(self, heading=None):
        return u"""
        <tr>
        <th title="The URI tested. Click to run a detailed analysis.">%s</th>
        <th title="The HTTP status code returned.">status</th>
        <th title="The size of the response body, in bytes.">size</th>
        <th title="Whether a shared (e.g., proxy) cache can store the
          response.">shared</th>
        <th title="Whether a private (e.g., browser) cache can store the
          response.">private</th>
        <th title="How long the response had been cached before RED got
          it.">age</th>
        <th title="How long a cache can treat the response as
          fresh.">freshness</th>
        <th title="Whether If-Modified-Since validation is supported, using
          Last-Modified.">IMS</th>
        <th title="Whether If-None-Match validation is supported, using
          ETags.">INM</th>
        <th title="Whether negotiation for gzip compression is supported; if
          so, the percent of the original size saved.">gzip</th>
        <th title="Whether partial responses are supported.">partial</th>
        <th title="Issues encountered.">notes</th>
        </tr>
        """ % (heading or "URI")

    def format_time(self, value):
        if value is None:
            return u'<td>-</td>'
        else:
            return u'<td>%s</td>' % relative_time(value, 0, 0)

    def format_size(self, value):
        if value is None:
            return u'<td>-</td>'
        else:
            return u'<td>%s</td>' % f_num(value, by1024=True)

    def format_yes_no(self, value):
        icon_tpl = u'<td><img src="%s/icon/%%s" alt="%%s"/></td>' % \
            static_root
        if value is True:
            return icon_tpl % (u"accept1.png", u"yes")
        elif value is False:
            return icon_tpl % (u"remove-16.png", u"no")
        elif value is None:
            return icon_tpl % (u"help1.png", u"unknown")
        else:
            raise AssertionError, 'unknown value'

    def format_options(self, state):
        "Return things that the user can do with the URI as HTML links"
        options = []
        media_type = state.response.parsed_headers.get('content-type', [""])[0]
        options.append((
          u"<a href='?descend=True&%s'>view har</a>" % self.req_qs(res_format="har"),
          u"View a HAR (HTTP ARchive) file for this response"
        ))
        if not self.kw.get('is_saved', False):
            if self.kw.get('allow_save', False):
                options.append((
                    u"<a href='#' id='save'>save</a>", 
                    u"Save these results for future reference"
                ))
        return nl.join(
            [o and u"<span class='option' title='%s'>%s</span>" % (o[1], o[0])
             or u"<br>" for o in options]
        )

    def format_problems(self):
        out = [u'<br /><h2>Notes</h2><ol>']
        for m in self.problems:
            out.append(u"""\
    <li class='%s %s note' name='msgid-%s'><span>%s</span></li>""" % (
                    m.level, 
                    e_html(m.subject), 
                    id(m), 
                    e_html(m.summary[self.lang] % m.vars)
                )
            )
            self.hidden_text.append(
                (u"msgid-%s" % id(m), m.text[self.lang] % m.vars)
            )
        out.append(u"</ol>\n")
        return nl.join(out)


# Escaping functions. 
uri_gen_delims = r":/?#[]@"
uri_sub_delims = r"!$&'()*+,;="
def unicode_url_escape(url, safe):
    """
    URL esape a unicode string. Assume that anything already encoded 
    is to be left alone.
    """
    # also include "~" because it doesn't need to be encoded, 
    # but Python does anyway :/
    return urllib.quote(url.encode('utf-8', 'replace'), safe + '%~')
e_url = partial(unicode_url_escape, safe=uri_gen_delims + uri_sub_delims)
e_authority = partial(unicode_url_escape, safe=uri_sub_delims + r"[]:@")
e_path = partial(unicode_url_escape, safe=uri_sub_delims + r":@/")
e_path_seg = partial(unicode_url_escape, safe=uri_sub_delims + r":@") 
e_query = partial(unicode_url_escape, safe=uri_sub_delims + r":@/?")
e_query_arg = partial(unicode_url_escape, safe=r"!$'()*+,:@/?")
e_fragment = partial(unicode_url_escape, safe=r"!$&'()*+,;:@=/?")

def e_js(instr):
    """
    Make sure instr is safe for writing into a double-quoted 
    JavaScript string.
    """
    if not instr: 
        return u""
    instr = instr.replace(u'\\', u'\\\\')
    instr = instr.replace(u'"', ur'\"')
    instr = instr.replace(u'<', ur'\x3c')
    return instr
