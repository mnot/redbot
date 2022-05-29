"""
Regex for RFC7231

These regex are directly derived from the collected ABNF in RFC7231.

  <http://httpwg.org/specs/rfc7231.html#collected.abnf>

They should be processed with re.VERBOSE.
"""

# pylint: disable=invalid-name,line-too-long


from .rfc3986 import URI_reference, absolute_URI
from .rfc5322 import mailbox
from .rfc5234 import DIGIT, SP, ALPHA
from .rfc5646 import Language_Tag as language_tag
from .rfc7230 import (
    list_rule,
    OWS,
    RWS,
    field_name,
    quoted_string,
    partial_URI,
    comment,
    token,
)

SPEC_URL = "http://httpwg.org/specs/rfc7231"

## Basics

# parameter = token "=" ( token / quoted-string )

parameter = rf"(?: {token} = (?: {token} | {quoted_string} ) )"

# qvalue = ( "0" [ "." *3DIGIT ] ) / ( "1" [ "." *3"0" ] )

qvalue = rf"(?: (?: 0 (: \. {DIGIT}{{,3}} ) ) | (?: 1 (: \. [0]{{,3}} ) ) )"


## Dates

# second = 2DIGIT

second = rf"(?: {DIGIT} {DIGIT} )"

# minute = 2DIGIT

minute = rf"(?: {DIGIT} {DIGIT} )"

# hour = 2DIGIT

hour = rf"(?: {DIGIT} {DIGIT} )"

# time-of-day = hour ":" minute ":" second

time_of_day = rf"(?: {hour} : {minute} : {second} )"

# day = 2DIGIT

day = rf"(?: {DIGIT} {DIGIT} )"

# day-name = %x4D.6F.6E ; Mon
#  / %x54.75.65 ; Tue
#  / %x57.65.64 ; Wed
#  / %x54.68.75 ; Thu
#  / %x46.72.69 ; Fri
#  / %x53.61.74 ; Sat
#  / %x53.75.6E ; Sun

day_name = r"(?: Mon | Tue | Wed | Thu | Fri | Sat | Sun )"

# day-name-l = %x4D.6F.6E.64.61.79 ; Monday
#  / %x54.75.65.73.64.61.79 ; Tuesday
#  / %x57.65.64.6E.65.73.64.61.79 ; Wednesday
#  / %x54.68.75.72.73.64.61.79 ; Thursday
#  / %x46.72.69.64.61.79 ; Friday
#  / %x53.61.74.75.72.64.61.79 ; Saturday
#  / %x53.75.6E.64.61.79 ; Sunday

day_name_l = (
    r"(?: Monday | Tuesday | Wednesday | Thursday | Friday | Saturday | Sunday )"
)

# month = %x4A.61.6E ; Jan
#  / %x46.65.62 ; Feb
#  / %x4D.61.72 ; Mar
#  / %x41.70.72 ; Apr
#  / %x4D.61.79 ; May
#  / %x4A.75.6E ; Jun
#  / %x4A.75.6C ; Jul
#  / %x41.75.67 ; Aug
#  / %x53.65.70 ; Sep
#  / %x4F.63.74 ; Oct
#  / %x4E.6F.76 ; Nov
#  / %x44.65.63 ; Dec

month = r"(?: Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec )"

# year = 4DIGIT

year = rf"(?: {DIGIT}{{4}} )"

# GMT = %x47.4D.54 ; GMT

GMT = r"(?: GMT )"

# date1 = day SP month SP year

date1 = rf"(?: {day} {SP} {month} {SP} {year} )"

# date2 = day "-" month "-" 2DIGIT

date2 = rf"(?: {day} \- {month} \- {DIGIT}{{2}} )"

# date3 = month SP ( 2DIGIT / ( SP DIGIT ) )

date3 = rf"(?: {month} {SP} (?: {DIGIT}{{2}} | (?: {SP} {DIGIT} ) ) )"

# IMF-fixdate = day-name "," SP date1 SP time-of-day SP GMT

IMF_fixdate = rf"(?: {day_name} , {SP} {date1} {SP} {time_of_day} {SP} {GMT} )"

# asctime-date = day-name SP date3 SP time-of-day SP year

asctime_date = rf"(?: {day_name} {SP} {date3} {SP} {time_of_day} {SP} {year} )"

# rfc850-date = day-name-l "," SP date2 SP time-of-day SP GMT

rfc850_date = rf"(?: {day_name_l} \, {SP} {date2} {SP} {time_of_day} {SP} {GMT} )"

# obs-date = rfc850-date / asctime-date

obs_date = rf"(?: {rfc850_date} | {asctime_date} )"

# HTTP-date = IMF-fixdate / obs-date

HTTP_date = rf"(?: {IMF_fixdate} | {obs_date} )"


## Headers

# weight = OWS ";" OWS "q=" qvalue

weight = rf"(?: {OWS} \; {OWS} q\= {qvalue} )"

# accept-ext = OWS ";" OWS token [ "=" ( token / quoted-string ) ]

accept_ext = rf"(?: {OWS} ; {OWS} {token} (?: \= (?: {token} | {quoted_string} ) )? )"

# accept-params = weight *accept-ext

accept_params = rf"(?: {weight} {accept_ext}* )"

# type = token

_type = token

# subtype = token

subtype = token

# media-range = ( "*/*" / ( type "/*" ) / ( type "/" subtype ) ) *( OWS ";" OWS parameter )

media_range = rf"(?: (?: \*/\* | (?: {_type} /\* ) | (?: {_type} / {subtype} ) ) ( {OWS} ; {OWS} {parameter} )* )"

# Accept = #( media-range [ accept-params ] )

Accept = list_rule(rf"(?: {media_range} (?: {accept_params} )? )")

# charset = token

charset = token

# Accept-Charset = 1#( ( charset / "*" ) [ weight ] )

Accept_Charset = list_rule(rf"(?: (?: {charset} | \* ) {weight}? )", 1)

# content-coding = token

content_coding = token

# codings = content-coding / "identity" / "*"

codings = rf"(?: {content_coding} | identity | \* )"

# Accept-Encoding  = #( codings [ weight ] )

Accept_Encoding = list_rule(rf"(?: {codings} {weight}? )")

# language-range = <language-range, see [RFC4647], Section 2.1>
# language-range   = (1*8ALPHA *("-" 1*8alphanum)) / "*"
# alphanum         = ALPHA / DIGIT

language_range = (
    rf"(?: (?: {ALPHA}{{1,8}} (?: \- (?: {ALPHA} {DIGIT} ){{1,8}} )* ) | \* )"
)

# Accept-Language = 1#( language-range [ weight ] )

Accept_Language = list_rule(rf"(?: {language_range} {weight}? )", 1)

# method = token

method = token

# Allow = #method

Allow = list_rule(method)

# Content-Encoding = 1#content-coding

Content_Encoding = list_rule(content_coding, 1)

# language-tag = <Language-Tag, see [RFC5646], Section 2.1>

# Content-Language = 1#language-tag

Content_Language = list_rule(language_tag, 1)

# Content-Location = absolute-URI / partial-URI

Content_Location = rf"(?: {absolute_URI} | {partial_URI} )"

# media-type = type "/" subtype *( OWS ";" OWS parameter )

media_type = rf"(?: {_type} / {subtype} (?: {OWS} ; {OWS} {parameter} )* )"

# Content-Type = media-type

Content_Type = media_type

# Date = HTTP-date

Date = HTTP_date

# Expect = "100-continue"

Expect = r"(?: 100\-continue )"

# From = mailbox

From = mailbox

# Location = URI-reference

Location = URI_reference

# Max-Forwards = 1*DIGIT

Max_Forwards = rf"(?: {DIGIT}+ )"

# Referer = absolute-URI / partial-URI

Referer = rf"(?: {absolute_URI} | {partial_URI} )"

# delay-seconds = 1*DIGIT

delay_seconds = rf"(?: {DIGIT}+ )"

# Retry-After = HTTP-date / delay-seconds

Retry_After = rf"(?: {HTTP_date} | {delay_seconds} )"

# product-version = token

product_version = token

# product = token [ "/" product-version ]

product = rf"(?: {token} (?: / {product_version} )? )"

# Server = product *( RWS ( product / comment ) )

Server = rf"(?: {product} (?: {RWS} (?: {product} | {comment} ) )* )"

# User-Agent = product *( RWS ( product / comment ) )

User_Agent = rf"(?: {product} (?: {RWS} (?: {product} | {comment} ) )* )"

# Vary = "*" / 1#field-name

Vary = rf"(?: \* | {list_rule(field_name, 1)} )"
