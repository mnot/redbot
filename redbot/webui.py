#!/usr/bin/env python

"""
A Web UI for RED, the Resource Expert Droid.
"""

import cPickle as pickle
import gzip
import locale
import os
import sys
import tempfile
import time
from urlparse import urlsplit
import zlib

assert sys.version_info[0] == 2 and sys.version_info[1] >= 6, \
    "Please use Python 2.6 or greater"

import thor
from redbot import __version__
from redbot.message import HttpRequest
from redbot.resource import HttpResource
from redbot.resource.robot_fetch import RobotFetcher
from redbot.formatter import find_formatter, html
from redbot.formatter.html import e_url


# HTML template for error bodies
error_template = u"""\

<p class="error">
 %s
</p>
"""

class RedWebUi(object):
    """
    A Web UI for RED.

    Given a URI, run RED on it and present the results to output as HTML.
    If descend is true, spider the links and present a summary.
    """
    def __init__(self, config, base_uri, method, query_string,
                 response_start, response_body, response_done):
        self.config = config
        self.base_uri = base_uri
        self.method = method
        self.response_start = response_start
        self.response_body = response_body
        self._response_done = response_done

        self.test_uri = None
        self.req_hdrs = None # tuple of unicode K,V
        self.format = None
        self.test_id = None
        self.check_type = None
        self.descend = None
        self.save = None
        self.parse_qs(method, query_string)

        self.start = time.time()
        self.timeout = thor.schedule(self.config.max_runtime, self.timeoutError)
        if self.save and self.config.save_dir and self.test_id:
            self.save_test()
        elif self.test_id:
            self.load_saved_test()
        elif self.test_uri:
            self.run_test()
        else:
            self.show_default()

    def response_done(self, trailers):
        if self.timeout:
            self.timeout.delete()
            self.timeout = None
        self._response_done(trailers)

    def save_test(self):
        """Save a previously run test_id."""
        try:
            # touch the save file so it isn't deleted.
            os.utime(os.path.join(self.config.save_dir, self.test_id), (
                thor.time(), thor.time() + (self.config.save_days * 24 * 60 * 60)))
            location = "?id=%s" % self.test_id
            if self.descend:
                location = "%s&descend=True" % location
            self.response_start("303", "See Other", [("Location", location)])
            self.response_body("Redirecting to the saved test page...")
        except (OSError, IOError):
            self.response_start("500", "Internal Server Error",
                                [("Content-Type", "text/html; charset=%s" % self.config.charset),])
            # TODO: better error message (through formatter?)
            self.response_body(error_template % "Sorry, I couldn't save that.")
        self.response_done([])

    def load_saved_test(self):
        """Load a saved test by test_id."""
        try:
            fd = gzip.open(os.path.join(self.config.save_dir, os.path.basename(self.test_id)))
            mtime = os.fstat(fd.fileno()).st_mtime
        except (OSError, IOError, TypeError, zlib.error):
            self.response_start("404", "Not Found", [
                ("Content-Type", "text/html; charset=%s" % self.config.charset),
                ("Cache-Control", "max-age=600, must-revalidate")])
            # TODO: better error page (through formatter?)
            self.response_body(error_template % "I'm sorry, I can't find that saved response.")
            self.response_done([])
            return
        is_saved = mtime > thor.time()
        try:
            state = pickle.load(fd)
        except (pickle.PickleError, IOError, EOFError):
            self.response_start("500", "Internal Server Error", [
                ("Content-Type", "text/html; charset=%s" % self.config.charset),
                ("Cache-Control", "max-age=600, must-revalidate")])
            self.response_body(error_template % "I'm sorry, I had a problem loading that response.")
            self.response_done([])
            return
        finally:
            fd.close()

        formatter = find_formatter(self.format, 'html', self.descend)(
            self.base_uri, state.request.uri, state.orig_req_hdrs, self.check_type, self.config.lang,
            self.output, allow_save=(not is_saved), is_saved=True,
            test_id=self.test_id)
        self.response_start("200", "OK", [
            ("Content-Type", "%s; charset=%s" % (formatter.media_type, self.config.charset)),
            ("Cache-Control", "max-age=3600, must-revalidate")])
        if self.check_type:
            state = state.subreqs.get(self.check_type, state)

        formatter.start_output()
        formatter.set_state(state)
        formatter.finish_output()
        self.response_done([])

    def run_test(self):
        """Test a URI."""
        if self.config.save_dir and os.path.exists(self.config.save_dir):
            try:
                fd, path = tempfile.mkstemp(prefix='', dir=self.config.save_dir)
                test_id = os.path.split(path)[1]
            except (OSError, IOError):
                # Don't try to store it.
                test_id = None
        else:
            test_id = None

        formatter = find_formatter(self.format, 'html', self.descend)(
            self.base_uri, self.test_uri, self.req_hdrs, self.check_type, self.config.lang,
            self.output, allow_save=test_id, is_saved=False,
            test_id=test_id, descend=self.descend)

        referers = []
        for hdr, value in self.req_hdrs:
            if hdr.lower() == 'referer':
                referers.append(value)
        referer_error = None
        if len(referers) > 1:
            referer_error = "Multiple referers not allowed."
        if referers and urlsplit(referers[0]).hostname in self.config.referer_spam_domains:
            referer_error = "Referer now allowed."
        if referer_error:
            self.response_start("403", "Forbidden", [
                ("Content-Type", "%s; charset=%s" % (formatter.media_type, self.config.charset)),
                ("Cache-Control", "max-age=360, must-revalidate")])
            formatter.start_output()
            self.output(error_template % referer_error)
            self.response_done([])
            return

        if not self.robots_precheck(self.test_uri):
            self.response_start("502", "Gateway Error", [
                ("Content-Type", "%s; charset=%s" % (formatter.media_type, self.config.charset)),
                ("Cache-Control", "max-age=60, must-revalidate")])
            formatter.start_output()
            self.output(error_template % "Forbidden by robots.txt.")
            self.response_done([])
            return

        self.response_start("200", "OK", [
            ("Content-Type", "%s; charset=%s" % (formatter.media_type, self.config.charset)),
            ("Cache-Control", "max-age=60, must-revalidate")])

        resource = HttpResource(self.test_uri, req_hdrs=self.req_hdrs, descend=self.descend)
        resource.on("status", formatter.status)
        resource.response.on("chunk", formatter.feed)
#        sys.stdout.write(pickle.dumps(resource))
        formatter.start_output()

        def done():
            if self.check_type:
                state = resource.subreqs.get(self.check_type, resource)
            else:
                state = resource
            formatter.set_state(state)
            formatter.finish_output()
            self.response_done([])
            if test_id:
                try:
                    tmp_file = gzip.open(path, 'w')
                    pickle.dump(resource, tmp_file)
                    tmp_file.close()
                except (IOError, zlib.error, pickle.PickleError):
                    pass # we don't cry if we can't store it.
#            objgraph.show_growth()
            ti = sum([i.transfer_in for i, t in resource.linked], resource.transfer_in)
            to = sum([i.transfer_out for i, t in resource.linked], resource.transfer_out)
            if ti + to > self.config.log_traffic:
                sys.stderr.write("%iK in %iK out for <%s> (descend %s)" % (
                    ti / 1024, to / 1024, e_url(self.test_uri), str(self.descend)))
        resource.on("done", done)
        resource.check()

    def show_default(self):
        """Show the default page."""
        formatter = html.BaseHtmlFormatter(
            self.base_uri, self.test_uri, self.req_hdrs, self.check_type,
            self.config.lang, self.output, is_blank=True)
        self.response_start(
            "200", "OK", [
                ("Content-Type", "%s; charset=%s" % (formatter.media_type, self.config.charset)),
                ("Cache-Control", "max-age=300")])
        formatter.start_output()
        formatter.finish_output()
        self.response_done([])

    def parse_qs(self, method, qs):
        """Given an method and a query-string dict, set attributes."""
        self.test_uri = qs.get('uri', [''])[0].decode(self.config.charset, 'replace')
        self.req_hdrs = [tuple(rh.decode(self.config.charset, 'replace').split(":", 1))
                         for rh in qs.get("req_hdr", []) if rh.find(":") > 0]
        self.format = qs.get('format', ['html'])[0]
        self.check_type = qs.get('request', [None])[0]
        self.test_id = qs.get('id', [None])[0]
        self.descend = qs.get('descend', [False])[0]
        if method == "POST":
            self.save = qs.get('save', [False])[0]
        else:
            self.save = False

    def output(self, chunk):
        self.response_body(chunk.encode(self.config.charset, 'replace'))

    def timeoutError(self):
        """ Max runtime reached."""
        self.output(error_template % ("RED timeout."))
        self.response_done([])


    def robots_precheck(self, iri):
        """
        If we have the robots.txt file available, check it to see if the
        request is permissible.

        This does not fetch robots.txt.
        """

        robot_fetcher = RobotFetcher()
        return robot_fetcher.check_robots(HttpRequest.iri_to_uri(iri), sync=True)



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
        if self.config.exception_dir is None:
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
            if self.config.debug:
                out(doc)
                return
            try:
                while etb.tb_next != None:
                    etb = etb.tb_next
                e_file = etb.tb_frame.f_code.co_filename
                e_line = etb.tb_frame.f_lineno
                ldir = os.path.join(self.config.exception_dir, os.path.split(e_file)[-1])
                if not os.path.exists(ldir):
                    os.umask(0000)
                    os.makedirs(ldir)
                (fd, path) = tempfile.mkstemp(prefix="%s_" % e_line, suffix='.html', dir=ldir)
                fh = os.fdopen(fd, 'w')
                fh.write(doc)
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
                out(''.join(traceback.format_exc()))
                out("</pre>")
        sys.exit(1) # We're in an uncertain state, so we must die horribly.

    return except_handler
