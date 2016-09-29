"""
A collection of notes that the RED can emit.

PLEASE NOTE: the summary field is automatically HTML escaped, so it can contain arbitrary text (as
long as it's unicode).

However, the longer text field IS NOT ESCAPED, and therefore all variables to be interpolated into
it need to be escaped to be safe for use in HTML.
"""

from cgi import escape as cgi_escape
from functools import partial
from markdown import markdown

e_html = partial(cgi_escape, quote=True)

class _Categories(object):
    "Note classifications."
    GENERAL = "General"
    SECURITY = "Security"
    CONNEG = "Content Negotiation"
    CACHING = "Caching"
    VALIDATION = "Validation"
    CONNECTION = "Connection"
    RANGE = "Partial Content"
categories = _Categories()

class _Levels(object):
    "Note levels."
    GOOD = 'good'
    WARN = 'warning'
    BAD = 'bad'
    INFO = 'info'
levels = _Levels()

class Note(object):
    """
    A note about an HTTP resource, representation, or other component
    related to the URI under test.
    """
    category = None
    level = None
    summary = ""
    text = ""
    def __init__(self, subject, vrs=None):
        self.subject = subject
        self.vars = vrs or {}

    def __eq__(self, other):
        return bool(self.__class__ == other.__class__ \
           and self.vars == other.vars \
           and self.subject == other.subject)

    def show_summary(self, lang):
        """
        Output a textual summary of the message as a Unicode string.

        Note that if it is displayed in an environment that needs
        encoding (e.g., HTML), that is *NOT* done.
        """
        return self.summary % self.vars

    def show_text(self, lang):
        """
        Show the HTML text for the message as a Unicode string.

        The resulting string is already HTML-encoded.
        """
        return markdown(self.text % dict(
            [(k, e_html(str(v))) for k, v in list(self.vars.items())]
        ), output_format="html5")




if __name__ == '__main__':
    # do a sanity check on all of the defined messages
    import re
    for n, v in list(locals().items()):
        if isinstance(v, type) and issubclass(v, Note) \
          and n != "Note":
            print("checking", n)
            assert v.category in list(categories.__class__.__dict__.values()), n
            assert v.level in list(levels.__class__.__dict__.values()), n
            assert isinstance(v.summary, str), n
            assert v.summary != "", n
            assert not re.search(r"\s{2,}", v.summary), n
            assert isinstance(v.text, str), n
    #        assert v.text != "", n
