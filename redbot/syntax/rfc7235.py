"""
Regex for RFC7235

These regex are directly derived from the collected ABNF in RFC7235.

  <http://httpwg.org/specs/rfc7235.html#collected.abnf>

They should be processed with re.VERBOSE.
"""

from rfc5234 import ALPHA, DIGIT, SP
from rfc7230 import list_rule, BWS, OWS, quoted_string, token

SPEC_URL = u"http://httpwg.org/specs/rfc7235"


# auth-param = token BWS "=" BWS ( token / quoted-string )

auth_param = r"(?: {token} {BWS} = {BWS} (?: {token} | {quoted_string} ) )".format(**locals())

# auth-scheme = token

auth_scheme = token

# token68 = 1*( ALPHA / DIGIT / "-" / "." / "_" / "~" / "+" / "/" ) *"="

token68 = r"(?: (?: {ALPHA} | {DIGIT} | \- | \. | _ | \~ | \+ | / )* =* )".format(**locals())

# challenge = auth-scheme 
#             [ 1*SP 
#               ( token68 / 
#                 [ 
#                    ( "," / auth-param ) 
#                   *( OWS "," [ OWS auth-param ] )
#                 ] 
#               ) 
#             ]

challenge = r"""(?: {auth_scheme} 
                        (?: {SP}+
                          (?: {token68} | 
                            (?: 
                                (?: , | {auth_param} )
                                (?: {OWS} , (?: OWS {auth_param} )? )*
                            )?
                          ) 
                        )? 
)""".format(**locals())

# credentials = auth-scheme 
#             [ 1*SP 
#               ( token68 / 
#                 [ 
#                    ( "," / auth-param ) 
#                   *( OWS "," [ OWS auth-param ] )
#                 ] 
#               ) 
#             ]

credentials = r"""(?: {auth_scheme} 
                        (?: {SP}+
                          (?: {token68} | 
                            (?: 
                                (?: , | {auth_param} )
                                (?: {OWS} , (?: OWS {auth_param} )? )*
                            )?
                          ) 
                        )? 
)""".format(**locals())

# Authorization = credentials

Authorization = credentials

# Proxy-Authenticate = 1#challenge

Proxy_Authenticate = list_rule(challenge, 1)

# Proxy-Authorization = credentials

Proxy_Authorization = credentials

# WWW-Authenticate = 1#challenge

WWW_Authenticate = list_rule(challenge, 1)
