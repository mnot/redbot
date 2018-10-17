#!/usr/bin/env python

"""
HTML Formatter for REDbot.
"""


from cgi import escape as cgi_escape
import codecs
from functools import partial
import json
import operator
import os
import re
import textwrap
from typing import Any, List, Match, Tuple, Union # pylint: disable=unused-import
from urllib.parse import urljoin, quote as urlquote

from markdown import markdown

import thor
import thor.http.error as httperr

from redbot import __version__
from redbot.formatter import Formatter, html_header, relative_time, f_num
from redbot.resource import HttpResource, active_check
from redbot.message import HttpResponse
from redbot.message.headers import HeaderProcessor
from redbot.speak import Note, levels, categories # pylint: disable=unused-import

nl = "\n"
e_html = partial(cgi_escape, quote=True)


class BaseHtmlFormatter(Formatter):
    """
    Base class for HTML formatters."""
    media_type = "text/html"

    def __init__(self, *args: Any, **kw: Any) -> None:
        Formatter.__init__(self, *args, **kw)
        self.hidden_text = []  # type: List[Tuple[str, str]]
        self.start = thor.time()

    def feed(self, chunk: bytes) -> None:
        pass

    def start_output(self) -> None:
        if self.resource:
            uri = self.resource.request.uri or ""
            req_headers = self.resource.request.headers
        else:
            uri = ""
            req_headers = []
        extra_title = " <span class='save'>"
        if self.kw.get('is_saved', None):
            extra_title += " saved "
        if self.resource and self.resource.check_name != "default":
            extra_title += "%s response" % e_html(self.resource.check_name)
        extra_title += "</span>"
        if self.kw.get('is_blank', None):
            extra_body_class = "blank"
        else:
            extra_body_class = ""
        if self.kw.get('descend', False):
            descend = "&descend=True"
        else:
            descend = ''
        self.output(html_header.__doc__ % {
            'static': self.config["static_root"],
            'version': __version__,
            'html_uri': e_html(uri),
            'js_uri': e_js(uri),
            'js_req_hdrs': ", ".join(['["%s", "%s"]' % (
                e_js(n), e_js(v)) for n, v in req_headers]),
            'config': json.dumps({
                'redbot_uri': uri,
                'redbot_req_hdrs': req_headers,
                'redbot_version': __version__
            }, ensure_ascii=True).replace('<', '\\u003c'),
            'extra_js': self.format_extra('.js'),
            'test_id': self.kw.get('test_id', ""),
            'extra_title': extra_title,
            'extra_body_class': extra_body_class,
            'descend': descend
        })

    def finish_output(self) -> None:
        """
        The bottom bits.
        """
        self.output(self.format_extra())
        self.output(self.format_footer())
        self.output("</body></html>\n")

    def error_output(self, message: str) -> None:
        """
        Something bad happend.
        """
        self.output("<p class='error'>%s</p>" % message)

    def status(self, message: str) -> None:
        "Update the status bar of the browser"
        self.output("""
<script>
<!-- %3.3f
$('#red_status').text("%s");
-->
</script>
""" % (thor.time() - self.start, e_html(message)))

    def final_status(self) -> None:
#        See issue #51
#        self.status("REDbot made %(reqs)s requests in %(elapse)2.3f seconds." % {
#            'reqs': fetch.total_requests,
        self.status("")
        self.output("""
<div id="final_status">%(elapse)2.2f seconds</div>
""" % {'elapse': thor.time() - self.start})

    def format_extra(self, etype: str='.html') -> str:
        """
        Show extra content from the extra_dir, if any. MUST be UTF-8.
        Type controls the extension included; currently supported:
          - '.html': shown only on start page, after input block
          - '.js': javascript block (with script tag surrounding)
            included on every page view.
        """
        o = []
        if self.config.get("extra_dir", "") and os.path.isdir(self.config["extra_dir"]):
            extra_files = [p for p in os.listdir(self.config["extra_dir"]) if os.path.splitext(p)[1] == etype]
            for extra_file in extra_files:
                extra_path = os.path.join(self.config["extra_dir"], extra_file)
                try:
                    o.append(codecs.open(extra_path, mode='r', encoding='utf-8', # type: ignore
                                         errors='replace').read())
                except IOError as why:
                    o.append("<!-- error opening %s: %s -->" % (extra_file, why))
        return nl.join(o)

    def format_hidden_list(self) -> str:
        "return a list of hidden items to be used by the UI"
        return "<ul>" + "\n".join(["<li id='%s'>%s</li>" % (lid, text) for \
            (lid, text) in self.hidden_text]) + "</ul>"

    def format_footer(self) -> str:
        "page footer"
        return """\
<br />
<div class="footer">
<p class="navigation">
<a href="https://REDbot.org/about/">about</a> |
<script type="text/javascript">
   document.write('<a href="#help" id="help"><strong>help</strong></a> |')
</script>
<a href="https://twitter.com/redbotorg"><img class="twitterlogo" src="%(static_root)s/icon/twitter.png"/></a> |
<span class="help">Drag the bookmarklet to your bookmark bar - it makes
checking easy!</span>
<a href="javascript:location%%20=%%20'%(baseuri)s?uri='+encodeURIComponent(location);%%20void%%200"
title="drag me to your toolbar to use REDbot any time.">REDbot</a> bookmarklet
</p>
</div>

""" % {'baseuri': e_html(self.config['ui_uri']), 'static_root': self.config["static_root"]}

    def req_qs(self, link: str=None, check_name: str=None, res_format: str=None,
               use_stored: bool=True, referer: bool=True) -> str:
        """
        Format a query string to refer to another REDbot resource.

        "link" is the resource to test; it is evaluated relative to the current context
        If blank, it is the same resource.

        "check_name" is the request type to show; see active_check/__init__.py. If not specified,
        that of the current context will be used.

        "res_format" is the response format; see formatter/*.py. If not specified, HTML will be
        used.

        If "use_stored" is true, we'll refer to the test_id, rather than make a new request.

        If 'referer" is true, we'll strip any existing Referer and add our own.

        Request headers are copied over from the current context.
        """
        out = []
        uri = self.resource.request.uri
        if use_stored and self.kw.get('test_id', None):
            out.append("id=%s" % e_query_arg(self.kw['test_id']))
        else:
            out.append("uri=%s" % e_query_arg(urljoin(uri, link or "")))
        if self.resource.request.headers:
            for k, v in self.resource.request.headers:
                if referer and k.lower() == 'referer':
                    continue
                out.append("req_hdr=%s%%3A%s" % (e_query_arg(k), e_query_arg(v)))
        if referer:
            out.append("req_hdr=Referer%%3A%s" % e_query_arg(uri))
        if check_name:
            out.append("check_name=%s" % e_query_arg(check_name))
        elif self.resource.check_name != None:
            out.append("check_name=%s" % e_query_arg(self.resource.check_name))
        if res_format:
            out.append("format=%s" % e_query_arg(res_format))
        return "&".join(out)


class SingleEntryHtmlFormatter(BaseHtmlFormatter):
    """
    Present a single REDbot response in detail.
    """
    # the order of note categories to display
    note_categories = [
        categories.GENERAL,
        categories.SECURITY,
        categories.CONNECTION,
        categories.CONNEG,
        categories.CACHING,
        categories.VALIDATION,
        categories.RANGE]

    # associating categories with subrequests
    note_responses = {
        categories.CONNEG: [active_check.ConnegCheck.check_name],
        categories.VALIDATION: [active_check.ETagValidate.check_name,
                                active_check.LmValidate.check_name],
        categories.RANGE: [active_check.RangeRequest.check_name]}

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
        'text/css']

    # Validator uris, by media type
    validators = {
        'text/html': "http://validator.w3.org/check?uri=%s",
        'text/css': "http://jigsaw.w3.org/css-validator/validator?uri=%s&",
        'application/xhtml+xml': "http://validator.w3.org/check?uri=%s",
        'application/atom+xml': "http://feedvalidator.org/check.cgi?url=%s",
        'application/rss+xml': "http://feedvalidator.org/check.cgi?url=%s"}

    # HTML template for the main response body
    template = """\
    <div id="left_column">
    %(nonfinal_responses)s

    <span class="help">These are the response headers; hover over each one
    for an explanation of what it does.</span>
    <pre id='response'>%(response)s</pre>

    <p class="options">
        <span class='help'>Here, you can see the response body, a HAR document for the request, and
        when appropriate, validate the response or check its assets (such as referenced images,
        stylesheets and scripts).</span>
        %(options)s
    </p>
    </div>

    <div id="right_column">
    <div id='details'>
    <span class='help right'>These notes explain what REDbot has found
    about your URL; hover over each one for a detailed explanation.</span>
    %(notes)s
    </div>
    <span class="help">If something doesn't seem right, feel free to <a
    href="https://github.com/mnot/redbot/issues/new">file an issue</a>!</span>
    </div>

    <br />

    <div id='body'>
    %(body)s
    </div>

    %(footer)s

    <div class='hidden' id='hidden_list'>%(hidden_list)s</div>
    </body></html>
    """

    name = "html"

    def __init__(self, *args: Any, **kw: Any) -> None:
        BaseHtmlFormatter.__init__(self, *args, **kw)
        self.header_presenter = HeaderPresenter(self)

    def finish_output(self) -> None:
        self.final_status()
        if self.resource.response.complete:
            self.output(self.template % {
                'nonfinal_responses': self.format_nonfinal_responses(self.resource),
                'response': self.format_response(self.resource.response),
                'options': self.format_options(self.resource),
                'notes': nl.join([self.format_category(cat, self.resource) \
                    for cat in self.note_categories]),
                'body': self.format_body_sample(self.resource),
                'footer': self.format_footer(),
                'hidden_list': self.format_hidden_list()})
        else:
            if self.resource.response.http_error is None:
                pass # usually a global timeout...
            elif isinstance(self.resource.response.http_error, httperr.HttpError):
                if self.resource.response.http_error.detail:
                    self.error_output("%s (%s)" % (
                        self.resource.response.http_error.desc,
                        self.resource.response.http_error.detail))
                else:
                    self.error_output(self.resource.response.http_error.desc)
            else:
                raise AssertionError("Unknown incomplete response error %s" % \
                                     (self.resource.response.http_error))

    def format_nonfinal_responses(self, resource: HttpResource) -> str:
        return nl.join(["<pre class='nonfinal_response'>%s</pre>" % self.format_response(r)
                        for r in resource.nonfinal_responses])

    def format_response(self, response: HttpResponse) -> str:
        "Return the HTTP response line and headers as HTML"
        offset = 0
        headers = []
        for (name, value) in response.headers:
            offset += 1
            headers.append(self.format_header(name, value, offset))

        return "    <span class='status'>HTTP/%s %s %s</span>\n" % (
            e_html(response.version),
            e_html(response.status_code),
            e_html(response.status_phrase)) + nl.join(headers)

    def format_header(self, name: str, value: str, offset: int) -> str:
        "Return an individual HTML header as HTML"
        token_name = "header-%s" % name.lower()
        header_desc = HeaderProcessor.find_header_handler(name).description
        if header_desc and token_name not in [i[0] for i in self.hidden_text]:
            html_desc = markdown(header_desc % {'field_name': name}, output_format="html5")
            self.hidden_text.append((token_name, html_desc))
        return """\
    <span data-offset='%s' data-name='%s' class='hdr'>%s:%s</span>""" % (
        offset,
        e_html(name.lower()),
        e_html(name),
        self.header_presenter.Show(name, value))

    def format_body_sample(self, resource: HttpResource) -> str:
        """show the stored body sample"""
        if resource.response.status_code == "206":
            sample = resource.response.payload
        else:
            sample = resource.response.decoded_sample
        try:
            uni_sample = sample.decode(resource.response.character_encoding, "ignore")
        except (TypeError, LookupError):
            uni_sample = sample.decode('utf-8', 'replace')
        safe_sample = e_html(uni_sample)
        message = ""
        if hasattr(resource, "links"):
            for tag, link_set in list(resource.links.items()):
                for link in link_set:
                    try:
                        link = urljoin(resource.response.base_uri, link)
                    except ValueError:
                        pass # we're not interested in raising these upstream
                    def link_to(matchobj: Match) -> str:
                        return r"%s<a href='?%s' class='nocode'>%s</a>%s" % (
                            matchobj.group(1),
                            self.req_qs(link, use_stored=False),
                            e_html(link),
                            matchobj.group(1))
                    safe_sample = re.sub(r"('|&quot;)%s\1" % re.escape(link), link_to, safe_sample)
        if not resource.response.decoded_sample_complete:
            message = "<p class='btw'>REDbot isn't showing the whole body, because it's so big!</p>"
        return """<pre class="prettyprint">%s</pre>\n%s""" % (safe_sample, message)

    def format_category(self, category: categories, resource: HttpResource) -> str:
        """
        For a given category, return all of the non-detail
        notes in it as an HTML list.
        """
        notes = [note for note in resource.notes if note.category == category]
        if not notes:
            return nl
        out = []
        # banner, possibly with links to subreqs
        out.append("<h3>%s\n" % category.value)
        if isinstance(resource, HttpResource) and category in self.note_responses:
            for check_name in self.note_responses[category]:
                if not resource.subreqs[check_name].fetch_started:
                    continue
                out.append('<span class="req_link"> (<a href="?%s">%s response</a>' % \
                  (self.req_qs(check_name=check_name), check_name))
                smsgs = [note for note in getattr(resource.subreqs[check_name], "notes", []) if \
                  note.level in [levels.BAD] and note not in notes]
#                notes.extend(smsgs)
                if len(smsgs) == 1:
                    out.append(" - %i problem\n" % len(smsgs))
                elif smsgs:
                    out.append(" - %i problems\n" % len(smsgs))
                out.append(')</span>\n')
        out.append("</h3>\n")
        out.append("<ul>\n")
        for note in notes:
            out.append("""\
    <li class='%s note' data-subject='%s' data-name='noteid-%s'>
        <span>%s</span>
    </li>""" % (
        note.level.value,
        e_html(note.subject),
        id(note),
        e_html(note.show_summary(self.lang))))
            self.hidden_text.append(("noteid-%s" % id(note), note.show_text(self.lang)))
        out.append("</ul>\n")
        return nl.join(out)

    def format_options(self, resource: HttpResource) -> str:
        "Return things that the user can do with the URI as HTML links"
        options = []
        media_type = resource.response.parsed_headers.get('content-type', [""])[0]
        options.append(
            ("response headers: %s bytes" % f_num(resource.response.header_length),
             "how large the response headers are, including the status line"))
        options.append(("body: %s bytes" % f_num(resource.response.payload_len),
                        "how large the response body is"))
        transfer_overhead = resource.response.transfer_length - resource.response.payload_len
        if transfer_overhead > 0:
            options.append((
                "transfer overhead: %s bytes" % f_num(transfer_overhead),
                "how much using chunked encoding adds to the response size"))
        options.append(None)
        options.append(("""\
<script type="text/javascript">
   document.write("<a href='#' id='body_view' accesskey='b'>view body</a>")
</script>""",
                        "View this response body (with any gzip compression removed)"))
        if isinstance(resource, HttpResource):
            options.append(
                ("""\
        <a href="?%s" accesskey="h">view har</a>""" % self.req_qs(res_format='har'),
                 "View a HAR (HTTP ARchive, a JSON format) file for this test"))
        if not self.kw.get('is_saved', False):
            if self.kw.get('allow_save', False):
                options.append((
                    "<a href=\"#\" id='save' accesskey='s'>save</a>",
                    "Save these results for future reference"))
            if media_type in self.validators:
                options.append((
                    "<a href=\"%s\" accesskey='v'>validate body</a>" %
                    self.validators[media_type] % e_query_arg(resource.request.uri), ""))
            if hasattr(resource, "link_count") and resource.link_count > 0:
                options.append((
                    "<a href=\"?descend=True&%s\" accesskey='a'>" \
                    "check embedded</a>" % self.req_qs(use_stored=False),
                    "run REDbot on images, frames and embedded links"))
        return nl.join(
            [o and "<span class='option' title='%s'>%s</span>" % (o[1], o[0])
             or "<br>" for o in options])


class HeaderPresenter(object):
    """
    Present a HTTP header in the Web UI. By default, it will:
       - Escape HTML sequences to avoid XSS attacks
       - Wrap long lines
    However if a method is present that corresponds to the header's
    field-name, that method will be run instead to represent the value.
    """

    def __init__(self, formatter: Formatter) -> None:
        self.formatter = formatter

    def Show(self, name: str, value: str) -> str:
        """
        Return the given header name/value pair after
        presentation processing.
        """
        name = name.lower()
        name_token = name.replace('-', '_')
        if name_token[0] != "_" and hasattr(self, name_token):
            return getattr(self, name_token)(name, value)
        else:
            return self.I(e_html(value), len(name))

    def BARE_URI(self, name: str, value: str) -> str:
        "Present a bare URI header value"
        value = value.rstrip()
        svalue = value.lstrip()
        space = len(value) - len(svalue)
        return "%s<a href=\"?%s\">%s</a>" % (
            " " * space,
            self.formatter.req_qs(svalue, use_stored=False),
            self.I(e_html(svalue), len(name)))
    content_location = location = x_xrds_location = BARE_URI

    @staticmethod
    def I(value: str, sub_width: int) -> str:
        "wrap a line to fit in the header box"
        hdr_sz = 75
        sw = hdr_sz - min(hdr_sz-1, sub_width)
        tr = textwrap.TextWrapper(width=sw, subsequent_indent=" "*8, break_long_words=True)
        return tr.fill(value)



class TableHtmlFormatter(BaseHtmlFormatter):
    """
    Present a summary of multiple HttpResources.
    """
    # HTML template for the main response body
    template = """\
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


    def __init__(self, *args: Any, **kw: Any) -> None:
        BaseHtmlFormatter.__init__(self, *args, **kw)
        self.problems = [] # type: List[Note]

    def finish_output(self) -> None:
        self.final_status()
        self.output(self.template % {
            'table': self.format_tables(self.resource),
            'problems': self.format_problems(),
            'options': self.format_options(self.resource),
            'footer': self.format_footer(),
            'hidden_list': self.format_hidden_list()})

    link_order = [
        ('link', 'Head Links'),
        ('script', 'Script Links'),
        ('frame', 'Frame Links'),
        ('iframe', 'IFrame Links'),
        ('img', 'Image Links')]
    def format_tables(self, resource: HttpResource) -> str:
        out = [self.format_table_header()]
        out.append(self.format_droid(resource))
        for hdr_tag, heading in self.link_order:
            droids = [d[0] for d in resource.linked if d[1] == hdr_tag]
            if droids:
                droids.sort(key=operator.attrgetter('response.base_uri'))
                out.append(self.format_table_header(heading + " (%s)" % len(droids)))
                out += [self.format_droid(d) for d in droids]
        return nl.join(out)

    def format_droid(self, resource: HttpResource) -> str:
        out = ['<tr class="droid %s">']
        m = 50
        ct = resource.response.parsed_headers.get('content-type', [""])
        if ct[0][:6] == 'image/':
            cl = " class='preview'"
        else:
            cl = ""
        if len(resource.request.uri) > m:
            out.append("""\
    <td class="uri">
        <a href="%s" title="%s"%s>%s<span class="fade1">%s</span><span class="fade2">%s</span><span class="fade3">%s</span>
        </a>
    </td>""" % (
        "?%s" % self.req_qs(resource.request.uri, use_stored=False),
        e_html(resource.request.uri),
        cl,
        e_html(resource.request.uri[:m-2]),
        e_html(resource.request.uri[m-2]),
        e_html(resource.request.uri[m-1]),
        e_html(resource.request.uri[m])))
        else:
            out.append(
                '<td class="uri"><a href="%s" title="%s"%s>%s</a></td>' % (
                    "?%s" % self.req_qs(resource.request.uri, use_stored=False),
                    e_html(resource.request.uri),
                    cl,
                    e_html(resource.request.uri)))
        if resource.response.complete:
            if resource.response.status_code in ['301', '302', '303', '307', '308'] and \
              'location' in resource.response.parsed_headers:
                out.append(
                    '<td><a href="?descend=True&%s">%s</a></td>' % (
                        self.req_qs(resource.response.parsed_headers['location'], use_stored=False),
                        resource.response.status_code))
            elif resource.response.status_code in ['400', '404', '410']:
                out.append('<td class="bad">%s</td>' % (
                    resource.response.status_code))
            else:
                out.append('<td>%s</td>' % resource.response.status_code)
    # pconn
            out.append(self.format_size(resource.response.payload_len))
            out.append(self.format_yes_no(resource.response.store_shared))
            out.append(self.format_yes_no(resource.response.store_private))
            out.append(self.format_time(resource.response.age))
            out.append(self.format_time(resource.response.freshness_lifetime))
            out.append(self.format_yes_no(resource.ims_support))
            out.append(self.format_yes_no(resource.inm_support))
            if resource.gzip_support:
                out.append("<td>%s%%</td>" % resource.gzip_savings)
            else:
                out.append(self.format_yes_no(resource.gzip_support))
            out.append(self.format_yes_no(resource.partial_support))
            problems = [m for m in resource.notes if m.level in [levels.WARN, levels.BAD]]
            out.append("<td>")
            pr_enum = []  # type: List[int]
            for problem in problems:
                if problem not in self.problems:
                    self.problems.append(problem)
                pr_enum.append(self.problems.index(problem))
            # add the problem number to the <tr> so we can highlight
            out[0] = out[0] % " ".join(["%d" % p for p in pr_enum])
            # append the actual problem numbers to the final <td>
            for p in pr_enum:
                n = self.problems[p]
                out.append("<span class='prob_num'>" \
                           " %s <span class='hidden'>%s</span></span>" % (
                               p + 1, e_html(n.show_summary(self.lang))))
        else:
            if resource.response.http_error is None:
                err = "response incomplete"
            else:
                err = resource.response.http_error.desc or 'unknown problem'
            out.append('<td colspan="11">%s' % err)
        out.append("</td>")
        out.append('</tr>')
        return nl.join(out)

    @staticmethod
    def format_table_header(heading: str=None) -> str:
        return """
        <tr>
        <th title="The URI tested. Click to run a detailed analysis.">%s</th>
        <th title="The HTTP status code returned.">status</th>
        <th title="The size of the response body, in bytes.">size</th>
        <th title="Whether a shared (e.g., proxy) cache can store the
          response.">shared</th>
        <th title="Whether a private (e.g., browser) cache can store the
          response.">private</th>
        <th title="How long the response had been cached before REDbot got
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

    @staticmethod
    def format_time(value: float) -> str:
        if value is None:
            return '<td>-</td>'
        else:
            return '<td>%s</td>' % relative_time(value, 0, 0)

    @staticmethod
    def format_size(value: int) -> str:
        if value is None:
            return '<td>-</td>'
        else:
            return '<td>%s</td>' % f_num(value, by1024=True)

    def format_yes_no(self, value: Union[bool, None]) -> str:
        icon_tpl = '<td><img src="%s/icon/%%s" alt="%%s"/></td>' % \
            self.config["static_root"]
        if value is True:
            return icon_tpl % ("accept1.png", "yes")
        elif value is False:
            return icon_tpl % ("remove-16.png", "no")
        elif value is None:
            return icon_tpl % ("help1.png", "unknown")
        else:
            raise AssertionError('unknown value')

    def format_options(self, resource: HttpResource) -> str:
        "Return things that the user can do with the URI as HTML links"
        options = []
        media_type = resource.response.parsed_headers.get('content-type', [""])[0]
        options.append((
            "<a href='?descend=True&%s'>view har</a>" % self.req_qs(res_format="har"),
            "View a HAR (HTTP ARchive) file for this response"))
        if not self.kw.get('is_saved', False):
            if self.kw.get('allow_save', False):
                options.append((
                    "<a href='#' id='save'>save</a>",
                    "Save these results for future reference"))
        return nl.join(
            [o and "<span class='option' title='%s'>%s</span>" % (o[1], o[0])
             or "<br>" for o in options])

    def format_problems(self) -> str:
        out = ['<br /><h2>Notes</h2><ol>']
        for m in self.problems:
            out.append("""\
    <li class='%s %s note' name='msgid-%s'><span>%s</span></li>""" % (
        m.level.value,
        e_html(m.subject),
        id(m),
        e_html(m.show_summary(self.lang))))
            self.hidden_text.append(("msgid-%s" % id(m), m.show_text(self.lang)))
        out.append("</ol>\n")
        return nl.join(out)


# Escaping functions.
uri_gen_delims = r":/?#[]@"
uri_sub_delims = r"!$&'()*+,;="
def unicode_url_escape(url: str, safe: str) -> str:
    """
    URL escape a unicode string. Assume that anything already encoded
    is to be left alone.
    """
    # also include "~" because it doesn't need to be encoded,
    # but Python does anyway :/
    return urlquote(url, safe + r'%~')
e_url = partial(unicode_url_escape, safe=uri_gen_delims + uri_sub_delims)
e_authority = partial(unicode_url_escape, safe=uri_sub_delims + r"[]:@")
e_path = partial(unicode_url_escape, safe=uri_sub_delims + r":@/")
e_path_seg = partial(unicode_url_escape, safe=uri_sub_delims + r":@")
e_query = partial(unicode_url_escape, safe=uri_sub_delims + r":@/?")
e_query_arg = partial(unicode_url_escape, safe=r"!$'()*+,:@/?")
e_fragment = partial(unicode_url_escape, safe=r"!$&'()*+,;:@=/?")

def e_js(instr: str) -> str:
    """
    Make sure instr is safe for writing into a double-quoted
    JavaScript string.
    """
    if not instr:
        return ""
    instr = instr.replace('\\', '\\\\')
    instr = instr.replace('"', r'\"')
    instr = instr.replace('<', r'\x3c')
    return instr
