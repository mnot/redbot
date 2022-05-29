"""
Regex for ABNF

These regex are directly derived from the core ABNF in RFC5234:

  https://tools.ietf.org/html/rfc5234#appendix-B.1

They should be processed with re.VERBOSE.
"""


# ALPHA          =  %x41-5A / %x61-7A   ; A-Z / a-z

ALPHA = r"[\x41-\x5A\x61-\x7A]"

# BIT            =  "0" / "1"

BIT = r"[01]"

# CHAR           =  %x01-7F
#                     ; any 7-bit US-ASCII character,
#                     ;  excluding NUL
#
# CR             =  %x0D
#                     ; carriage return

CR = r"[\x0D]"

# LF             =  %x0A
#                     ; linefeed

LF = r"[\x0A]"

# CRLF           =  CR LF
#                     ; Internet standard newline

CRLF = rf"(?: {CR} {LF} )"

# CTL            =  %x00-1F / %x7F
#                     ; controls

CTL = r"[\x00-\x1F\x7F]"

# DIGIT          =  %x30-39
#                     ; 0-9

DIGIT = r"[\x30-\x39]"

# DQUOTE         =  %x22
#                     ; " (Double Quote)

DQUOTE = r"[\x22]"

# HEXDIG         =  DIGIT / "A" / "B" / "C" / "D" / "E" / "F"

HEXDIG = r"[\x30-\x39A-Fa-f]"

# HTAB           =  %x09
#                     ; horizontal tab

HTAB = r"[\x09]"

# OCTET          =  %x00-FF
#                     ; 8 bits of data

OCTET = r"[\x00-\xFF]"

# SP             =  %x20

SP = r"[\x20]"

# VCHAR          =  %x21-7E
#                     ; visible (printing) characters

VCHAR = r"[\x21-\x7E]"

# WSP            =  SP / HTAB
#                     ; white space

WSP = rf"(?: {SP} | {HTAB} )"

# LWSP           =  *(WSP / CRLF WSP)
#                     ; Use of this linear-white-space rule
#                     ;  permits lines containing only white
#                     ;  space that are no longer legal in
#                     ;  mail headers and have caused
#                     ;  interoperability problems in other
#                     ;  contexts.
#                     ; Do not use when defining mail
#                     ;  headers and use with caution in
#                     ;  other contexts.

LWSP = rf"(?: {WSP} | (?: {CRLF} {WSP} ) )"
