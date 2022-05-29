"""
Regex for RFC7235

These regex are directly derived from the collected ABNF in RFC7235.

  <http://httpwg.org/specs/rfc7235.html#collected.abnf>

They should be processed with re.VERBOSE.
"""

from .rfc5234 import ALPHA, DIGIT, SP
from .rfc7230 import list_rule, BWS, OWS, quoted_string, token

SPEC_URL = "http://httpwg.org/specs/rfc7235"


# auth-param = token BWS "=" BWS ( token / quoted-string )

auth_param = rf"(?: {token} {BWS} = {BWS} (?: {token} | {quoted_string} ) )"

# auth-scheme = token

auth_scheme = token

# token68 = 1*( ALPHA / DIGIT / "-" / "." / "_" / "~" / "+" / "/" ) *"="

token68 = rf"(?: (?: {ALPHA} | {DIGIT} | \- | \. | _ | \~ | \+ | / )* =* )"

# challenge = auth-scheme
#             [ 1*SP
#               ( token68 /
#                 [
#                    ( "," / auth-param )
#                   *( OWS "," [ OWS auth-param ] )
#                 ]
#               )
#             ]

challenge = rf"""(?: {auth_scheme}
                        (?: {SP}+
                          (?: {token68} |
                            (?:
                                (?: , | {auth_param} )
                                (?: {OWS} , (?: OWS {auth_param} )? )*
                            )?
                          )
                        )?
)"""

# credentials = auth-scheme
#             [ 1*SP
#               ( token68 /
#                 [
#                    ( "," / auth-param )
#                   *( OWS "," [ OWS auth-param ] )
#                 ]
#               )
#             ]

credentials = rf"""(?: {auth_scheme}
                        (?: {SP}+
                          (?: {token68} |
                            (?:
                                (?: , | {auth_param} )
                                (?: {OWS} , (?: OWS {auth_param} )? )*
                            )?
                          )
                        )?
)"""

# Authorization = credentials

Authorization = credentials

# Proxy-Authenticate = 1#challenge

Proxy_Authenticate = list_rule(challenge, 1)

# Proxy-Authorization = credentials

Proxy_Authorization = credentials

# WWW-Authenticate = 1#challenge

WWW_Authenticate = list_rule(challenge, 1)
