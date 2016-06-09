# alphanum      = (ALPHA / DIGIT)     ; letters and numbers
#
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
#
# regular       = "art-lojban"        ; these tags match the 'langtag'
#               / "cel-gaulish"       ; production, but their subtags
#               / "no-bok"            ; are not extended language
#               / "no-nyn"            ; or variant subtags: their meaning
#               / "zh-guoyu"          ; is defined by their registration
#               / "zh-hakka"          ; and all of these are deprecated
#               / "zh-min"            ; in favor of a more modern
#               / "zh-min-nan"        ; subtag or sequence of subtags
#               / "zh-xiang"
#
# grandfathered = irregular           ; non-redundant tags registered
#               / regular             ; during the RFC 3066 era
#
# extlang       = 3ALPHA              ; selected ISO 639 codes
#                 *2("-" 3ALPHA)      ; permanently reserved
#
#
# language      = 2*3ALPHA            ; shortest ISO 639 code
#                 ["-" extlang]       ; sometimes followed by
#                                     ; extended language subtags
#               / 4ALPHA              ; or reserved for future use
#               / 5*8ALPHA            ; or registered language subtag
#
# script        = 4ALPHA              ; ISO 15924 code
#
# region        = 2ALPHA              ; ISO 3166-1 code
#               / 3DIGIT              ; UN M.49 code
#
# variant       = 5*8alphanum         ; registered variants
#               / (DIGIT 3alphanum)
#
# singleton     = DIGIT               ; 0 - 9
#               / %x41-57             ; A - W
#               / %x59-5A             ; Y - Z
#               / %x61-77             ; a - w
#               / %x79-7A             ; y - z
#
# extension     = singleton 1*("-" (2*8alphanum))
#
# privateuse    = "x" 1*("-" (1*8alphanum))
#
# langtag       = language
#                 ["-" script]
#                 ["-" region]
#                 *("-" variant)
#                 *("-" extension)
#                 ["-" privateuse]
#
# Language-Tag  = langtag             ; normal language tags
#               / privateuse          ; private use tag
#               / grandfathered       ; grandfathered tags

Language_Tag =  r"[.]+" # FIXME