#!/usr/bin/env python

"""
Parse links from a stream of HTML data.
"""

from html.parser import HTMLParser
from typing import Any, Callable, Dict, List, Tuple

from redbot.message import headers, HttpMessage
from redbot.syntax import rfc7231


class HTMLLinkParser(HTMLParser):
    """
    Parse the links out of an HTML document in a very forgiving way.

    feed() accepts a HttpMessage object and a chunk of the document at a
    time.

    When links are found, link_procs will be called for each with the
    following arguments;
      - base (base URI for the link, in a unicode string)
      - link (URI as it appeared in document, in a unicode string)
      - tag (name of the element that contained it)
      - title (title attribute as a unicode string, if any)
    """

    link_parseable_types = [
        "text/html",
        "application/xhtml+xml",
        "application/atom+xml",
    ]

    def __init__(
        self,
        message: HttpMessage,
        link_procs: List[Callable[[str, str, str, str], None]],
        err: Callable[[str], int] = None,
    ) -> None:
        self.message = message
        self.link_procs = link_procs
        self.err = err
        self.link_types = {
            "link": ("href", ["stylesheet"]),
            "a": ("href", None),
            "img": ("src", None),
            "script": ("src", None),
            "frame": ("src", None),
            "iframe": ("src", None),
        }  # type: Dict[str, Tuple[str, List[str]]]
        self.errors = 0
        self.last_err_pos = None  # type: int
        self.ok = True
        HTMLParser.__init__(self)

    def __getstate__(self) -> Dict[str, Any]:
        return {"errors": self.errors, "last_err_pos": self.last_err_pos, "ok": self.ok}

    def feed(self, chunk: str) -> None:
        "Feed a given chunk of bytes to the parser"
        if not self.ok:
            return
        if (
            self.message.parsed_headers.get("content-type", [None])[0]
            in self.link_parseable_types
        ):
            try:
                if not isinstance(chunk, str):
                    try:
                        chunk = chunk.decode(self.message.character_encoding, "ignore")
                    except LookupError:
                        pass
                HTMLParser.feed(self, chunk)
            except BadErrorIReallyMeanIt:
                pass
            except Exception as why:  # oh, well...
                if self.err:
                    self.err("feed problem: %s" % why)
                self.errors += 1
        else:
            self.ok = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        attr_d = dict(attrs)
        title = attr_d.get("title", "").strip()
        if tag in self.link_types:
            url_attr, rels = self.link_types[tag]
            if not rels or attr_d.get("rel", None) in rels:
                target = attr_d.get(url_attr, "")
                if target:
                    if "#" in target:
                        target = target[: target.index("#")]
                    for proc in self.link_procs:
                        proc(self.message.base_uri, target, tag, title)
        elif tag == "base":
            self.message.base_uri = attr_d.get("href", self.message.base_uri)
        elif tag == "meta" and attr_d.get("http-equiv", "").lower() == "content-type":
            ct = attr_d.get("content", None)
            if ct:
                try:
                    media_type, params = ct.split(";", 1)
                except ValueError:
                    media_type, params = ct, ""
                media_type = media_type.lower()
                param_dict = {}
                for param in headers.split_string(
                    params, rfc7231.parameter, r"\s*;\s*"
                ):
                    try:
                        a, v = param.split("=", 1)
                        param_dict[a.lower()] = headers.unquote_string(v)
                    except ValueError:
                        param_dict[param.lower()] = None
                self.message.character_encoding = param_dict.get(
                    "charset", self.message.character_encoding
                )

    def error(self, message: str) -> None:
        self.errors += 1
        if self.getpos() == self.last_err_pos:
            # we're in a loop; give up.
            if self.err:
                self.err("giving up on link parsing after %s errors" % self.errors)
            self.ok = False
            raise BadErrorIReallyMeanIt()
        else:
            self.last_err_pos, offset = self.getpos()
            if self.err:
                self.err(message)


class BadErrorIReallyMeanIt(Exception):
    """See http://bugs.python.org/issue8885 for why this is necessary."""

    pass


if __name__ == "__main__":
    import sys
    from configparser import ConfigParser
    import thor
    from redbot.resource.fetch import RedFetcher  # pylint: disable=ungrouped-imports

    T = RedFetcher(ConfigParser()["DEFAULT"])
    T.set_request(sys.argv[1], req_hdrs=[("Accept-Encoding", "gzip")])

    def show_link(base: str, link: str, tag: str, title: str) -> None:
        print("* [%s] %s -- %s" % (tag, base, link))

    P = HTMLLinkParser(T.response, [show_link], sys.stderr.write)

    @thor.events.on(T)
    def fetch_done() -> None:
        print("done")
        thor.stop()

    @thor.events.on(T)
    def status(msg: str) -> None:
        print(msg)

    @thor.events.on(T.response)
    def chunk(decoded_chunk: bytes) -> None:
        P.feed(decoded_chunk.decode(P.message.character_encoding, "ignore"))

    T.check()
    thor.run()
