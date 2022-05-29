"""
Regex for RFC5988

These regex are directly derived from the collected ABNF in RFC5988.

  <https://tools.ietf.org/html/rfc5988#section-5>

They should be processed with re.VERBOSE.
"""

# pylint: disable=invalid-name


from .rfc3986 import URI_reference, URI
from .rfc5234 import ALPHA, DIGIT, SP
from .rfc5646 import Language_Tag
from .rfc5987 import ext_value
from .rfc7230 import list_rule, OWS, quoted_string, token
from .rfc7231 import _type as type_name, subtype as subtype_name

MediaDesc = r"(?: {token} (?: {SP}+ {token} )* )"
parmname = token
LOALPHA = r"(?: [a-z] )"

SPEC_URL = "http://httpwg.org/specs/rfc5988"


#  ext-name-star  = parmname "*" ; reserved for RFC2231-profiled
#                                ; extensions.  Whitespace NOT
#                                ; allowed in between.

ext_name_star = rf"(?: {parmname} [*] )"

#  ptokenchar     = "!" | "#" | "$" | "%" | "&" | "'" | "("
#                 | ")" | "*" | "+" | "-" | "." | "/" | DIGIT
#                 | ":" | "<" | "=" | ">" | "?" | "@" | ALPHA
#                 | "[" | "]" | "^" | "_" | "`" | "{" | "|"
#                 | "}" | "~"

ptokenchar = rf"""(?:
                     !  | #  | \$ | %  | &  | '  | \(
                   | \) | \* | \+ | -  | \. | /  | {DIGIT}
                   | :  | <  | =  | >  | \? | @  | {ALPHA}
                   | \[ | \] | \^ | _  | `  | \{{ | \|
                   | \}} | ~
)"""

#  ptoken         = 1*ptokenchar

ptoken = rf"(?: {ptokenchar}+ )"

#  link-extension = ( parmname [ "=" ( ptoken | quoted-string ) ] )
#                 | ( ext-name-star "=" ext-value )

link_extension = rf"""(?: (?: {parmname} (?: = (?: {ptoken} | {quoted_string} ) )? )
                       | (?: {ext_name_star} = {ext_value} ) )"""

#  media-type     = type-name "/" subtype-name

media_type = rf"(?: {type_name} / {subtype_name} )"

#  quoted-mt      = <"> media-type <">

quoted_mt = rf"""(?: " {media_type} " )"""

#  reg-rel-type   = LOALPHA *( LOALPHA | DIGIT | "." | "-" )

reg_rel_type = rf"(?: {LOALPHA} (?: {LOALPHA} | {DIGIT} | [.-] )* )"

#  ext-rel-type   = URI

ext_rel_type = URI

#  relation-type  = reg-rel-type | ext-rel-type

relation_type = rf"(?: {reg_rel_type} | {ext_rel_type} )"

#  relation-types = relation-type
#                 | <"> relation-type *( 1*SP relation-type ) <">

relation_types = rf"""(?: {relation_type}
                      |  " {relation_type} (?: {SP}+ {relation_type} )* "
)"""

#  link-param     = ( ( "rel" "=" relation-types )
#                 | ( "anchor" "=" <"> URI-Reference <"> )
#                 | ( "rev" "=" relation-types )
#                 | ( "hreflang" "=" Language-Tag )
#                 | ( "media" "=" ( MediaDesc | ( <"> MediaDesc <"> ) ) )
#                 | ( "title" "=" quoted-string )
#                 | ( "title*" "=" ext-value )
#                 | ( "type" "=" ( media-type | quoted-mt ) )
#                 | ( link-extension ) )

link_param = rf"""(?: (?: rel = {relation_types} )
                   | (?: anchor = " {URI_reference} " )
                   | (?: rev = {relation_types} )
                   | (?: hreflang = {Language_Tag} )
                   | (?: media = (?: {MediaDesc} | (?: " {MediaDesc} " ) ) )
                   | (?: title = {quoted_string} )
                   | (?: title\* = {ext_value} )
                   | (?: type = (?: {media_type} | {quoted_mt} ) )
                   | (?: {link_extension} ) )"""

#  link-value     = "<" URI-Reference ">" *( ";" link-param )

link_value = rf"(?: < {URI_reference} > (?: {OWS} ; {OWS} {link_param} )* )"

#  Link           = "Link" ":" #link-value

Link = list_rule(link_value)
