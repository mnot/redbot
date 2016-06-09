# Decorators for headers

from redbot.message import http_syntax as syntax
import redbot.speak as rs
import re

def GenericHeaderSyntax(func):
    """
    Decorator for parse; to take a list of header values, split on commas
    (except where escaped) and return a list of header field-values. This will
    not work for Set-Cookie (which contains an unescaped comma) and similar
    headers containing bare dates.

    E.g.,
      ["foo,bar", "baz, bat"]
    becomes
      ["foo", "bar", "baz", "bat"]
    """
    assert func.__name__ == 'parse', func.__name__
    def split_generic_syntax(value): # pylint: disable=C0111
        return [f.strip() for f in re.findall(r'((?:[^",]|%s)+)(?=%s|\s*$)' %
             (syntax.QUOTED_STRING, syntax.COMMA), value)] or ['']
    func.pre_parse = split_generic_syntax
    return func

def SingleFieldValue(func):
    """
    Decorator for join, to make sure that there's only one value.
    """
    assert func.__name__ == 'join', func.__name__
    def new(subject, values, msg): # pylint: disable=C0111
        if values == []: # weird, yes
            values = [None]
        if len(values) > 1:
            msg.add_note(subject, rs.SINGLE_HEADER_REPEAT)
        return func(subject, values, msg)
    new.__name__ = func.__name__
    return new

def RequestHeader(func):
    """
    Decorator for parse; assures that the header is only used in requests.
    """
    assert func.__name__ == 'parse', func.__name__
    assert hasattr(func, 'valid_msgs') == False, "Make up your mind."
    def new(subject, value, msg): # pylint: disable=C0111
        if msg.is_request != True:
            msg.add_note(subject, rs.RESPONSE_HDR_IN_REQUEST)
            def bad_hdr(subject, value, msg): # pylint: disable=W0613
                "Don't process headers that aren't used correctly."
                return None
            return bad_hdr(subject, value, msg)
        return func(subject, value, msg)
    new.__name__ = func.__name__
    new.valid_msgs = ['request']
    return new

def ResponseHeader(func):
    """
    Decorator for parse; assures that the header is only used in responses.
    """
    assert func.__name__ == 'parse', func.__name__
    assert hasattr(func, 'valid_msgs') == False, "Make up your mind."
    def new(subject, value, msg): # pylint: disable=C0111
        if msg.is_request != False:
            msg.add_note(subject, rs.REQUEST_HDR_IN_RESPONSE)
            def bad_hdr(subject, value, msg): # pylint: disable=W0613
                "Don't process headers that aren't used correctly."
                return None
            return bad_hdr(subject, value, msg)
        return func(subject, value, msg)
    new.__name__ = func.__name__
    new.valid_msgs = ['response']
    return new

def RequestOrResponseHeader(func):
    """
    Decorator for parse; header can be used in both requests and responses.
    """
    assert func.__name__ == 'parse', func.__name__
    assert hasattr(func, 'valid_msgs') == False, "Make up your mind."
    func.valid_msgs = ['request', 'response']
    return func

def ResponseOrPutHeader(func):
    """
    Decorator for parse; header can be used in a response or a PUT request.
    """
    assert func.__name__ == 'parse', func.__name__
    assert hasattr(func, 'valid_msgs') == False, "Make up your mind."
    def new(subject, value, msg): # pylint: disable=C0111
        if msg.is_request != False and msg.method != 'PUT':
            msg.add_note(subject, rs.REQUEST_HDR_IN_RESPONSE)
            def bad_hdr(subject, value, msg): # pylint: disable=W0613
                "Don't process headers that aren't used correctly."
                return None
            return bad_hdr(subject, value, msg)
        return func(subject, value, msg)
    new.__name__ = func.__name__
    new.valid_msgs = ['PUT', 'response']
    return new

def DeprecatedHeader(deprecation_ref):
    """
    Decorator for parse; indicates header is deprecated.
    """
    def wrap(func): # pylint: disable=C0111
        assert func.__name__ == 'parse', func.__name__
        def new(subject, value, msg): # pylint: disable=C0111
            msg.add_note(subject, rs.rs.HEADER_DEPRECATED, deprecation_ref=deprecation_ref)
            return func(subject, value, msg)
        new.__name__ = func.__name__
        new.state = "deprecated"
        return new
    return wrap


def CheckFieldSyntax(exp, ref):
    """
    Decorator for parse; to check each header field-value to conform to the
    regex exp, and if not to point users to url ref.
    """
    def wrap(func): # pylint: disable=C0111
        assert func.__name__ == 'parse', func.__name__
        def new(subject, value, msg): # pylint: disable=C0111
            if not re.match(r"^\s*(?:%s)\s*$" % exp, value, re.VERBOSE):
                msg.add_note(subject, rs.BAD_SYNTAX, ref_uri=ref)
                def bad_syntax(subject, value, msg): # pylint: disable=W0613
                    "Don't process headers with bad syntax."
                    return None
                return bad_syntax(subject, value, msg)
            return func(subject, value, msg)
        new.__name__ = func.__name__
        return new
    return wrap
