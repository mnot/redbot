#!/usr/bin/env python

"""
Parsing links from streams of data.
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

from htmlentitydefs import entitydefs
from HTMLParser import HTMLParser
from urlparse import urljoin

from redbot import droid, response_analyse
from redbot.response_analyse import ResponseHeaderParser as RHP

class HTMLLinkParser(HTMLParser):
    """
    Parse the links out of an HTML document in a very forgiving way.

    feed() accepts a RedFetcher object (which it uses HTTP response headers
    from) and a chunk of the document at a time.

    When links are found, process_link will be called for eac with the
    following arguments;
      - link (absolute URI as a unicode string)
      - tag (name of the element that contained it)
      - title (title attribute as a unicode string, if any)
    """

    link_parseable_types = [
        'text/html',
        'application/xhtml+xml',
        'application/atom+xml'
    ]

    def __init__(self, base_uri, err, descend=False):
        self.base = base_uri
        self.err = err
        self.descend = descend
        self.links = {}          # {type: set(link...)}
        self.link_count = 0
        self.link_droids = []    # list of REDs for summary output        
        self.http_enc = 'latin-1'
        self.doc_enc = None
        self.link_types = {
            'link': 'href',
            'a': 'href',
            'img': 'src',
            'script': 'src',
            'frame': 'src',
            'iframe': 'src',
        }
        self.errors = 0
        self.last_err_pos = None
        self.ok = True
        HTMLParser.__init__(self)

    def feed(self, response, chunk):
        "Feed a given chunk of HTML data to the parser"
        if not self.ok:
            return
        if response.parsed_hdrs.get('content-type', [None])[0] in self.link_parseable_types:
            self.http_enc = response.parsed_hdrs['content-type'][1].get('charset', self.http_enc)
            try:
                if chunk.__class__.__name__ != 'unicode':
                    try:
                        chunk = unicode(chunk, self.doc_enc or self.http_enc, 'ignore')
                    except LookupError:
                        pass
                HTMLParser.feed(self, chunk)
            except BadErrorIReallyMeanIt:
                pass
            except Exception, why: # oh, well...
                if self.err:
                    self.err("feed problem: %s" % why)
                self.errors += 1
        else:
            self.ok = False

    def process_link(self, link, tag, title):
        "Handle a link from content"
        self.link_count += 1
        if not self.links.has_key(tag):
            self.links[tag] = set()
        if self.descend and tag not in ['a'] and \
          link not in self.links[tag]:
            self.link_droids.append((
                droid.ResourceExpertDroid(
                    urljoin(self.base, link),
# FIXME:                    req_hdrs=self.req_hdrs,
                    status_cb=self.err
                ),
                tag
            ))
        self.links[tag].add(link)

    def handle_starttag(self, tag, attrs):
        attr_d = dict(attrs)
        title = attr_d.get('title', '').strip()
        if tag in self.link_types.keys():
            target = attr_d.get(self.link_types[tag], "")
            if target:
                if "#" in target:
                    target = target[:target.index('#')]
                self.process_link(target, tag, title)
        elif tag == 'base':
            self.base = attr_d.get('href', self.base)
        elif tag == 'meta' and attr_d.get('http-equiv', '').lower() == 'content-type':
            ct = attr_d.get('content', None)
            if ct:
                try:
                    media_type, params = ct.split(";", 1)
                except ValueError:
                    media_type, params = ct, ''
                media_type = media_type.lower()
                param_dict = {}
                for param in RHP._splitString(params, response_analyse.PARAMETER, "\s*;\s*"):
                    try:
                        a, v = param.split("=", 1)
                        param_dict[a.lower()] = RHP._unquoteString(v)
                    except ValueError:
                        param_dict[param.lower()] = None
                self.doc_enc = param_dict.get('charset', self.doc_enc)

    def handle_charref(self, name):
        return entitydefs.get(name, '')

    def handle_entityref(self, name):
        return entitydefs.get(name, '')

    def error(self, message):
        self.errors += 1
        if self.getpos() == self.last_err_pos:
            # we're in a loop; give up.
            if self.err:
                self.err("giving up on link parsing after %s errors" % self.errors)
            self.ok = False
            raise BadErrorIReallyMeanIt()
        else:
            self.last_err_pos = self.getpos()
            if self.err:
                self.err(message)

class BadErrorIReallyMeanIt(Exception):
    """See http://bugs.python.org/issue8885 for why this is necessary."""
    pass

if "__main__" == __name__:
    import sys
    from redbot.fetch import RedFetcher
    uri = sys.argv[1]
    req_hdrs = [('Accept-Encoding', 'gzip')]
    class TestFetcher(RedFetcher):
        def done(self):
            pass
        @staticmethod
        def err(mesg):
            sys.stderr.write("ERROR: %s\n" % mesg)
    p = HTMLLinkParser(uri, TestFetcher.err)
    TestFetcher(uri, req_hdrs=req_hdrs, body_procs=[p.feed])
    print "%s links" % p.link_count
