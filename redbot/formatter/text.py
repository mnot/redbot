#!/usr/bin/env python

"""
HAR Formatter for REDbot.
"""

from html.parser import HTMLParser
import operator
import re
import textwrap
from typing import Any, List

import thor.http.error as httperr

from redbot.formatter import Formatter
from redbot.resource import HttpResource
from redbot.speak import Note, levels, categories

nl = "\n"


class BaseTextFormatter(Formatter):
    """
    Base class for text formatters."""
    media_type = "text/plain"

    note_categories = [
        categories.GENERAL,
        categories.SECURITY,
        categories.CONNECTION,
        categories.CONNEG,
        categories.CACHING,
        categories.VALIDATION,
        categories.RANGE
    ]

    link_order = [
        ('link', 'Head Links'),
        ('script', 'Script Links'),
        ('frame', 'Frame Links'),
        ('iframe', 'IFrame Links'),
        ('img', 'Image Links'),
    ]

    error_template = "Error: %s\n"

    def __init__(self, *args: Any, **kw: Any) -> None:
        Formatter.__init__(self, *args, **kw)
        self.verbose = False

    def start_output(self) -> None:
        pass

    def feed(self, chunk: bytes) -> None:
        pass

    def status(self, msg: str) -> None:
        pass

    def finish_output(self) -> None:
        "Fill in the template with RED's results."
        if self.resource.response.complete:
            self.output(self.format_headers(self.resource) + nl + nl)
            self.output(self.format_recommendations(self.resource) + nl)
        else:
            if self.resource.response.http_error is None:
                pass
            elif isinstance(self.resource.response.http_error, httperr.HttpError):
                self.output(self.error_template % self.resource.response.http_error.desc)
            else:
                raise AssertionError("Unknown incomplete response error.")

    def format_headers(self, resource: HttpResource) -> str:
        out = ["HTTP/%s %s %s" % (
            resource.response.version,
            resource.response.status_code,
            resource.response.status_phrase
        )]
        return nl.join(out + ["%s:%s" % h for h in resource.response.headers])

    def format_recommendations(self, resource: HttpResource) -> str:
        return "".join([self.format_recommendation(resource, category) \
            for category in self.note_categories])

    def format_recommendation(self, resource: HttpResource, category: categories) -> str:
        notes = [note for note in resource.notes if note.category == category]
        if not notes:
            return ""
        out = []
        if [note for note in notes]:
            out.append("* %s:" % category.value)
        for m in notes:
            out.append("  * %s" % (self.colorize(m.level, m.show_summary("en"))))
            if self.verbose:
                out.append('')
                out.extend('    ' + line for line in self.format_text(m))
                out.append('')
        out.append(nl)
        return nl.join(out)

    def format_text(self, m: Note) -> List[str]:
        return textwrap.wrap(strip_tags(re.sub(r"(?m)\s\s+", " ", m.show_text("en"))))

    def colorize(self, level: levels, instr: str) -> str:
        if self.kw.get('tty_out', False):
            # info
            color_start = "\033[0;32m"
            color_end = "\033[0;39m"
            if level == levels.GOOD:
                color_start = "\033[1;32m"
                color_end = "\033[0;39m"
            if level == levels.BAD:
                color_start = "\033[1;31m"
                color_end = "\033[0;39m"
            if level == levels.WARN:
                color_start = "\033[1;33m"
                color_end = "\033[0;39m"
            else:
                color_start = "\033[1;34m"
                color_end = "\033[0;39m"
            return color_start + instr + color_end
        else:
            return instr



class TextFormatter(BaseTextFormatter):
    """
    Format a REDbot object as text.
    """
    name = "txt"
    media_type = "text/plain"

    def __init__(self, *args: Any, **kw: Any) -> None:
        BaseTextFormatter.__init__(self, *args, **kw)

    def finish_output(self) -> None:
        BaseTextFormatter.finish_output(self)


class VerboseTextFormatter(TextFormatter):
    name = 'txt_verbose'

    def __init__(self, *args: Any, **kw: Any) -> None:
        TextFormatter.__init__(self, *args, **kw)
        self.verbose = True


class TextListFormatter(BaseTextFormatter):
    """
    Format multiple REDbot responses as a textual list.
    """
    name = "text"
    media_type = "text/plain"
    can_multiple = True

    def __init__(self, *args: Any, **kw: Any) -> None:
        BaseTextFormatter.__init__(self, *args, **kw)

    def finish_output(self) -> None:
        "Fill in the template with RED's results."
        BaseTextFormatter.finish_output(self)
        sep = "=" * 78
        for hdr_tag, heading in self.link_order:
            subresources = [d[0] for d in self.resource.linked if d[1] == hdr_tag]
            self.output("%s\n%s (%d)\n%s\n" % (
                sep, heading, len(subresources), sep
            ))
            if subresources:
                subresources.sort(key=operator.attrgetter('request.uri'))
                for subresource in subresources:
                    self.output(self.format_uri(subresource) + nl + nl)
                    self.output(self.format_headers(subresource) + nl + nl)
                    self.output(self.format_recommendations(subresource) + nl + nl)

    def format_uri(self, resource: HttpResource) -> str:
        return self.colorize(None, resource.request.uri)


class VerboseTextListFormatter(TextListFormatter):
    name = "txt_verbose"

    def __init__(self, *args: Any, **kw: Any) -> None:
        TextListFormatter.__init__(self, *args, **kw)
        self.verbose = True


class MLStripper(HTMLParser):
    def __init__(self) -> None:
        self.reset()
        self.fed = [] # type: List[str]
    def handle_data(self, d: str) -> None:
        self.fed.append(d)
    def get_data(self) -> str:
        return ''.join(self.fed)

def strip_tags(html: str) -> str:
    s = MLStripper()
    s.feed(html)
    return s.get_data()
