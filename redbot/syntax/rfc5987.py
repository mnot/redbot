"""
Regex for RFC5987

These regex are directly derived from the collected ABNF in RFC5987.

Well, not really; it's:

  <http://httpwg.org/http-extensions/rfc5987bis.html>

They should be processed with re.VERBOSE.
"""

from .rfc5234 import ALPHA, DIGIT, HEXDIG
from .rfc5646 import Language_Tag

SPEC_URL = "http://httpwg.org/specs/rfc5987"


#  language      = <Language-Tag, see [RFC5646], Section 2.1>

language = Language_Tag

#  pct-encoded   = "%" HEXDIG HEXDIG
#                ; see [RFC3986], Section 2.1

pct_encoded = rf"(?: % {HEXDIG} {HEXDIG} )"

#  attr-char     = ALPHA / DIGIT
#                / "!" / "#" / "$" / "&" / "+" / "-" / "."
#                / "^" / "_" / "`" / "|" / "~"
#                ; token except ( "*" / "'" / "%" )

attr_char = rf"""(?:
                  {ALPHA} | {DIGIT}
                | !  | #  | \$ | &  | \+ | -  | .
                | \^ | _  | `  | \| | ~
)"""

#  value-chars   = *( pct-encoded / attr-char )

value_chars = rf"(?: (?: {pct_encoded} | {attr_char} )* )"

#  mime-charsetc = ALPHA / DIGIT
#                / "!" / "#" / "$" / "%" / "&"
#                / "+" / "-" / "^" / "_" / "`"
#                / "{" / "}" / "~"
#                ; as <mime-charset> in Section 2.3 of [RFC2978]
#                ; except that the single quote is not included
#                ; SHOULD be registered in the IANA charset registry

mime_charsetc = rf"""(?:
                  {ALPHA} | {DIGIT}
                | !  | #  | \$ | %  | &
                | \+ | -  | \^ | _  | `
                | \{{ | \}} | ~
)"""

#  mime-charset  = 1*mime-charsetc

mime_charset = rf"(?: {mime_charsetc}+ )"

#  charset       = "UTF-8" / mime-charset

charset = rf"(?: UTF-8 | {mime_charset} )"

#  ext-value     = charset  "'" [ language ] "'" value-chars
#                ; like RFC 2231's <extended-initial-value>
#                ; (see [RFC2231], Section 7)

ext_value = rf"(?: {charset} ' (?: {language} )? ' {value_chars} )"
