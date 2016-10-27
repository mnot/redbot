# pylint: disable=line-too-long, unused-import

"""
Regex for RFC7231

These regex are directly derived from the collected ABNF in RFC7231.

  <http://httpwg.org/specs/rfc7231.html#collected.abnf>

They should be processed with re.VERBOSE.
"""

from .rfc3986 import URI_reference, absolute_URI
from .rfc5322 import mailbox
from .rfc5234 import DIGIT, SP, ALPHA
from .rfc5646 import Language_Tag as language_tag
from .rfc7230 import list_rule, BWS, OWS, RWS, field_name, quoted_string, partial_URI, comment, token

SPEC_URL = "http://httpwg.org/specs/rfc7231"

## Basics

# parameter = token "=" ( token / quoted-string )

parameter = r"(?: {token} = (?: {token} | {quoted_string} ) )".format(**locals())

# qvalue = ( "0" [ "." *3DIGIT ] ) / ( "1" [ "." *3"0" ] )

qvalue = r"(?: (?: 0 (: \. {DIGIT}{{,3}} ) ) | (?: 1 (: \. [0]{{,3}} ) ) )".format(**locals())



## Dates

# second = 2DIGIT

second = r"(?: {DIGIT} {DIGIT} )".format(**locals())

# minute = 2DIGIT

minute = r"(?: {DIGIT} {DIGIT} )".format(**locals())

# hour = 2DIGIT

hour = r"(?: {DIGIT} {DIGIT} )".format(**locals())

# time-of-day = hour ":" minute ":" second

time_of_day = r"(?: {hour} : {minute} : {second} )".format(**locals())

# day = 2DIGIT

day = r"(?: {DIGIT} {DIGIT} )".format(**locals())

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

day_name_l = r"(?: Monday | Tuesday | Wednesday | Thursday | Friday | Saturday | Sunday )"

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

year = r"(?: {DIGIT}{{4}} )".format(**locals())

# GMT = %x47.4D.54 ; GMT

GMT = r"(?: GMT )"

# date1 = day SP month SP year

date1 = r"(?: {day} {SP} {month} {SP} {year} )".format(**locals())

# date2 = day "-" month "-" 2DIGIT

date2 = r"(?: {day} \- {month} \- {DIGIT}{{2}} )".format(**locals())

# date3 = month SP ( 2DIGIT / ( SP DIGIT ) )

date3 = r"(?: {month} {SP} (?: {DIGIT}{{2}} | (?: {SP} {DIGIT} ) ) )".format(**locals())

# IMF-fixdate = day-name "," SP date1 SP time-of-day SP GMT

IMF_fixdate = r"(?: {day_name} , {SP} {date1} {SP} {time_of_day} {SP} {GMT} )".format(**locals())

# asctime-date = day-name SP date3 SP time-of-day SP year

asctime_date = r"(?: {day_name} {SP} {date3} {SP} {time_of_day} {SP} {year} )".format(**locals())

# rfc850-date = day-name-l "," SP date2 SP time-of-day SP GMT

rfc850_date = r"(?: {day_name_l} \, {SP} {date2} {SP} {time_of_day} {SP} {GMT} )".format(**locals())

# obs-date = rfc850-date / asctime-date

obs_date = r"(?: {rfc850_date} | {asctime_date} )".format(**locals())

# HTTP-date = IMF-fixdate / obs-date

HTTP_date = r"(?: {IMF_fixdate} | {obs_date} )".format(**locals())



## Headers

# weight = OWS ";" OWS "q=" qvalue

weight = r"(?: {OWS} \; {OWS} q\= {qvalue} )".format(**locals())

# accept-ext = OWS ";" OWS token [ "=" ( token / quoted-string ) ]

accept_ext = r"(?: {OWS} ; {OWS} {token} (?: \= (?: {token} | {quoted_string} ) )? )".format(**locals())

# accept-params = weight *accept-ext

accept_params = r"(?: {weight} {accept_ext}* )".format(**locals())

# type = token

_type = token

# subtype = token

subtype = token

# media-range = ( "*/*" / ( type "/*" ) / ( type "/" subtype ) ) *( OWS ";" OWS parameter )

media_range = r"(?: (?: \*/\* | (?: {_type} /\* ) | (?: {_type} / {subtype} ) ) ( {OWS} ; {OWS} {parameter} )* )".format(**locals())

# Accept = #( media-range [ accept-params ] )

Accept = list_rule(r"(?: {media_range} (?: {accept_params} )? )".format(**locals()))

# charset = token

charset = token

# Accept-Charset = 1#( ( charset / "*" ) [ weight ] )

Accept_Charset = list_rule(r"(?: (?: {charset} | \* ) {weight}? )".format(**locals()), 1)

# content-coding = token

content_coding = token

# codings = content-coding / "identity" / "*"

codings = r"(?: {content_coding} | identity | \* )".format(**locals())

# Accept-Encoding  = #( codings [ weight ] )

Accept_Encoding = list_rule(r"(?: {codings} {weight}? )".format(**locals()))

# language-range = <language-range, see [RFC4647], Section 2.1>
# language-range   = (1*8ALPHA *("-" 1*8alphanum)) / "*"
# alphanum         = ALPHA / DIGIT

language_range = r"(?: (?: {ALPHA}{{1,8}} (?: \- (?: {ALPHA} {DIGIT} ){{1,8}} )* ) | \* )".format(**locals())

# Accept-Language = 1#( language-range [ weight ] )

Accept_Language = list_rule(r"(?: {language_range} {weight}? )".format(**locals()), 1)

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

Content_Location = r"(?: {absolute_URI} | {partial_URI} )".format(**locals())

# media-type = type "/" subtype *( OWS ";" OWS parameter )

media_type = r"(?: {_type} / {subtype} (?: {OWS} ; {OWS} {parameter} )* )".format(**locals())

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

Max_Forwards = r"(?: {DIGIT}+ )".format(**locals())

# Referer = absolute-URI / partial-URI

Referer = r"(?: {absolute_URI} | {partial_URI} )".format(**locals())

# delay-seconds = 1*DIGIT

delay_seconds = r"(?: {DIGIT}+ )".format(**locals())

# Retry-After = HTTP-date / delay-seconds

Retry_After = r"(?: {HTTP_date} | {delay_seconds} )".format(**locals())

# product-version = token

product_version = token

# product = token [ "/" product-version ]

product = r"(?: {token} (?: / {product_version} )? )".format(**locals())

# Server = product *( RWS ( product / comment ) )

Server = r"(?: {product} (?: {RWS} (?: {product} | {comment} ) )* )".format(**locals())

# User-Agent = product *( RWS ( product / comment ) )

User_Agent = r"(?: {product} (?: {RWS} (?: {product} | {comment} ) )* )".format(**locals())

# Vary = "*" / 1#field-name

Vary = r"(?: \* | %s )" % list_rule(field_name, 1)
