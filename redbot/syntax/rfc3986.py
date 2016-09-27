#!/usr/bin/env python

"""
Regex for URIs

These regex are directly derived from the collected ABNF in RFC3986:

  https://tools.ietf.org/html/rfc3986#appendix-A

They should be processed with re.VERBOSE.
"""

from .rfc5234 import DIGIT, ALPHA, HEXDIG


#   pct-encoded   = "%" HEXDIG HEXDIG
pct_encoded = r" % {HEXDIG} {HEXDIG}".format(**locals())

#   unreserved    = ALPHA / DIGIT / "-" / "." / "_" / "~"
unreserved = r"(?: {ALPHA} | {DIGIT} | \- | \. | _ | ~ )".format(**locals())

#   gen-delims    = ":" / "/" / "?" / "#" / "[" / "]" / "@"
gen_delims = r"(?: : | / | \? | \# | \[ | \] | @ )"

#   sub-delims    = "!" / "$" / "&" / "'" / "(" / ")"
#                 / "*" / "+" / "," / ";" / "="
sub_delims = r"""(?: ! | \$ | & | ' | \( | \) |
                     \* | \+ | , | ; | = )"""

#   pchar         = unreserved / pct-encoded / sub-delims / ":" / "@"
pchar = r"(?: {unreserved} | {pct_encoded} | {sub_delims} | : | @ )".format(**locals())

#   reserved      = gen-delims / sub-delims
reserved = r"(?: {gen_delims} | {sub_delims} )".format(**locals())


### scheme

#   scheme        = ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )
scheme = r"{ALPHA} (?: {ALPHA} | {DIGIT} | \+ | \- | \. )*".format(**locals())


### authority

#   dec-octet     = DIGIT                 ; 0-9
#                 / %x31-39 DIGIT         ; 10-99
#                 / "1" 2DIGIT            ; 100-199
#                 / "2" %x30-34 DIGIT     ; 200-249
#                 / "25" %x30-35          ; 250-255
dec_octet = r"""(?: {DIGIT} |
                    [\x31-\x39] {DIGIT} |
                    1 {DIGIT}{{2}} |
                    2 [\x30-\x34] {DIGIT} |
                    25 [\x30-\x35]
                )
""".format(**locals())

#  IPv4address   = dec-octet "." dec-octet "." dec-octet "." dec-octet
IPv4address = r"{dec_octet} \. {dec_octet} \. {dec_octet} \. {dec_octet}".format(**locals())

#  h16           = 1*4HEXDIG
h16 = r"(?: {HEXDIG} ){{1,4}}".format(**locals())

#  ls32          = ( h16 ":" h16 ) / IPv4address
ls32 = r"(?: (?: {h16} : {h16} ) | {IPv4address} )".format(**locals())

#   IPv6address   =                            6( h16 ":" ) ls32
#                 /                       "::" 5( h16 ":" ) ls32
#                 / [               h16 ] "::" 4( h16 ":" ) ls32
#                 / [ *1( h16 ":" ) h16 ] "::" 3( h16 ":" ) ls32
#                 / [ *2( h16 ":" ) h16 ] "::" 2( h16 ":" ) ls32
#                 / [ *3( h16 ":" ) h16 ] "::"    h16 ":"   ls32
#                 / [ *4( h16 ":" ) h16 ] "::"              ls32
#                 / [ *5( h16 ":" ) h16 ] "::"              h16
#                 / [ *6( h16 ":" ) h16 ] "::"
IPv6address = r"""(?:                            (?: {h16} : ){{6}} {ls32} |
                                              :: (?: {h16} : ){{5}} {ls32} |
                                        {h16} :: (?: {h16} : ){{4}} {ls32} |
                     (?: {h16} : )      {h16} :: (?: {h16} : ){{3}} {ls32} |
                     (?: {h16} : ){{2}} {h16} :: (?: {h16} : ){{2}} {ls32} |
                     (?: {h16} : ){{3}} {h16} ::     {h16} :        {ls32} |
                     (?: {h16} : ){{4}} {h16} ::                    {ls32} |
                     (?: {h16} : ){{5}} {h16} ::                    {h16}  |
                     (?: {h16} : ){{6}} {h16} ::
                  )
""".format(**locals())

#   IPvFuture     = "v" 1*HEXDIG "." 1*( unreserved / sub-delims / ":" )
IPvFuture = r"v {HEXDIG}+ \. (?: {unreserved} | {sub_delims} | : )+".format(**locals())

#   IP-literal    = "[" ( IPv6address / IPvFuture  ) "]"
IP_literal = r"\[ (?: {IPv6address} | {IPvFuture} ) \]".format(**locals())

#   reg-name      = *( unreserved / pct-encoded / sub-delims )
reg_name = r"(?: {unreserved} | {pct_encoded} | {sub_delims} )*".format(**locals())

#   userinfo      = *( unreserved / pct-encoded / sub-delims / ":" )
userinfo = r"(?: {unreserved} | {pct_encoded} | {sub_delims} | : )".format(**locals())

#   host          = IP-literal / IPv4address / reg-name
host = r"(?: {IP_literal} | {IPv4address} | {reg_name} )".format(**locals())

#   port          = *DIGIT
port = r"(?: {DIGIT} )*".format(**locals())

#   authority     = [ userinfo "@" ] host [ ":" port ]
authority = r"(?: {userinfo} @)? {host} (?: : {port})?".format(**locals())



### Path

#   segment       = *pchar
segment = r"{pchar}*".format(**locals())

#   segment-nz    = 1*pchar
segment_nz = r"{pchar}+".format(**locals())

#   segment-nz-nc = 1*( unreserved / pct-encoded / sub-delims / "@" )
#                 ; non-zero-length segment without any colon ":"
segment_nz_nc = r"(?: {unreserved} | {pct_encoded} | {sub_delims} | @ )+".format(**locals())

#   path-abempty  = *( "/" segment )
path_abempty = r"(?: / {segment} )*".format(**locals())

#   path-absolute = "/" [ segment-nz *( "/" segment ) ]
path_absolute = r"/ (?: {segment_nz} (?: / {segment} )* )?".format(**locals())

#   path-noscheme = segment-nz-nc *( "/" segment )
path_noscheme = r"{segment_nz_nc} (?: / {segment} )*".format(**locals())

#   path-rootless = segment-nz *( "/" segment )
path_rootless = r"{segment_nz} (?: / {segment} )*".format(**locals())

#   path-empty    = 0<pchar>
path_empty = r"{pchar}{0}"

#   path          = path-abempty    ; begins with "/" or is empty
#                 / path-absolute   ; begins with "/" but not "//"
#                 / path-noscheme   ; begins with a non-colon segment
#                 / path-rootless   ; begins with a segment
#                 / path-empty      ; zero characters
path = r"""(?: {path_abempty} |
               {path_absolute} |
               {path_noscheme} |
               {path_rootless} |
               {path_empty}
            )
""".format(**locals())



### Query and Fragment

#   query         = *( pchar / "/" / "?" )
query = r"(?: {pchar} | / | \? )*".format(**locals())

#   fragment      = *( pchar / "/" / "?" )
fragment = r"(?: {pchar} | / | \? )*".format(**locals())



### URIs

#   hier-part     = "//" authority path-abempty
#                 / path-absolute
#                 / path-rootless
#                 / path-empty
hier_part = r"""(?: (?: // {authority} {path_abempty} ) |
                    {path_absolute} |
                    {path_rootless} |
                    {path_empty}
                )
""".format(**locals())

#   relative-part = "//" authority path-abempty
#                 / path-absolute
#                 / path-noscheme
#                 / path-empty
relative_part = r"""(?: (?: // {authority} {path_abempty} ) |
                        {path_absolute} |
                        {path_noscheme} |
                        {path_empty}
                    )
""".format(**locals())

#   relative-ref  = relative-part [ "?" query ] [ "#" fragment ]
relative_ref = r"{relative_part} (?: \? {query})? (?: \# {fragment})?".format(**locals())

#   URI           = scheme ":" hier-part [ "?" query ] [ "#" fragment ]
URI = r"(?: {scheme} : {hier_part} (?: \? {query} )? (?: \# {fragment} )? )".format(**locals())

#   URI-reference = URI / relative-ref
URI_reference = r"(?: {URI} | {relative_ref} )".format(**locals())

#   absolute-URI  = scheme ":" hier-part [ "?" query ]
absolute_URI = r"(?: {scheme} : {hier_part} (?: \? {query} )? )".format(**locals())


if __name__ == "__main__":
    import re
    import sys
    try:
        instr = sys.argv[1]
    except IndexError:
        print("usage: %s test-string" % sys.argv[0])
        sys.exit(1)

    print('testing: "%s"' % instr)

    print("URI:", end=' ')
    if re.match("^%s$" % URI, instr, re.VERBOSE):
        print("yes")
    else:
        print("no")

    print("URI reference:", end=' ')
    if re.match("^%s$" % URI_reference, instr, re.VERBOSE):
        print("yes")
    else:
        print("no")

    print("Absolute URI:", end=' ')
    if re.match("^%s$" % absolute_URI, instr, re.VERBOSE):
        print("yes")
    else:
        print("no")
