
from .rfc5234 import VCHAR, WSP, CRLF, ALPHA, DIGIT


# qtext           =  %d33 /             ; Printable US-ASCII
#                    %d35-91 /          ;  characters not including
#                    %d93-126 /         ;  "\" or the quote character
#                    obs-qtext

qtext = r"[\x21\x23-\x5b\x5d-\x7e]"

# quoted-pair     =   ("\" (VCHAR / WSP)) / obs-qp

quoted_pair = r"(?: \\ (?: {VCHAR} | {WSP} ) )".format(**locals())

# qcontent        =   qtext / quoted-pair

qcontent = r"(?: {qtext} | {quoted_pair} )".format(**locals())

# ctext           =   %d33-39 /          ; Printable US-ASCII
#                     %d42-91 /          ;  characters not including
#                     %d93-126 /         ;  "(", ")", or "\"
#                     obs-ctext

ctext = r"[\x21-\x27\x2a-\x5b\x5d\x7e]"

# ccontent        =   ctext / quoted-pair / comment

# TODO: nested comments
ccontent = r"(?: {ctext} | {quoted_pair} |)".format(**locals())

# FWS             =   ([*WSP CRLF] 1*WSP) /  obs-FWS

FWS = r"(?: (?: {WSP}* {CRLF} )? {WSP}{{1,}} )".format(**locals())

# comment         =   "(" *([FWS] ccontent) [FWS] ")"

comment = r"(?: \( (?: {FWS}? {ccontent} )* {FWS}? \) )".format(**locals())

# CFWS            =   (1*([FWS] comment) [FWS]) / FWS

CFWS = r"(?: (?: {FWS}? {comment} {FWS}? ){{1,}} | {FWS} )".format(**locals())

# quoted-string   =  [CFWS]
#                    DQUOTE *([FWS] qcontent) [FWS] DQUOTE
#                    [CFWS]

quoted_string = r"(?: {CFWS}? \" (?: {FWS}? {qcontent} )* \" {CFWS}? )".format(**locals())

# atext           =   ALPHA / DIGIT /    ; Printable US-ASCII
#                    "!" / "#" /        ;  characters not including
#                    "$" / "%" /        ;  specials.  Used for atoms.
#                    "&" / "'" /
#                    "*" / "+" /
#                    "-" / "/" /
#                    "=" / "?" /
#                    "^" / "_" /
#                    "`" / "{" /
#                    "|" / "}" /
#                    "~"

atext = r"(?: {ALPHA} | {DIGIT} | [!#$%&'*+-/=?^_`{{|}}~] )".format(**locals())

# atom            =   [CFWS] 1*atext [CFWS]

atom = r"(?: {CFWS}? {atext}{{1,}} {CFWS}? )".format(**locals())

# word            =   atom / quoted-string

word = r"(?: {atom} | {quoted_string} )".format(**locals())

# phrase          =   1*word / obs-phrase

phrase = r"(?: {word}{{1,}} | obs_phrase )".format(**locals())

# display-name    =   phrase

display_name = phrase

# dot-atom-text   =   1*atext *("." 1*atext)

dot_atom_text = r"(?: {atext}+ (?: \. {atext}+ )* )".format(**locals())

# dot-atom        =   [CFWS] dot-atom-text [CFWS]

dot_atom = r"(?: {CFWS}? {dot_atom_text} {CFWS}? )".format(**locals())

# local-part      =   dot-atom / quoted-string / obs-local-part

local_part = r"(?: {dot_atom} | {quoted_string} )".format(**locals())

# dtext           =   %d33-90 /          ; Printable US-ASCII
#                     %d94-126 /         ;  characters not including
#                     obs-dtext          ;  "[", "]", or "\"

dtext = r"[\x21-\x5a\x5e-\x7e]".format(**locals())

# domain-literal  =   [CFWS] "[" *([FWS] dtext) [FWS] "]" [CFWS]

domain_literal = r"(?: {CFWS}? \[ (?: {FWS}? {dtext} )* {FWS}? \] {CFWS}? )".format(**locals())

# domain          =   dot-atom / domain-literal / obs-domain

domain = r"(?: {dot_atom} | {domain_literal} )".format(**locals())

# addr-spec       =   local-part "@" domain

addr_spec = r"(?: {local_part} @ {domain} )".format(**locals())

# angle-addr      =   [CFWS] "<" addr-spec ">" [CFWS] /
#                     obs-angle-addr

angle_addr = r"(?: {CFWS}? \< {addr_spec} \> {CFWS}? )".format(**locals())

# name-addr       =   [display-name] angle-addr

name_addr = r"(?: {display_name}? {angle_addr} )".format(**locals())

# mailbox         =   name-addr / addr-spec

mailbox = r"(?: {name_addr} | {addr_spec} )".format(**locals())
