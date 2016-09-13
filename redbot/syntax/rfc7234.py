"""
Regex for RFC7234

These regex are directly derived from the collected ABNF in RFC7234.

  <http://httpwg.org/specs/rfc7234.html#collected.abnf>

They should be processed with re.VERBOSE.
"""

from rfc3986 import port, host as uri_host
from rfc5234 import DIGIT, DQUOTE, SP
from rfc7230 import list_rule, OWS, field_name, pseudonym, quoted_string, token
from rfc7231 import HTTP_date

SPEC_URL = u"http://httpwg.org/specs/rfc7234"


# delta-seconds = 1*DIGIT

delta_seconds = r"{DIGIT}+".format(**locals())

# Age = delta-seconds

Age = delta_seconds

# cache-directive = token [ "=" ( token / quoted-string ) ]

cache_directive = r"(?: {token} (?: = (?: {token} | {quoted_string} ) )? )".format(**locals())

# Cache-Control = 1#cache-directive

Cache_Control = list_rule(cache_directive, 1)

# Expires = HTTP-date

Expires = HTTP_date

# extension-pragma = token [ "=" ( token / quoted-string ) ]

extension_pragma = r"(?: {token} (?: = (?: {token} | {quoted_string} ) )? )".format(**locals())

# pragma-directive = "no-cache" / extension-pragma

pragma_directive = r"(?: no-cache | {extension_pragma} )".format(**locals())

# Pragma = 1#pragma-directive

Pragma = list_rule(pragma_directive, 1)

# warn-agent = ( uri-host [ ":" port ] ) / pseudonym

warn_agent = r"(?: (?: {uri_host} (?: : {port} )? ) | {pseudonym} )"

# warn-code = 3DIGIT

warn_code = r"{DIGIT}{{3}}".format(**locals())

# warn-date = DQUOTE HTTP-date DQUOTE

warn_date = r"(?: {DQUOTE} {HTTP_date} {DQUOTE} )".format(**locals())

# warn-text = quoted-string

warn_text = quoted_string

# warning-value = warn-code SP warn-agent SP warn-text [ SP warn-date ]

warning_value = r"(?: {warn_code} {SP} {warn_agent} {SP} {warn_text} (?: {SP} {warn_date} )? )".format(**locals())

# Warning = 1#warning-value

Warning = list_rule(warning_value, 1)
