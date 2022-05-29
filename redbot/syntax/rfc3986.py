#!/usr/bin/env python


"""
Regex for URIs

These regex are directly derived from the collected ABNF in RFC3986:

  https://tools.ietf.org/html/rfc3986#appendix-A

They should be processed with re.VERBOSE.
"""

# pylint: disable=invalid-name

from .rfc5234 import DIGIT, ALPHA, HEXDIG


#   pct-encoded   = "%" HEXDIG HEXDIG
pct_encoded = rf" % {HEXDIG} {HEXDIG}"

#   unreserved    = ALPHA / DIGIT / "-" / "." / "_" / "~"
unreserved = rf"(?: {ALPHA} | {DIGIT} | \- | \. | _ | ~ )"

#   gen-delims    = ":" / "/" / "?" / "#" / "[" / "]" / "@"
gen_delims = r"(?: : | / | \? | \# | \[ | \] | @ )"

#   sub-delims    = "!" / "$" / "&" / "'" / "(" / ")"
#                 / "*" / "+" / "," / ";" / "="
sub_delims = r"""(?: ! | \$ | & | ' | \( | \) |
                     \* | \+ | , | ; | = )"""

#   pchar         = unreserved / pct-encoded / sub-delims / ":" / "@"
pchar = rf"(?: {unreserved} | {pct_encoded} | {sub_delims} | : | @ )"

#   reserved      = gen-delims / sub-delims
reserved = rf"(?: {gen_delims} | {sub_delims} )"


### scheme

#   scheme        = ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )
scheme = rf"{ALPHA} (?: {ALPHA} | {DIGIT} | \+ | \- | \. )*"


### authority

#   dec-octet     = DIGIT                 ; 0-9
#                 / %x31-39 DIGIT         ; 10-99
#                 / "1" 2DIGIT            ; 100-199
#                 / "2" %x30-34 DIGIT     ; 200-249
#                 / "25" %x30-35          ; 250-255
dec_octet = rf"""(?: {DIGIT} |
                    [\x31-\x39] {DIGIT} |
                    1 {DIGIT}{{2}} |
                    2 [\x30-\x34] {DIGIT} |
                    25 [\x30-\x35]
                )
"""

#  IPv4address   = dec-octet "." dec-octet "." dec-octet "." dec-octet
IPv4address = rf"{dec_octet} \. {dec_octet} \. {dec_octet} \. {dec_octet}"

#  h16           = 1*4HEXDIG
h16 = rf"(?: {HEXDIG} ){{1,4}}"

#  ls32          = ( h16 ":" h16 ) / IPv4address
ls32 = rf"(?: (?: {h16} : {h16} ) | {IPv4address} )"

#   IPv6address   =                            6( h16 ":" ) ls32
#                 /                       "::" 5( h16 ":" ) ls32
#                 / [               h16 ] "::" 4( h16 ":" ) ls32
#                 / [ *1( h16 ":" ) h16 ] "::" 3( h16 ":" ) ls32
#                 / [ *2( h16 ":" ) h16 ] "::" 2( h16 ":" ) ls32
#                 / [ *3( h16 ":" ) h16 ] "::"    h16 ":"   ls32
#                 / [ *4( h16 ":" ) h16 ] "::"              ls32
#                 / [ *5( h16 ":" ) h16 ] "::"              h16
#                 / [ *6( h16 ":" ) h16 ] "::"
IPv6address = rf"""(?:                            (?: {h16} : ){{6}} {ls32} |
                                              :: (?: {h16} : ){{5}} {ls32} |
                                        {h16} :: (?: {h16} : ){{4}} {ls32} |
                     (?: {h16} : )      {h16} :: (?: {h16} : ){{3}} {ls32} |
                     (?: {h16} : ){{2}} {h16} :: (?: {h16} : ){{2}} {ls32} |
                     (?: {h16} : ){{3}} {h16} ::     {h16} :        {ls32} |
                     (?: {h16} : ){{4}} {h16} ::                    {ls32} |
                     (?: {h16} : ){{5}} {h16} ::                    {h16}  |
                     (?: {h16} : ){{6}} {h16} ::
                  )
"""

#   IPvFuture     = "v" 1*HEXDIG "." 1*( unreserved / sub-delims / ":" )
IPvFuture = rf"v {HEXDIG}+ \. (?: {unreserved} | {sub_delims} | : )+"

#   IP-literal    = "[" ( IPv6address / IPvFuture  ) "]"
IP_literal = rf"\[ (?: {IPv6address} | {IPvFuture} ) \]"

#   reg-name      = *( unreserved / pct-encoded / sub-delims )
reg_name = rf"(?: {unreserved} | {pct_encoded} | {sub_delims} )*"

#   userinfo      = *( unreserved / pct-encoded / sub-delims / ":" )
userinfo = rf"(?: {unreserved} | {pct_encoded} | {sub_delims} | : )"

#   host          = IP-literal / IPv4address / reg-name
host = rf"(?: {IP_literal} | {IPv4address} | {reg_name} )"

#   port          = *DIGIT
port = rf"(?: {DIGIT} )*"

#   authority     = [ userinfo "@" ] host [ ":" port ]
authority = rf"(?: {userinfo} @)? {host} (?: : {port})?"


### Path

#   segment       = *pchar
segment = rf"{pchar}*"

#   segment-nz    = 1*pchar
segment_nz = rf"{pchar}+"

#   segment-nz-nc = 1*( unreserved / pct-encoded / sub-delims / "@" )
#                 ; non-zero-length segment without any colon ":"
segment_nz_nc = rf"(?: {unreserved} | {pct_encoded} | {sub_delims} | @ )+"

#   path-abempty  = *( "/" segment )
path_abempty = rf"(?: / {segment} )*"

#   path-absolute = "/" [ segment-nz *( "/" segment ) ]
path_absolute = rf"/ (?: {segment_nz} (?: / {segment} )* )?"

#   path-noscheme = segment-nz-nc *( "/" segment )
path_noscheme = rf"{segment_nz_nc} (?: / {segment} )*"

#   path-rootless = segment-nz *( "/" segment )
path_rootless = rf"{segment_nz} (?: / {segment} )*"

#   path-empty    = 0<pchar>
path_empty = rf"{pchar}{0}"

#   path          = path-abempty    ; begins with "/" or is empty
#                 / path-absolute   ; begins with "/" but not "//"
#                 / path-noscheme   ; begins with a non-colon segment
#                 / path-rootless   ; begins with a segment
#                 / path-empty      ; zero characters
path = rf"""(?: {path_abempty} |
               {path_absolute} |
               {path_noscheme} |
               {path_rootless} |
               {path_empty}
            )
"""


### Query and Fragment

#   query         = *( pchar / "/" / "?" )
query = rf"(?: {pchar} | / | \? )*"

#   fragment      = *( pchar / "/" / "?" )
fragment = rf"(?: {pchar} | / | \? )*"


### URIs

#   hier-part     = "//" authority path-abempty
#                 / path-absolute
#                 / path-rootless
#                 / path-empty
hier_part = rf"""(?: (?: // {authority} {path_abempty} ) |
                    {path_absolute} |
                    {path_rootless} |
                    {path_empty}
                )
"""

#   relative-part = "//" authority path-abempty
#                 / path-absolute
#                 / path-noscheme
#                 / path-empty
relative_part = rf"""(?: (?: // {authority} {path_abempty} ) |
                        {path_absolute} |
                        {path_noscheme} |
                        {path_empty}
                    )
"""

#   relative-ref  = relative-part [ "?" query ] [ "#" fragment ]
relative_ref = rf"{relative_part} (?: \? {query})? (?: \# {fragment})?"

#   URI           = scheme ":" hier-part [ "?" query ] [ "#" fragment ]
URI = rf"(?: {scheme} : {hier_part} (?: \? {query} )? (?: \# {fragment} )? )"

#   URI-reference = URI / relative-ref
URI_reference = rf"(?: {URI} | {relative_ref} )"

#   absolute-URI  = scheme ":" hier-part [ "?" query ]
absolute_URI = rf"(?: {scheme} : {hier_part} (?: \? {query} )? )"


if __name__ == "__main__":
    import re
    import sys

    try:
        instr = sys.argv[1]
    except IndexError:
        print(f"usage: {sys.argv[0]} test-string")
        sys.exit(1)

    print(f'testing: "{instr}"')

    print("URI:", end=" ")
    if re.match(f"^{URI}$", instr, re.VERBOSE):
        print("yes")
    else:
        print("no")

    print("URI reference:", end=" ")
    if re.match(f"^{URI_reference}$", instr, re.VERBOSE):
        print("yes")
    else:
        print("no")

    print("Absolute URI:", end=" ")
    if re.match(f"^{absolute_URI}$", instr, re.VERBOSE):
        print("yes")
    else:
        print("no")
