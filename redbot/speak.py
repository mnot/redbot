"""
A collection of notes that the RED can emit.

PLEASE NOTE: the summary field is automatically HTML escaped, so it can contain arbitrary text (as
long as it's unicode).

However, the longer text field IS NOT ESCAPED, and therefore all variables to be interpolated into
it need to be escaped to be safe for use in HTML.
"""

from cgi import escape as e_html
from markdown import markdown


class _Categories(object):
    "Note classifications."
    GENERAL = u"General"
    SECURITY = u"Security"
    CONNEG = u"Content Negotiation"
    CACHING = u"Caching"
    VALIDATION = u"Validation"
    CONNECTION = u"Connection"
    RANGE = u"Partial Content"
categories = _Categories()

class _Levels(object):
    "Note levels."
    GOOD = u'good'
    WARN = u'warning'
    BAD = u'bad'
    INFO = u'info'
levels = _Levels()

class Note(object):
    """
    A note about an HTTP resource, representation, or other component
    related to the URI under test.
    """
    category = None
    level = None
    summary = u""
    text = u""
    def __init__(self, subject, subrequest=None, vrs=None):
        self.subject = subject
        self.subrequest = subrequest
        self.vars = vrs or {}

    def __eq__(self, other):
        if self.__class__ == other.__class__ \
           and self.vars == other.vars \
           and self.subject == other.subject:
            return True
        else:
            return False

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
            [(k, e_html(unicode(v), True)) for k, v in self.vars.items()]
        ), output_format="html5")


response = {
    'this': 'This response',
    'conneg': 'The uncompressed response',
    'LM validation': 'The 304 response',
    'ETag validation': 'The 304 response',
    'range': 'The partial response',
}




if __name__ == '__main__':
    # do a sanity check on all of the defined messages
    import re, types
    for n, v in locals().items():
        if isinstance(v, types.ClassType) and issubclass(v, Note) \
          and n != "Note":
            print "checking", n
            assert v.category in categories.__class__.__dict__.values(), n
            assert v.level in levels.__class__.__dict__.values(), n
            assert isinstance(v.summary, types.UnicodeType), n
            assert v.summary != "", n
            assert not re.search(r"\s{2,}", v.summary), n
            assert isinstance(v.text, types.UnicodeType), n
    #        assert v.text != "", n
