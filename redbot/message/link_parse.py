#!/usr/bin/env python

"""
Parse links from a stream of HTML data.
"""


from htmlentitydefs import entitydefs
from HTMLParser import HTMLParser

from redbot.message import headers as rh
from redbot.syntax import rfc7231

class HTMLLinkParser(HTMLParser):
    """
    Parse the links out of an HTML document in a very forgiving way.

    feed() accepts a HttpResponse object and a chunk of the document at a
    time.

    When links are found, link_procs will be called for each with the
    following arguments;
      - base (base URI for the link, in a unicode string)
      - link (URI as it appeared in document, in a unicode string)
      - tag (name of the element that contained it)
      - title (title attribute as a unicode string, if any)
    """

    link_parseable_types = [
        'text/html',
        'application/xhtml+xml',
        'application/atom+xml'
    ]

    def __init__(self, base_uri, link_procs, err=None):
        self.base = base_uri
        self.link_procs = link_procs
        self.err = err
        self.doc_enc = None
        self.link_types = {
            'link': ['href', ['stylesheet']],
            'a': ['href', None],
            'img': ['src', None],
            'script': ['src', None],
            'frame': ['src', None],
            'iframe': ['src', None],
        }
        self.errors = 0
        self.last_err_pos = None
        self.ok = True
        HTMLParser.__init__(self)

    def __getstate__(self):
        return {
            'base': self.base,
            'doc_enc': self.doc_enc,
            'errors': self.errors,
            'last_err_pos': self.last_err_pos,
            'ok': self.ok,
        }

    def feed(self, msg, chunk):
        "Feed a given chunk of HTML data to the parser"
        if not self.ok:
            return
        if msg.parsed_headers.get('content-type', [None])[0] in \
          self.link_parseable_types:
            try:
                if chunk.__class__.__name__ != 'unicode':
                    try:
                        chunk = unicode(
                            chunk, 
                            self.doc_enc or msg.character_encoding, 
                            'ignore'
                        )
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

    def handle_starttag(self, tag, attrs):
        attr_d = dict(attrs)
        title = attr_d.get('title', '').strip()
        if tag in self.link_types.keys():
            url_attr, rels = self.link_types[tag]
            if not rels or attr_d.get("rel", None) in rels:
                target = attr_d.get(url_attr, "")
                if target:
                    if "#" in target:
                        target = target[:target.index('#')]
                    for proc in self.link_procs:
                        proc(self.base, target, tag, title)
        elif tag == 'base':
            self.base = attr_d.get('href', self.base)
        elif tag == 'meta' and \
          attr_d.get('http-equiv', '').lower() == 'content-type':
            ct = attr_d.get('content', None)
            if ct:
                try:
                    media_type, params = ct.split(";", 1)
                except ValueError:
                    media_type, params = ct, ''
                media_type = media_type.lower()
                param_dict = {}
                for param in rh.split_string(
                    params, rfc7231.parameter, "\s*;\s*"
                ):
                    try:
                        a, v = param.split("=", 1)
                        param_dict[a.lower()] = rh.unquote_string(v)
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
                self.err(
                    "giving up on link parsing after %s errors" % self.errors
                )
            self.ok = False
            raise BadErrorIReallyMeanIt()
        else:
            self.last_err_pos = self.getpos()
            if self.err:
                self.err(message)

class BadErrorIReallyMeanIt(Exception):
    """See http://bugs.python.org/issue8885 for why this is necessary."""
    pass

if __name__ == "__main__":
    import sys
    from redbot.resource.fetch import RedFetcher
    uri = sys.argv[1]
    req_hdrs = [(u'Accept-Encoding', u'gzip')]
    class TestFetcher(RedFetcher):
        count = 0
        def done(self):
            pass
        @staticmethod
        def err(mesg):
            sys.stderr.write("ERROR: %s\n" % mesg)        
        @staticmethod
        def show_link(link, tag, title):
            TestFetcher.count += 1
            out = "%.3d) [%s] %s" % (TestFetcher.count, tag, link)
            print out.encode('utf-8', 'strict')
    p = HTMLLinkParser(uri, TestFetcher.show_link, TestFetcher.err)
    TestFetcher(uri, req_hdrs=req_hdrs, body_procs=[p.feed])
