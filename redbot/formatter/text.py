#!/usr/bin/env python

"""
HAR Formatter for REDbot.
"""


try:
    from html.parser import HTMLParser
except ImportError:
    from HTMLParser import HTMLParser
import operator
import re
import textwrap

import thor.http.error as httperr

from redbot.formatter import Formatter
from redbot.speak import levels, categories

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

    def __init__(self, *args, **kw):
        Formatter.__init__(self, *args, **kw)
        self.verbose = False

    def start_output(self):
        pass

    def feed(self, chunk):
        pass

    def status(self, msg):
        pass

    def finish_output(self):
        "Fill in the template with RED's results."
        if self.resource.response.complete:
            self.output(self.format_headers(self.resource) + nl + nl)
            self.output(self.format_recommendations(self.resource) + nl)
        else:
            if self.resource.response.http_error is None:
                pass
            elif isinstance(self.resource.response.http_error, httperr.HttpError):
                self.output(self.error_template % \
                            self.resource.response.http_error.desc)
            else:
                raise AssertionError("Unknown incomplete response error.")

    def format_headers(self, resource):
        out = ["HTTP/%s %s %s" % (
            resource.response.version,
            resource.response.status_code,
            resource.response.status_phrase
        )]
        return nl.join(out + ["%s:%s" % h for h in resource.response.headers])

    def format_recommendations(self, resource):
        return "".join([self.format_recommendation(resource, category) \
            for category in self.note_categories])

    def format_recommendation(self, resource, category):
        notes = [note for note in resource.notes if note.category == category]
        if not notes:
            return ""
        out = []
        if [note for note in notes]:
            out.append("* %s:" % category)
        for m in notes:
            out.append(
                "  * %s" % (self.colorize(m.level, m.show_summary("en")))
            )
            if self.verbose:
                out.append('')
                out.extend('    ' + line for line in self.format_text(m))
                out.append('')
        out.append(nl)
        return nl.join(out)

    def format_text(self, m):
        return textwrap.wrap(
            strip_tags(
                re.sub(
                    r"(?m)\s\s+",
                    " ",
                    m.show_text("en")
                )
            )
        )

    def colorize(self, level, string):
        if self.kw.get('tty_out', False):
            # info
            color_start = "\033[0;32m"
            color_end = "\033[0;39m"
            if level == "good":
                color_start = "\033[1;32m"
                color_end = "\033[0;39m"
            if level == "bad":
                color_start = "\033[1;31m"
                color_end = "\033[0;39m"
            if level == "warning":
                color_start = "\033[1;33m"
                color_end = "\033[0;39m"
            if level == "uri":
                color_start = "\033[1;34m"
                color_end = "\033[0;39m"
            return color_start + string + color_end
        else:
            return string



class TextFormatter(BaseTextFormatter):
    """
    Format a RED object as text.
    """
    name = "txt"
    media_type = "text/plain"

    def __init__(self, *args, **kw):
        BaseTextFormatter.__init__(self, *args, **kw)

    def finish_output(self):
        BaseTextFormatter.finish_output(self)


class VerboseTextFormatter(TextFormatter):
    name = 'txt_verbose'

    def __init__(self, *args, **kw):
        TextFormatter.__init__(self, *args, **kw)
        self.verbose = True


class TextListFormatter(BaseTextFormatter):
    """
    Format multiple RED responses as a textual list.
    """
    name = "text"
    media_type = "text/plain"
    can_multiple = True

    def __init__(self, *args, **kw):
        BaseTextFormatter.__init__(self, *args, **kw)

    def finish_output(self):
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

    def format_uri(self, resource):
        return self.colorize("uri", resource.request.uri)


class VerboseTextListFormatter(TextListFormatter):
    name = "txt_verbose"

    def __init__(self, *args, **kw):
        TextListFormatter.__init__(self, *args, **kw)
        self.verbose = True


class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()
