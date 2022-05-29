"""
Regex for RFC5646

These regex are directly derived from the collected ABNF in RFC5646.

They should be processed with re.VERBOSE.
"""

# pylint: disable=invalid-name


from .rfc5234 import DIGIT, ALPHA


# alphanum      = (ALPHA / DIGIT)     ; letters and numbers

alphanum = r"(?: {ALPHA} | {DIGIT} )"

# irregular     = "en-GB-oed"         ; irregular tags do not match
#               / "i-ami"             ; the 'langtag' production and
#               / "i-bnn"             ; would not otherwise be
#               / "i-default"         ; considered 'well-formed'
#               / "i-enochian"        ; These tags are all valid,
#               / "i-hak"             ; but most are deprecated
#               / "i-klingon"         ; in favor of more modern
#               / "i-lux"             ; subtags or subtag
#               / "i-mingo"           ; combination
#               / "i-navajo"
#               / "i-pwn"
#               / "i-tao"
#               / "i-tay"
#               / "i-tsu"
#               / "sgn-BE-FR"
#               / "sgn-BE-NL"
#               / "sgn-CH-DE"

irregular = r"""
  en-GB-oed
| i-ami
| i-bnn
| i-default
| i-enochian
| i-hak
| i-klingon
| i-lux
| i-mingo
| i-navajo
| i-pwn
| i-tao
| i-tay
| i-tsu
| sgn-BE-FR
| sgn-BE-NL
| sgn-CH-DE
"""

# regular       = "art-lojban"        ; these tags match the 'langtag'
#               / "cel-gaulish"       ; production, but their subtags
#               / "no-bok"            ; are not extended language
#               / "no-nyn"            ; or variant subtags: their meaning
#               / "zh-guoyu"          ; is defined by their registration
#               / "zh-hakka"          ; and all of these are deprecated
#               / "zh-min"            ; in favor of a more modern
#               / "zh-min-nan"        ; subtag or sequence of subtags
#               / "zh-xiang"

regular = r"""
art\-lojban
| cel\-gaulish
| no\-bok
| no\-nyn
| zh\-guoyu
| zh\-hakka
| zh\-min
| zh\-min\-nan
| zh\-xiang
"""

# grandfathered = irregular           ; non-redundant tags registered
#               / regular             ; during the RFC 3066 era

grandfathered = rf"(?: {irregular} | {regular} )"

# extlang       = 3ALPHA              ; selected ISO 639 codes
#                 *2("-" 3ALPHA)      ; permanently reserved

extlang = rf"(?: {ALPHA}{{3}} (?: \- {ALPHA}{{3}} ){{,2}} )"

# language      = 2*3ALPHA            ; shortest ISO 639 code
#                 ["-" extlang]       ; sometimes followed by
#                                     ; extended language subtags
#               / 4ALPHA              ; or reserved for future use
#               / 5*8ALPHA            ; or registered language subtag

language = rf"""(?:
  {ALPHA}{{2,3}}
  (?: \- {extlang} )?
| {ALPHA}{{4}}
| {ALPHA}{{5,8}}
)"""

# script        = 4ALPHA              ; ISO 15924 code

script = rf"(?: {ALPHA}{{4}} )"

# region        = 2ALPHA              ; ISO 3166-1 code
#               / 3DIGIT              ; UN M.49 code

region = rf"(?: {ALPHA}{{2}} | {DIGIT}{{3}} )"

# variant       = 5*8alphanum         ; registered variants
#               / (DIGIT 3alphanum)

variant = rf"(?: {alphanum}{{3}} | (?: {DIGIT} {alphanum}{{3}} ) )"

# singleton     = DIGIT               ; 0 - 9
#               / %x41-57             ; A - W
#               / %x59-5A             ; Y - Z
#               / %x61-77             ; a - w
#               / %x79-7A             ; y - z

singleton = rf"(?: {DIGIT} | [\x41-\x57\x59-\x5a\x61-\x77\x79-\x7a] )"

# extension     = singleton 1*("-" (2*8alphanum))

extension = rf"{singleton} (?: \- {alphanum}{{2,8}} ){{1,}}"

# privateuse    = "x" 1*("-" (1*8alphanum))

privateuse = rf"x (?: \- {alphanum}{{1,8}} ){{1,}}"

# langtag       = language
#                 ["-" script]
#                 ["-" region]
#                 *("-" variant)
#                 *("-" extension)
#                 ["-" privateuse]

langtag = rf"""(?:
  {language}
  (?: \- {script} )?
  (?: \- {region} )?
  (?: \- {variant} )*
  (?: \- {extension} )*
  (?: \- {privateuse} )?
)"""

# Language-Tag  = langtag             ; normal language tags
#               / privateuse          ; private use tag
#               / grandfathered       ; grandfathered tags

Language_Tag = rf"(?: {langtag} | {privateuse} | {grandfathered} )"
