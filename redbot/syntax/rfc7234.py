"""
Regex for RFC7234

These regex are directly derived from the collected ABNF in RFC7234.

  <http://httpwg.org/specs/rfc7234.html#collected.abnf>

They should be processed with re.VERBOSE.
"""

from .rfc3986 import port, host as uri_host
from .rfc5234 import DIGIT, DQUOTE, SP
from .rfc7230 import list_rule, pseudonym, quoted_string, token
from .rfc7231 import HTTP_date

SPEC_URL = "http://httpwg.org/specs/rfc7234"


# delta-seconds = 1*DIGIT

delta_seconds = rf"{DIGIT}+"

# Age = delta-seconds

Age = delta_seconds

# cache-directive = token [ "=" ( token / quoted-string ) ]

cache_directive = rf"(?: {token} (?: = (?: {token} | {quoted_string} ) )? )"

# Cache-Control = 1#cache-directive

Cache_Control = list_rule(cache_directive, 1)

# Expires = HTTP-date

Expires = HTTP_date

# extension-pragma = token [ "=" ( token / quoted-string ) ]

extension_pragma = rf"(?: {token} (?: = (?: {token} | {quoted_string} ) )? )"

# pragma-directive = "no-cache" / extension-pragma

pragma_directive = rf"(?: no-cache | {extension_pragma} )"

# Pragma = 1#pragma-directive

Pragma = list_rule(pragma_directive, 1)

# warn-agent = ( uri-host [ ":" port ] ) / pseudonym

warn_agent = rf"(?: (?: {uri_host} (?: : {port} )? ) | {pseudonym} )"

# warn-code = 3DIGIT

warn_code = rf"{DIGIT}{{3}}"

# warn-date = DQUOTE HTTP-date DQUOTE

warn_date = rf"(?: {DQUOTE} {HTTP_date} {DQUOTE} )"

# warn-text = quoted-string

warn_text = quoted_string

# warning-value = warn-code SP warn-agent SP warn-text [ SP warn-date ]

warning_value = (
    rf"(?: {warn_code} {SP} {warn_agent} {SP} {warn_text} (?: {SP} {warn_date} )? )"
)

# Warning = 1#warning-value

Warning_ = list_rule(warning_value, 1)
