
from rfc5234 import VCHAR, WSP

# qtext           =  %d33 /             ; Printable US-ASCII
#                    %d35-91 /          ;  characters not including
#                    %d93-126 /         ;  "\" or the quote character
#                    obs-qtext

# quoted-pair     =   ("\" (VCHAR / WSP)) / obs-qp

# qcontent        =   qtext / quoted-pair

# ctext           =   %d33-39 /          ; Printable US-ASCII
#                     %d42-91 /          ;  characters not including
#                     %d93-126 /         ;  "(", ")", or "\"
#                     obs-ctext

# ccontent        =   ctext / quoted-pair / comment

# comment         =   "(" *([FWS] ccontent) [FWS] ")"

# FWS             =   ([*WSP CRLF] 1*WSP) /  obs-FWS

# CFWS            =   (1*([FWS] comment) [FWS]) / FWS

# quoted-string   =  [CFWS]
#                    DQUOTE *([FWS] qcontent) [FWS] DQUOTE
#                    [CFWS]

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
 
# atom            =   [CFWS] 1*atext [CFWS]
                        
# word            =   atom / quoted-string
 
# phrase          =   1*word / obs-phrase
    
# display-name    =   phrase

# angle-addr      =   [CFWS] "<" addr-spec ">" [CFWS] /
#                     obs-angle-addr

# name-addr       =   [display-name] angle-addr

# dot-atom-text   =   1*atext *("." 1*atext)

# dot-atom        =   [CFWS] dot-atom-text [CFWS]
   
# local-part      =   dot-atom / quoted-string / obs-local-part

# dtext           =   %d33-90 /          ; Printable US-ASCII
#                     %d94-126 /         ;  characters not including
#                     obs-dtext          ;  "[", "]", or "\"

# domain-literal  =   [CFWS] "[" *([FWS] dtext) [FWS] "]" [CFWS]

# domain          =   dot-atom / domain-literal / obs-domain

# addr-spec       =   local-part "@" domain

# mailbox         =   name-addr / addr-spec

mailbox = r"[.]+"  #FIXME