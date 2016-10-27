#!/usr/bin/env python

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.type import AddNoteMethodType


class x_content_type_options(headers.HttpHeader):
    canonical_name = "X-Content-Type-Options"
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def evaluate(self, add_note: AddNoteMethodType) -> None:
        if 'nosniff' in self.value:
            add_note(CONTENT_TYPE_OPTIONS)
        else:
            add_note(CONTENT_TYPE_OPTIONS_UNKNOWN)


class CONTENT_TYPE_OPTIONS(Note):
    category = categories.SECURITY
    level = levels.INFO
    summary = "%(response)s instructs Internet Explorer not to 'sniff' its media type."
    text = """\
Many Web browers "sniff" the media type of responses to figure out whether they're HTML, RSS or
another format, no matter what the `Content-Type` header says.

This header instructs Microsoft's Internet Explorer not to do this, but to always respect the
Content-Type header. It probably won't have any effect in other clients.

See [this blog entry](http://bit.ly/t1UHW2) for more information about this header."""

class CONTENT_TYPE_OPTIONS_UNKNOWN(Note):
    category = categories.SECURITY
    level = levels.WARN
    summary = "%(response)s contains an X-Content-Type-Options header with an unknown value."
    text = """\
Only one value is currently defined for this header, `nosniff`. Using other values here won't
necessarily cause problems, but they probably won't have any effect either.

See [this blog entry](http://bit.ly/t1UHW2) for more information about this header."""
