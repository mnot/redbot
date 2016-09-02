
import calendar
from email.utils import parsedate as lib_parsedate
import re
import urllib

from redbot.message import http_syntax as syntax
from redbot.speak import Note, c as categories, l as levels

def parse_date(value):
    """Parse a HTTP date. Raises ValueError if it's bad."""
    if not re.match(r"%s$" % syntax.DATE, value, re.VERBOSE):
        raise ValueError
    date_tuple = lib_parsedate(value)
    if date_tuple is None:
        raise ValueError
    # http://sourceforge.net/tracker/index.php?func=detail&aid=1194222&group_id=5470&atid=105470
    if date_tuple[0] < 100:
        if date_tuple[0] > 68:
            date_tuple = (date_tuple[0]+1900,)+date_tuple[1:]
        else:
            date_tuple = (date_tuple[0]+2000,)+date_tuple[1:]
    date = calendar.timegm(date_tuple)
    return date

def unquote_string(instr):
    """
    Unquote a unicode string; does NOT unquote control characters.

    @param instr: string to be unquoted
    @type instr: unicode
    @return: unquoted string
    @rtype: unicode
    """
    instr = unicode(instr).strip()
    if not instr or instr == '*':
        return instr
    if instr[0] == instr[-1] == '"':
        ninstr = instr[1:-1]
        instr = re.sub(r'\\(.)', r'\1', ninstr)
    return instr

def split_string(instr, item, split):
    """
    Split instr as a list of items separated by splits.

    @param instr: string to be split
    @param item: regex for item to be split out
    @param split: regex for splitter
    @return: list of strings
    """
    if not instr:
        return []
    return [h.strip() for h in re.findall(
        r'%s(?=%s|\s*$)' % (item, split), instr
    )]

def parse_params(msg, subject, instr, nostar=None, delim=";"):
    """
    Parse parameters into a dictionary.

    @param msg: the message instance to use
    @param subject: the subject identifier
    @param instr: string to be parsed
    @param nostar: list of parameters that definitely don't get a star. If
                   True, no parameter can be starred.
    @param delim: delimter between params, default ";"
    @return: dictionary of {name: value}
    """
    param_dict = {}
    instr = instr.encode('ascii') # TODO: non-ascii input?
    for param in split_string(instr, syntax.PARAMETER, r"\s*%s\s*" % delim):
        try:
            key, val = param.split("=", 1)
        except ValueError:
            param_dict[param.lower()] = None
            continue
        k_norm = key.lower() # TODO: warn on upper-case in param?
        if param_dict.has_key(k_norm):
            msg.add_note(subject, PARAM_REPEATS, param=k_norm)
        if val[0] == val[-1] == "'":
            msg.add_note(subject,
                PARAM_SINGLE_QUOTED,
                param=k_norm,
                param_val=val,
                param_val_unquoted=val[1:-1]
            )
        if key[-1] == '*':
            if nostar is True or (nostar and k_norm[:-1] in nostar):
                msg.add_note(subject, PARAM_STAR_BAD,
                                param=k_norm[:-1])
            else:
                if val[0] == '"' and val[-1] == '"':
                    msg.add_note(subject, PARAM_STAR_QUOTED,
                                    param=k_norm)
                    val = unquote_string(val).encode('ascii')
                try:
                    enc, lang, esc_v = val.split("'", 3)
                except ValueError:
                    msg.add_note(subject, PARAM_STAR_ERROR,
                                    param=k_norm)
                    continue
                enc = enc.lower()
                lang = lang.lower()
                if enc == '':
                    msg.add_note(subject,
                        PARAM_STAR_NOCHARSET, param=k_norm)
                    continue
                elif enc not in ['utf-8']:
                    msg.add_note(subject,
                        PARAM_STAR_CHARSET,
                        param=k_norm,
                        enc=enc
                    )
                    continue
                # TODO: catch unquoting errors, range of chars, charset
                unq_v = urllib.unquote(esc_v)
                dec_v = unq_v.decode(enc) # ok, because we limit enc above
                param_dict[k_norm] = dec_v
        else:
            param_dict[k_norm] = unquote_string(val)
    return param_dict


## notes

class SINGLE_HEADER_REPEAT(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"Only one %(field_name)s header is allowed in a response."
    text = u"""\
This header is designed to only occur once in a message. When it occurs more than once, a receiver
needs to choose the one to use, which can lead to interoperability problems, since different
implementations may make different choices.

For the purposes of its tests, RED uses the last instance of the header that is present; other
implementations may behave differently."""


class BAD_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The %(field_name)s header's syntax isn't valid."
    text = u"""\
The value for this header doesn't conform to its specified syntax; see [its
definition](%(ref_uri)s) for more information."""

class PARAM_STAR_QUOTED(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The '%(param)s' parameter's value cannot be quoted."
    text = u"""\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](http://tools.ietf.org/html/rfc5987), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` header has double-quotes around it, which is not
valid."""

class PARAM_STAR_ERROR(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The %(param)s parameter's value is invalid."
    text = u"""\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](http://tools.ietf.org/html/rfc5987), to allow non-ASCII text.
 
 The `%(param)s` parameter on the `%(field_name)s` header is not valid; it needs to have three
parts, separated by single quotes (')."""

class PARAM_STAR_BAD(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The %(param)s* parameter isn't allowed on the %(field_name)s header."
    text = u"""\
Parameter values that end in '*' are reserved for non-ascii text, as explained in
[RFC5987](http://tools.ietf.org/html/rfc5987).

The `%(param)s` parameter on the `%(field_name)s` does not allow this; you should use %(param)s
without the "*" on the end (and without the associated encoding).

RED ignores the content of this parameter. 
     """

class PARAM_STAR_NOCHARSET(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The %(param)s parameter's value doesn't define an encoding."
    text = u"""\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](http://tools.ietf.org/html/rfc5987), to allow non-ASCII text.

The `%(param)s` parameter on the `%(field_name)s` header doesn't declare its character encoding,
which means that recipients can't understand it. It should be `UTF-8`."""

class PARAM_STAR_CHARSET(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The %(param)s parameter's value uses an encoding other than UTF-8."
    text = u"""\
Parameter values that end in '*' have a specific format, defined in
[RFC5987](http://tools.ietf.org/html/rfc5987), to allow non-ASCII text.
 
The `%(param)s` parameter on the `%(field_name)s` header uses the `'%(enc)s` encoding, which has
interoperability issues on some browsers. It should be `UTF-8`."""

class PARAM_REPEATS(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The '%(param)s' parameter repeats in the %(field_name)s header."
    text = u"""\
Parameters on the %(field_name)s header should not repeat; implementations may handle them
differently."""

class PARAM_SINGLE_QUOTED(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = u"The '%(param)s' parameter on the %(field_name)s header is single-quoted."
    text = u"""\
The `%(param)s`'s value on the %(field_name)s header start and ends with a single quote (').
However, single quotes don't mean anything there.

This means that the value will be interpreted as `%(param_val)s`, **not**
`%(param_val_unquoted)s`. If you intend the latter, drop the single quotes."""

class BAD_DATE_SYNTAX(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = u"The %(field_name)s header's value isn't a valid date."
    text = u"""\
HTTP dates have very specific syntax, and sending an invalid date can cause a number of problems,
especially around caching. Common problems include sending "1 May" instead of "01 May" (the month
is a fixed-width field), and sending a date in a timezone other than GMT. See [the HTTP
specification](http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.3) for more
information."""

