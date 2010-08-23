#!/usr/bin/env python

"""
A Web UI for RED, the Resource Expert Droid.
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

### Configuration ##########################################################

# FIXME: make language configurable/dynamic
lang = "en"
charset = "utf-8"

# Where to store exceptions; set to None to disable traceback logging
logdir = 'exceptions'

# how many seconds to allow it to run for
max_runtime = 60

# URI root for static assets (absolute or relative, but no trailing '/')
static_root = 'static'

# directory containing files to append to the front page; None to disable
extra_dir = "extra"

### End configuration ######################################################

import cgi
import locale
import os
import pprint
import sys
import time
from urlparse import urlsplit

assert sys.version_info[0] == 2 and sys.version_info[1] >= 5, "Please use Python 2.5 or greater"

import nbhttp
from redbot import droid, fetch
from redbot.formatter import find_formatter
from redbot.formatter.html import BaseHtmlFormatter

# HTML template for error bodies
error_template = u"""\

<p class="error">
 %s
</p>
"""

try:
    locale.setlocale(locale.LC_ALL, locale.normalize(lang))
except:
    locale.setlocale(locale.LC_ALL, '')

class RedWebUi(object):
    """
    A Web UI for RED.

    Given a URI, run RED on it and present the results to output as HTML.
    If descend is true, spider the links and present a summary.
    """
    def __init__(self, test_uri, req_hdrs, base_uri, format, output_hdrs, output_body, descend=False):
        self.output_body = output_body
        self.start = time.time()
        timeout = nbhttp.schedule(max_runtime, self.timeoutError)
        if test_uri:
            formatter = find_formatter(format, 'html', descend)(base_uri, test_uri, req_hdrs, lang, self.output)
            output_hdrs("200 OK", [
                ("Content-Type", "%s; charset=%s" % (formatter.media_type, charset)), 
                ("Cache-Control", "max-age=60, must-revalidate")
            ])
            formatter.start_output()
            ired = droid.InspectingResourceExpertDroid(
                test_uri,
                req_hdrs=req_hdrs,
                status_cb=formatter.status,
                body_procs=[formatter.feed],
                descend=descend
            )
            formatter.finish_output(ired)
        else:  # no test_uri
            formatter = BaseHtmlFormatter(base_uri, test_uri, req_hdrs, lang, self.output)
            output_hdrs("200 OK", [
                ("Content-Type", "%s; charset=%s" % (formatter.media_type, charset)), 
                ("Cache-Control", "max-age=300")
            ])
            formatter.start_output()
            formatter.finish_output(None)
        timeout.delete()

    def output(self, chunk):
        self.output_body(chunk.encode(charset, 'replace'))

    def timeoutError(self):
        """ Max runtime reached."""
        self.output(error_template % ("RED timeout."))
        nbhttp.stop() # FIXME: not appropriate for standalone server




# adapted from cgitb.Hook
def except_handler(etype, evalue, etb):
    """
    Log uncaught exceptions and display a friendly error.
    Assumes output to STDOUT (i.e., CGI only).
    """
    import cgitb
    print cgitb.reset()
    if logdir is None:
            print error_template % """
A problem has occurred, but it probably isn't your fault.
"""
    else:
        import stat
        import tempfile
        import traceback
        try:
            doc = cgitb.html((etype, evalue, etb), 5)
        except:                         # just in case something goes wrong
            doc = ''.join(traceback.format_exception(etype, evalue, etb))
        try:
            while etb.tb_next != None:
                etb = etb.tb_next
            e_file = etb.tb_frame.f_code.co_filename
            e_line = etb.tb_frame.f_lineno
            ldir = os.path.join(logdir, os.path.split(e_file)[-1])
            if not os.path.exists(ldir):
                os.umask(0000)
                os.makedirs(ldir)
            (fd, path) = tempfile.mkstemp(prefix="%s_" % e_line, suffix='.html', dir=ldir)
            fh = os.fdopen(fd, 'w')
            fh.write(doc)
            fh.write("<h2>Outstanding Connections</h2>\n<pre>")
            for conn in fetch.outstanding_requests:
                fh.write("*** %s - %s\n" % (conn.uri, hex(id(conn))))
                pprint.pprint(conn.__dict__, fh)
                if conn.client:
                    pprint.pprint(conn.client.__dict__, fh)
                if conn.client._tcp_conn:
                    pprint.pprint(conn.client._tcp_conn.__dict__, fh)
            fh.write("</pre>\n")
            fh.close()
            os.chmod(path, stat.S_IROTH)
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
            print "<h3>Original Error</h3>"
            print "<pre>"
            print ''.join(traceback.format_exception(etype, evalue, etb))
            print "</pre>"
            print "<h3>Write Error</h3>"
            print "<pre>"
            etype, value, tb = sys.exc_info()
            print ''.join(traceback.format_exception(etype, value, tb))
            print "</pre>"
    sys.stdout.flush()

def cgi_main():
    """Run RED as a CGI Script."""
    sys.excepthook = except_handler
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0) 
    form = cgi.FieldStorage()
    test_uri = form.getfirst("uri", "").decode(charset, 'replace')
    req_hdrs = [tuple(rh.split(":", 1))
                for rh in form.getlist("req_hdr")
                if rh.find(":") > 0
               ]
    format = form.getfirst('format', 'html')
    descend = form.getfirst('descend', False)
    base_uri = "http://%s%s%s" % ( # FIXME: only supports HTTP
      os.environ.get('HTTP_HOST'),
      os.environ.get('SCRIPT_NAME'),
      os.environ.get('PATH_INFO', '')
    )
    def output_hdrs(status, res_hdrs):
        sys.stdout.write("Status: %s\n" % status)
        for k, v in res_hdrs:
            sys.stdout.write("%s: %s\n" % (k, v))
        sys.stdout.write("\n")
    def output_body(o):
        sys.stdout.write(o)
    RedWebUi(test_uri, req_hdrs, base_uri, format, output_hdrs, output_body, descend)

def standalone_main(port, static_dir):
    """Run RED as a standalone Web server."""
    static_files = {}
    for file in os.listdir(static_dir):
        sys.stderr.write("Loading %s...\n" % file)
        try:
            # FIXME: need to load icons
            static_files["/static/%s" % file] = open(os.path.join(static_dir, file)).read()
        except IOError:
            sys.stderr.write("failed.\n")
    def red_handler(method, uri, req_hdrs, res_start, req_pause):
        p_uri = urlsplit(uri)
        if static_files.has_key(p_uri.path):
            res_body, res_done = res_start("200", "OK", [], nbhttp.dummy)
            res_body(static_files[p_uri.path])
            res_done(None)
        elif p_uri.path == "/":
            query = cgi.parse_qs(p_uri.query)
            test_uri = query.get('uri', [""])[0]
            test_hdrs = [] #FIXME
            base_uri = "/"
            descend = query.has_key('descend')
            res_hdrs = [('Content-Type', 'text/html; charset=utf-8')] #FIXME: need to send proper content-type back, caching headers
            res_body, res_done = res_start("200", "OK", res_hdrs, nbhttp.dummy)
            sys.stderr.write("%s %s %s\n" % (str(descend), test_uri, test_hdrs))
            RedWebUi(test_uri, test_hdrs, base_uri, res_body, output_hdr, descend)
            res_done(None)
        else:
            res_body, res_done = res_start("404", "Not Found", [], nbhttp.dummy)
            res_done(None)
        return nbhttp.dummy, nbhttp.dummy
    nbhttp.Server("", port, red_handler)
    nbhttp.run() # FIXME: catch errors
    # FIXME: catch interrupts
    # FIXME: run/stop in red_fetcher
    # FIXME: logging

def standalone_monitor(port, static_dir):
    """Fork a process as a standalone Web server and watch it."""
    from multiprocessing import Process
    while True:
        p = Process(target=standalone_main, args=(port, static_dir))
        sys.stderr.write("* Starting RED server...\n")
        p.start()
        p.join()
        # TODO: listen to socket and drop privs

if __name__ == "__main__":
    try:
        # FIXME: usage
        port = sys.argv[1]
        static_dir = sys.argv[2]
        standalone_monitor(int(port), static_dir)
    except IndexError:
        cgi_main()