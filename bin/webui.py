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
import gzip
import locale
import os
import pprint
import shutil
import sys
import tempfile
import time
from urlparse import urlsplit
import zlib

assert sys.version_info[0] == 2 and sys.version_info[1] >= 5, \
    "Please use Python 2.5 or greater"

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
save_dir = '/var/state/redbot/'

# how long to store things when users save them, in days.
save_days = 30

# URI root for static assets (absolute or relative, but no trailing '/')
html.static_root = 'static'

# directory containing files to append to the front page; None to disable
html.extra_dir = "extra"

# show errors in the browser
debug = False

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
    def __init__(self, base_uri, method, query_string, output_hdrs):
        self.base_uri = base_uri
        self.method = method
        self.output_hdrs = output_hdrs
        
        self.output_body = None
        self.body_done = None
        self.test_uri = None
        self.req_hdrs = None
        self.format = None
        self.test_id = None
        self.descend = None
        self.save = None
        self.parse_qs(method, query_string)
        
        self.start = time.time()
        timeout = nbhttp.schedule(max_runtime, self.timeoutError)
        if self.save and save_dir and self.test_id:
            self.save_test()
        elif self.test_id:
            self.load_saved_test()
        elif self.test_uri:
            self.run_test()
        else:
            self.show_default()
        timeout.delete()

    def save_test(self):
        """Save a previously run test_id."""
        try:
            # touch the save file so it isn't deleted.
            os.utime(
                os.path.join(save_dir, self.test_id), 
                (
                    nbhttp.now(), 
                    nbhttp.now() + (save_days * 24 * 60 * 60)
                )
            )
            location = "?id=%s" % self.test_id
            if self.descend:
                location = "%s&descend=True" % location
            self.output_body, self.body_done = self.output_hdrs(
                "303 See Other", [
                ("Location", location)
            ])
            self.output_body("Redirecting to the saved test page...")
        except (OSError, IOError):
            self.output_body, self.body_done = self.output_hdrs(
                "500 Internal Server Error", [
                ("Content-Type", "text/html; charset=%s" % charset), 
            ])
            # TODO: better error message (through formatter?)
            self.output_body(
                error_template % "Sorry, I couldn't save that."
            )
            self.body_done()

    def load_saved_test(self):
        """Load a saved test by test_id."""
        try:
            fd = gzip.open(os.path.join(
                save_dir, os.path.basename(self.test_id)
            ))
            mtime = os.fstat(fd.fileno()).st_mtime
        except (OSError, IOError, zlib.error):
            self.output_body, self.body_done = self.output_hdrs(
                "404 Not Found", [
                ("Content-Type", "text/html; charset=%s" % charset), 
                ("Cache-Control", "max-age=600, must-revalidate")
            ])
            # TODO: better error page (through formatter?)
            self.output_body(error_template % 
                "I'm sorry, I can't find that saved response."
            )
            self.body_done()
            timeout.delete()
            return
        is_saved = mtime > nbhttp.now()
        try:
            ired = pickle.load(fd)
        except (pickle.PickleError, EOFError):
            self.output_body, self.body_done = self.output_hdrs(
                "500 Internal Server Error", [
                ("Content-Type", "text/html; charset=%s" % charset), 
                ("Cache-Control", "max-age=600, must-revalidate")
            ])
            # TODO: better error page (through formatter?)
            self.output_body(error_template % 
                "I'm sorry, I had a problem reading that response."
            )
            self.body_done()
            timeout.delete()
            return
        finally:
            fd.close()
        formatter = find_formatter(self.format, 'html', self.descend)(
            self.base_uri, ired.uri, ired.orig_req_hdrs, lang,
            self.output, allow_save=(not is_saved), is_saved=True,
            test_id=self.test_id
        )
        self.output_body, self.body_done = self.output_hdrs(
            "200 OK", [
            ("Content-Type", "%s; charset=%s" % (
                formatter.media_type, charset)), 
            ("Cache-Control", "max-age=3600, must-revalidate")
        ])
        formatter.start_output()
        formatter.finish_output(ired)
        self.body_done()

    def run_test(self):
        """Test a URI."""
        if save_dir and os.path.exists(save_dir):
            try:
                fd, path = tempfile.mkstemp(prefix='', dir=save_dir)
                test_id = os.path.split(path)[1]
            except (OSError, IOError):
                # Don't try to store it. 
                test_id = None
        else:
            test_id = None
        formatter = find_formatter(self.format, 'html', self.descend)(
            self.base_uri, self.test_uri, self.req_hdrs, lang,
            self.output, allow_save=test_id, is_saved=False,
            test_id=test_id, descend=self.descend
        )
        self.output_body, self.body_done = self.output_hdrs(
            "200 OK", [
            ("Content-Type", "%s; charset=%s" % (
                formatter.media_type, charset)), 
            ("Cache-Control", "max-age=60, must-revalidate")
        ])
        formatter.start_output()
        ired = droid.InspectingResourceExpertDroid(
            self.test_uri,
            req_hdrs=self.req_hdrs,
            status_cb=formatter.status,
            body_procs=[formatter.feed],
            descend=self.descend
        )
        formatter.finish_output(ired)
        if test_id:
            try:
                tmp_file = gzip.open(path, 'w')
                pickle.dump(ired, tmp_file)
                tmp_file.close()
            except (IOError, zlib.error, pickle.PickleError):
                pass # we don't cry if we can't store it.
        self.body_done()

    def show_default(self):
        """Show the default page."""
        formatter = html.BaseHtmlFormatter(
            self.base_uri, self.test_uri, self.req_hdrs, 
            lang, self.output
        )
        self.output_body, self.body_done = self.output_hdrs(
            "200 OK", [
            ("Content-Type", "%s; charset=%s" % (
                formatter.media_type, charset)
            ), 
            ("Cache-Control", "max-age=300")
        ])
        formatter.start_output()
        formatter.finish_output(None)
        self.body_done()

    def parse_qs(self, method, qs):
        """Given an method and a query-string dict, set attributes."""
        self.test_uri = qs.get('uri', [''])[0].decode(charset, 'replace')
        self.req_hdrs = [tuple(rh.split(":", 1))
                            for rh in qs.get("req_hdr", [])
                            if rh.find(":") > 0
                        ]
        self.format = qs.get('format', ['html'])[0]
        self.test_id = qs.get('id', [None])[0] 
        self.descend = qs.get('descend', [False])[0]
        if method == "POST":
            self.save = qs.get('save', [False])[0]
        else:
            self.save = False

    def output(self, chunk):
        self.output_body(chunk.encode(charset, 'replace'))
        
    def timeoutError(self):
        """ Max runtime reached."""
        self.output(error_template % ("RED timeout."))
        self.body_done()
        nbhttp.stop() # FIXME: not appropriate for standalone server




# adapted from cgitb.Hook
def except_handler_factory(out=None):
    if not out:
        out = sys.stdout.write
        
    def except_handler(etype=None, evalue=None, etb=None):
        """
        Log uncaught exceptions and display a friendly error.
        """
        if not etype or not evalue or not etb:
            etype, evalue, etb = sys.exc_info()
        import cgitb
        out(cgitb.reset())
        if logdir is None:
                out(error_template % """
    A problem has occurred, but it probably isn't your fault.
    """)
        else:
            import stat
            import traceback
            try:
                doc = cgitb.html((etype, evalue, etb), 5)
            except:                  # just in case something goes wrong
                doc = ''.join(traceback.format_exception(etype, evalue, etb))
            if debug:
                out(doc)
                return
            try:
                while etb.tb_next != None:
                    etb = etb.tb_next
                e_file = etb.tb_frame.f_code.co_filename
                e_line = etb.tb_frame.f_lineno
                ldir = os.path.join(logdir, os.path.split(e_file)[-1])
                if not os.path.exists(ldir):
                    os.umask(0000)
                    os.makedirs(ldir)
                (fd, path) = tempfile.mkstemp(
                    prefix="%s_" % e_line, suffix='.html', dir=ldir
                )
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
                out(error_template % """\
A problem has occurred, but it probably isn't your fault.
RED has remembered it, and we'll try to fix it soon.""")
            except:
                out(error_template % """\
A problem has occurred, but it probably isn't your fault.
RED tried to save it, but it couldn't! Oops.<br>
Please e-mail the information below to
<a href='mailto:red@redbot.org'>red@redbot.org</a>
and we'll look into it.""")
                out("<h3>Original Error</h3>")
                out("<pre>")
                out(''.join(traceback.format_exception(etype, evalue, etb)))
                out("</pre>")
                out("<h3>Write Error</h3>")
                out("<pre>")
                etype, value, tb = sys.exc_info()
                out(''.join(traceback.format_exception(etype, value, tb)))
                out("</pre>")
        
    return except_handler



def mod_python_handler(r):
    """Run RED as a mod_python handler."""
    from mod_python import apache
    status_lookup = {
     100: apache.HTTP_CONTINUE                     ,
     101: apache.HTTP_SWITCHING_PROTOCOLS          ,
     102: apache.HTTP_PROCESSING                   ,
     200: apache.HTTP_OK                           ,
     201: apache.HTTP_CREATED                      ,
     202: apache.HTTP_ACCEPTED                     ,
     200: apache.HTTP_OK                           ,
     200: apache.HTTP_OK                           ,
     201: apache.HTTP_CREATED                      ,
     202: apache.HTTP_ACCEPTED                     ,
     203: apache.HTTP_NON_AUTHORITATIVE            ,
     204: apache.HTTP_NO_CONTENT                   ,
     205: apache.HTTP_RESET_CONTENT                ,
     206: apache.HTTP_PARTIAL_CONTENT              ,
     207: apache.HTTP_MULTI_STATUS                 ,
     300: apache.HTTP_MULTIPLE_CHOICES             ,
     301: apache.HTTP_MOVED_PERMANENTLY            ,
     302: apache.HTTP_MOVED_TEMPORARILY            ,
     303: apache.HTTP_SEE_OTHER                    ,
     304: apache.HTTP_NOT_MODIFIED                 ,
     305: apache.HTTP_USE_PROXY                    ,
     307: apache.HTTP_TEMPORARY_REDIRECT           ,
     400: apache.HTTP_BAD_REQUEST                  ,
     401: apache.HTTP_UNAUTHORIZED                 ,
     402: apache.HTTP_PAYMENT_REQUIRED             ,
     403: apache.HTTP_FORBIDDEN                    ,
     404: apache.HTTP_NOT_FOUND                    ,
     405: apache.HTTP_METHOD_NOT_ALLOWED           ,
     406: apache.HTTP_NOT_ACCEPTABLE               ,
     407: apache.HTTP_PROXY_AUTHENTICATION_REQUIRED,
     408: apache.HTTP_REQUEST_TIME_OUT             ,
     409: apache.HTTP_CONFLICT                     ,
     410: apache.HTTP_GONE                         ,
     411: apache.HTTP_LENGTH_REQUIRED              ,
     412: apache.HTTP_PRECONDITION_FAILED          ,
     413: apache.HTTP_REQUEST_ENTITY_TOO_LARGE     ,
     414: apache.HTTP_REQUEST_URI_TOO_LARGE        ,
     415: apache.HTTP_UNSUPPORTED_MEDIA_TYPE       ,
     416: apache.HTTP_RANGE_NOT_SATISFIABLE        ,
     417: apache.HTTP_EXPECTATION_FAILED           ,
     422: apache.HTTP_UNPROCESSABLE_ENTITY         ,
     423: apache.HTTP_LOCKED                       ,
     424: apache.HTTP_FAILED_DEPENDENCY            ,
     426: apache.HTTP_UPGRADE_REQUIRED             ,
     500: apache.HTTP_INTERNAL_SERVER_ERROR        ,
     501: apache.HTTP_NOT_IMPLEMENTED              ,
     502: apache.HTTP_BAD_GATEWAY                  ,
     503: apache.HTTP_SERVICE_UNAVAILABLE          ,
     504: apache.HTTP_GATEWAY_TIME_OUT             ,
     505: apache.HTTP_VERSION_NOT_SUPPORTED        ,
     506: apache.HTTP_VARIANT_ALSO_VARIES          ,
     507: apache.HTTP_INSUFFICIENT_STORAGE         ,
     510: apache.HTTP_NOT_EXTENDED                 ,
    }    
    
    r.content_type = "text/html"
    def output_hdrs (status, hdrs):
        for hdr in hdrs:
            r.status = status_lookup.get(
                int(status), 
                apache.HTTP_INTERNAL_SERVER_ERROR
            )
            r.headers_out[hdr[0]] = hdr[1]
        return r.write, nbhttp.dummy
    query_string = cgi.parse_qs(r.args or "")
    try:
        RedWebUi(r.unparsed_uri, r.method, query_string, output_hdrs)
    except:
        except_handler_factory(r.write)()
    return apache.OK
    

def cgi_main():
    """Run RED as a CGI Script."""
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0) 
    base_uri = "http://%s%s%s" % ( # FIXME: only supports HTTP
      os.environ.get('HTTP_HOST'),
      os.environ.get('SCRIPT_NAME'),
      os.environ.get('PATH_INFO', '')
    )
    method = os.environ.get('REQUEST_METHOD')
    query_string = cgi.parse_qs(os.environ.get('QUERY_STRING', ""))
    def output_hdrs(status, res_hdrs):
        sys.stdout.write("Status: %s\n" % status)
        for k, v in res_hdrs:
            sys.stdout.write("%s: %s\n" % (k, v))
        sys.stdout.write("\n")
        return sys.stdout.write, nbhttp.dummy
    try:
        RedWebUi(base_uri, method, query_string, output_hdrs)
    except:
        except_handler_factory(sys.stdout.write)()

# FIXME: standalone server not yet working
def standalone_main(port, static_dir):
    """Run RED as a standalone Web server."""
    
    # load static files
    static_files = {}
    def static_walker(arg, dirname, names):
        for name in names:
            try:
                path = os.path.join(dirname, name)
                if os.path.isdir(path):
                    continue
                uri = os.path.relpath(path, static_dir)
                static_files["/static/%s" % uri] = open(path).read()
            except IOError:
                sys.stderr.write(
                  "* Problem loading %s\n" % path
                )
    os.path.walk(static_dir, static_walker, "")
    sys.stderr.write("* Static files loaded.\n")

    def red_handler (method, uri, req_hdrs, res_start, req_pause):
        p_uri = urlsplit(uri)
        if static_files.has_key(p_uri.path):
            res_body, res_done = res_start("200", "OK", [], nbhttp.dummy)
            res_body(static_files[p_uri.path])
            res_done(None)
        elif p_uri.path == "/":
            query_string = cgi.parse_qs(p_uri.query)

            # logging
            sys.stderr.write("%s %s %s\n" % (
                str(descend), test_uri, req_hdrs
            ))
            def output_hdrs (status, hdrs):
                code, phrase = status.split(None, 1)
                return res_start(code, phrase, hdrs, nbhttp.dummy)
        
            try:
                RedWebUi('/', method, query_string, output_hdrs)
            except:
                except_handler_factory(sys.stdout.write)()
                nbhttp.stop()
                sys.exit(1)
        else:
            res_body, res_done = res_start(
                "404", "Not Found", [], nbhttp.dummy
            )
            res_done(None)
        return nbhttp.dummy, nbhttp.dummy

    nbhttp.Server("", port, red_handler)
    
    try:
        nbhttp.run() # FIXME: catch other errors
    except KeyboardInterrupt:
        sys.stderr.write("Stopping...\n")
        nbhttp.stop()
    except:
        except_handler_factory(sys.stderr.write)()
    # FIXME: run/stop in red_fetcher
    # FIXME: logging

def standalone_monitor (port, static_dir):
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
        port = int(sys.argv[1])
        static_dir = sys.argv[2]
        sys.stderr.write("Starting standalone server...\n")
        standalone_main(port, static_dir)
#        standalone_monitor(int(port), static_dir)
    except IndexError:
        cgi_main()