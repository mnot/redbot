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

import cgi
import cPickle as pickle
import locale
import os
import pprint
import shutil
import sys
import tempfile
import time
from urlparse import urlsplit

assert sys.version_info[0] == 2 and sys.version_info[1] >= 5, "Please use Python 2.5 or greater"

import nbhttp
from redbot import droid, fetch
from redbot.formatter import find_formatter, html

### Configuration ##########################################################

# FIXME: make language configurable/dynamic
lang = "en"
charset = "utf-8"

# Where to store exceptions; set to None to disable traceback logging
logdir = 'exceptions'

# how many seconds to allow it to run for
max_runtime = 60

# Where to keep files for future reference, when users save them. None
# to disable saving.
save_dir = '/var/redbot/'

# how long to store things when users save them, in seconds.
save_time = 365 * 24 * 60 * 60

# URI root for static assets (absolute or relative, but no trailing '/')
html.static_root = 'static'

# directory containing files to append to the front page; None to disable
html.extra_dir = "extra"

### End configuration ######################################################


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
    def __init__(self, test_id, test_uri, req_hdrs, base_uri, 
        format, output_hdrs, output_body, descend=False, save=False):
        self.output_body = output_body
        self.start = time.time()
        timeout = nbhttp.schedule(max_runtime, self.timeoutError)
        if save and save_dir and test_id:
            try:
                os.utime(
                    os.path.join(save_dir, test_id),
                    (nbhttp.now(), nbhttp.now() + save_time)
                )
                output_hdrs("303 See Other", [
                    ("Location", "?id=%s" % test_id)
                ])
                output_body("Redirecting...")
            except (OSError, IOError):
                output_hdrs("500 Internal Server Error", [
                    ("Content-Type", "text/html; charset=%s" % charset), 
                ])
                # TODO: better error message (through formatter?)
                output_body(error_template % "Sorry, I couldn't save that.")
        elif test_id:
            try:
                test_id = os.path.basename(test_id)
                fd = open(os.path.join(save_dir, test_id))
                mtime = os.fstat(fd.fileno()).st_mtime
            except (OSError, IOError):
                output_hdrs("404 Not Found", [
                    ("Content-Type", "text/html; charset=%s" % charset), 
                    ("Cache-Control", "max-age=600, must-revalidate")
                ])
                # TODO: better error page (through formatter?)
                self.output_body(error_template % 
                    "I'm sorry, I can't find that saved response."
                )
                timeout.delete()
                return
            is_saved = mtime > nbhttp.now()
            ired = pickle.load(fd)
            fd.close()
            formatter = find_formatter(format, 'html', descend)(
                base_uri, ired.uri, ired.req_hdrs, lang, self.output,
                allow_save=(not is_saved), test_id=test_id
            )
            output_hdrs("200 OK", [
                ("Content-Type", "%s; charset=%s" % (
                    formatter.media_type, charset)), 
                ("Cache-Control", "max-age=3600, must-revalidate")
            ])
            formatter.start_output()
            formatter.finish_output(ired)
        elif test_uri:
            if save_dir and os.path.exists(save_dir):
                try:
                    fd, path = tempfile.mkstemp(prefix='', dir=save_dir)
                    test_id = os.path.split(path)[1]
                except (OSError, IOError):
                    # Don't try to store it. 
                    test_id = None
            else:
                test_id = None
            formatter = find_formatter(format, 'html', descend)(
                base_uri, test_uri, req_hdrs, lang, self.output,
                allow_save=save_dir, test_id=test_id
            )
            output_hdrs("200 OK", [
                ("Content-Type", "%s; charset=%s" % (
                    formatter.media_type, charset)), 
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
            try:
                tmp_file = os.fdopen(fd, 'w')
                pickle.dump(ired, tmp_file)
                tmp_file.close()
            except IOError:
                pass # we don't cry if we can't store it.
        else:  # no test_uri
            formatter = html.BaseHtmlFormatter(
                base_uri, test_uri, req_hdrs, lang, self.output)
            output_hdrs("200 OK", [
                ("Content-Type", "%s; charset=%s" % (
                    formatter.media_type, charset)
                ), 
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
    file_id = form.getfirst("id", None)
    descend = form.getfirst('descend', False)
    if os.environ.get("REQUEST_METHOD") == "POST":
        save = form.getfirst('save', False)
    else:
        save = False
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
    RedWebUi(file_id, test_uri, req_hdrs, base_uri, format, 
        output_hdrs, output_body, descend, save)

# FIXME: standalone server needs to be updated.
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