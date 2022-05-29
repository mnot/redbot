from .rfc5234 import VCHAR, WSP, CRLF, ALPHA, DIGIT

# pylint: disable=invalid-name


# qtext           =  %d33 /             ; Printable US-ASCII
#                    %d35-91 /          ;  characters not including
#                    %d93-126 /         ;  "\" or the quote character
#                    obs-qtext

qtext = r"[\x21\x23-\x5b\x5d-\x7e]"

# quoted-pair     =   ("\" (VCHAR / WSP)) / obs-qp

quoted_pair = rf"(?: \\ (?: {VCHAR} | {WSP} ) )"

# qcontent        =   qtext / quoted-pair

qcontent = rf"(?: {qtext} | {quoted_pair} )"

# ctext           =   %d33-39 /          ; Printable US-ASCII
#                     %d42-91 /          ;  characters not including
#                     %d93-126 /         ;  "(", ")", or "\"
#                     obs-ctext

ctext = r"[\x21-\x27\x2a-\x5b\x5d\x7e]"

# ccontent        =   ctext / quoted-pair / comment

ccontent = rf"(?: {ctext} | {quoted_pair} |)"

# FWS             =   ([*WSP CRLF] 1*WSP) /  obs-FWS

FWS = rf"(?: (?: {WSP}* {CRLF} )? {WSP}{{1,}} )"

# comment         =   "(" *([FWS] ccontent) [FWS] ")"

comment = rf"(?: \( (?: {FWS}? {ccontent} )* {FWS}? \) )"

# CFWS            =   (1*([FWS] comment) [FWS]) / FWS

CFWS = rf"(?: (?: {FWS}? {comment} {FWS}? ){{1,}} | {FWS} )"

# quoted-string   =  [CFWS]
#                    DQUOTE *([FWS] qcontent) [FWS] DQUOTE
#                    [CFWS]

quoted_string = rf"(?: {CFWS}? \" (?: {FWS}? {qcontent} )* \" {CFWS}? )"

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

atext = rf"(?: {ALPHA} | {DIGIT} | [!#$%&'*+-/=?^_`{{|}}~] )"

# atom            =   [CFWS] 1*atext [CFWS]

atom = rf"(?: {CFWS}? {atext}{{1,}} {CFWS}? )"

# word            =   atom / quoted-string

word = rf"(?: {atom} | {quoted_string} )"

# phrase          =   1*word / obs-phrase

phrase = rf"(?: {word}{{1,}} | obs_phrase )"

# display-name    =   phrase

display_name = phrase

# dot-atom-text   =   1*atext *("." 1*atext)

dot_atom_text = rf"(?: {atext}+ (?: \. {atext}+ )* )"

# dot-atom        =   [CFWS] dot-atom-text [CFWS]

dot_atom = rf"(?: {CFWS}? {dot_atom_text} {CFWS}? )"

# local-part      =   dot-atom / quoted-string / obs-local-part

local_part = rf"(?: {dot_atom} | {quoted_string} )"

# dtext           =   %d33-90 /          ; Printable US-ASCII
#                     %d94-126 /         ;  characters not including
#                     obs-dtext          ;  "[", "]", or "\"

dtext = r"[\x21-\x5a\x5e-\x7e]"

# domain-literal  =   [CFWS] "[" *([FWS] dtext) [FWS] "]" [CFWS]

domain_literal = rf"(?: {CFWS}? \[ (?: {FWS}? {dtext} )* {FWS}? \] {CFWS}? )"

# domain          =   dot-atom / domain-literal / obs-domain

domain = rf"(?: {dot_atom} | {domain_literal} )"

# addr-spec       =   local-part "@" domain

addr_spec = rf"(?: {local_part} @ {domain} )"

# angle-addr      =   [CFWS] "<" addr-spec ">" [CFWS] /
#                     obs-angle-addr

angle_addr = rf"(?: {CFWS}? \< {addr_spec} \> {CFWS}? )"

# name-addr       =   [display-name] angle-addr

name_addr = rf"(?: {display_name}? {angle_addr} )"

# mailbox         =   name-addr / addr-spec

mailbox = rf"(?: {name_addr} | {addr_spec} )"
