
"""
Regex for RFC7230

These regex are directly derived from the collected ABNF in RFC7230:

  <http://httpwg.org/specs/rfc7230.html#collected.abnf>

They should be processed with re.VERBOSE.
"""

from rfc5234 import ALPHA, CR, LF, CRLF, CTL, DIGIT, DQUOTE, HEXDIG, HTAB, OCTET, SP, VCHAR
from rfc3986 import URI_reference, absolute_URI, authority, fragment, path_abempty, port, query, relative_part, scheme, segment, host as uri_host


## Basics

# OWS = *( SP / HTAB )

OWS = r"(?: {SP} | {HTAB} )*".format(**locals())

# BWS = OWS

BWS = OWS

# RWS = 1*( SP / HTAB )

RWS = r"(?: {SP} | {HTAB} )+".format(**locals())

# obs-fold = CRLF 1*( SP / HTAB )

obs_fold = r"(?: {CRLF} (?: {SP} | {HTAB} )+ )".format(**locals())

# obs-text = %x80-FF

obs_text = r"[\x80-\xff]"

# tchar = "!" / "#" / "$" / "%" / "&" / "'" / "*" / "+" / "-" / "." / "^" / "_" / "`" / "|" / "~" / DIGIT / ALPHA

tchar = r"(?: ! | # | \$ | %% | & | ' | \* | \+ | - | . | \^ | _ | ` | \| | ~ | {DIGIT} | {ALPHA} )".format(**locals())

# token = 1*tchar

token = r"{tchar}+".format(**locals())

# qdtext = HTAB / SP / "!" / %x23-5B ; '#'-'['
#  / %x5D-7E ; ']'-'~'
#  / obs-text

qdtext = r"[\t !\x23-\x5b\x5d-\x7e\x80-\xff]"

# quoted-pair = "\" ( HTAB / SP / VCHAR / obs-text )

quoted_pair = r"(?: \\ (?: {HTAB} | {SP} | {VCHAR} | {obs_text} ) )".format(**locals())

# quoted-string = DQUOTE *( qdtext / quoted-pair ) DQUOTE

quoted_string = r"\" (?: {qdtext} | {quoted_pair} )* \"".format(**locals())




def list_rule(element, min=None):
    """
    Given a piece of ABNF, wrap it in the "list rule" 
    as per RFC7230, Section 7.
    
    Uses the sender syntax, not the more lenient recipient syntax.
    """
    
    if min:
        min = r"?"
    else:
        min = r""
    
    # element *( OWS "," OWS element )
    return r"{element} (?: {OWS} , {OWS} {element} ){min}".format(element=element, OWS=OWS, min=min)



## Header Definitions

# connection-option = token

connection_option = token

# Connection = 1#connection-option

Connection = list_rule(connection_option, 1)

# Content-Length = 1*DIGIT

Content_Length = r"{DIGIT}+".format(**locals())
 
# Host = uri-host [ ":" port ]

Host = r"{uri_host} (?: : {port} )?".format(**locals())

# transfer-parameter = token BWS "=" BWS ( token / quoted-string )

transfer_parameter = r"(?: {token} {BWS} \= {BWS} (?: {token} | {quoted_string} ) )".format(**locals())

# transfer-extension = token *( OWS ";" OWS transfer-parameter )

transfer_extension = r"(?: {token} (?: {OWS} \; {OWS} (%tranfer_parameter) )* )".format(**locals())

# rank = ( "0" [ "." *3DIGIT ] ) / ( "1" [ "." *3"0" ] )

rank = r"(?: 0 (?: \. {DIGIT}{{,3}} ) | (?: 1 \. [0]{{,3}} ) )".format(**locals())

# t-ranking = OWS ";" OWS "q=" rank

t_ranking = r"(?: {OWS} \; {OWS} q\= {rank} )".format(**locals())

# transfer-coding = "chunked" / "compress" / "deflate" / "gzip" / transfer-extension

transfer_coding = r"(?: chunked | compress | deflate | gzip | {transfer_extension} )".format(**locals())

# t-codings = "trailers" / ( transfer-coding [ t-ranking ] )

t_codings = r"(?: trailers | (?: {transfer_coding} (?: {t_ranking}? ) ) )".format(**locals())
 
# TE = #t-codings

TE = list_rule(t_codings)

# field-name = token

field_name = token

# Trailer = 1#field-name

Trailer = list_rule(field_name, 1)

# Transfer-Encoding = 1#transfer-coding

Transfer_Encoding = list_rule(transfer_coding, 1)

# protocol-name = token

protocol_name = token

# protocol-version = token

protocol_version = token

# protocol = protocol-name [ "/" protocol-version ]

protocol = r"(?: {protocol_name} (?: %(protocol-version) )? )".format(**locals())
 
# Upgrade = 1#protocol

Upgrade = list_rule(protocol, 1)

# pseudonym = token

pseudonym = token

# received-by = ( uri-host [ ":" port ] ) / pseudonym

received_by = r"(?: (?: {uri_host} (?: : {port} )? ) | {pseudonym} )".format(**locals())

# received-protocol = [ protocol-name "/" ] protocol-version

received_protocol = r"(?: (?: {protocol_name} )? / {protocol_version} )".format(**locals())

# ctext = HTAB / SP / %x21-27 ; '!'-'''
#  / %x2A-5B ; '*'-'['
#  / %x5D-7E ; ']'-'~'
#  / obs-text

ctext = r"(?: {HTAB} | {SP} | [\x21-\x27] | [\x2A-\x5b] | \x5D-\x7E | {obs_text} )".format(**locals())
 
# comment = "(" *( ctext / quoted-pair / comment ) ")"

comment = r"(?: (?: {ctext} | {quoted_pair} )* ) ".format(**locals())
# FIXME: handle recursive comments - see <https://pypi.python.org/pypi/regex/>

# Via = 1#( received-protocol RWS received-by [ RWS comment ] )

Via = list_rule( r"(?: {received_protocol} {RWS} {received_by} (?: {RWS} {comment} ) )".format(**locals()), 1)




## Headers (generic)

# field-vchar = VCHAR / obs-text

field_vchar = r"(?: {VCHAR} | {obs_text} )".format(**locals())

# field-content = field-vchar [ 1*( SP / HTAB ) field-vchar ]

field_content = r"(?: {field_vchar} (?: (?: {SP} | {HTAB} )+ {field_vchar} )? )".format(**locals())

# field-value = *( field-content / obs-fold )

field_value = r"(?: {field_content} | {obs_fold} )*".format(**locals())
 
# header-field = field-name ":" OWS field-value OWS

header_field = r"(?: {field_name} : {OWS} {field_value} {OWS} )".format(**locals())




## Chunked Encoding

# chunk-size = 1*HEXDIG

chunk_size =  r"(?: {HEXDIG}+ )".format(**locals())

# chunk-ext-name = token

chunk_ext_name = token

# chunk-ext-val = token / quoted-string

chunk_ext_val = r"(?: {token} | {quoted_string} )".format(**locals())

# chunk-ext = *( ";" chunk-ext-name [ "=" chunk-ext-val ] )

chunk_ext = r"(?: \; {chunk_ext_name} (?: \= {chunk_ext_val} )? )".format(**locals())

# chunk-data = 1*OCTET

chunk_data = r"{OCTET}+".format(**locals())
 
# chunk = chunk-size [ chunk-ext ] CRLF chunk-data CRLF

chunk = r"(?: {chunk_size} (?: {chunk_ext} )? {CRLF} {chunk_data} {CRLF} )".format(**locals())

# last-chunk = 1*"0" [ chunk-ext ] CRLF

last_chunk = r"(?: (?: 0 )+ (?: {chunk_ext} )? {CRLF} )".format(**locals())

# trailer-part = *( header-field CRLF )

trailer_part = r"(?: {header_field} {CRLF} )*".format(**locals())

# chunked-body = *chunk last-chunk trailer-part CRLF

chunked_body = r"(?: (?: chunk )* {last_chunk} {trailer_part} {CRLF} )".format(**locals())




## HTTP(S) URIs

# absolute-form = absolute-URI

absolute_form = absolute_URI

# absolute-path = 1*( "/" segment )

absolute_path = r"(?: / {segment} )+".format(**locals())

# asterisk-form = "*"

asterisk_form = r"\*"

# authority-form = authority

authority_form = authority

# http-URI = "http://" authority path-abempty [ "?" query ] [ "#" fragment ]

http_URI = r"(?: http:// {authority} {path_abempty} (?: \? {query} )? (?: \# {fragment} )? )".format(**locals())

# https-URI = "https://" authority path-abempty [ "?" query ] [ "#" fragment ]

https_URI = r"(?: https:// {authority} {path_abempty} (?: \? {query} )? (?: \# {fragment} )? )".format(**locals())

# origin-form = absolute-path [ "?" query ]

origin_form = r"(?: {absolute_path} (?: {query} )? )".format(**locals())
 
# partial-URI = relative-part [ "?" query ]

partial_URI = r"(?: {relative_part} (?: {query} )? )".format(**locals())




## Message

# HTTP-name = %x48.54.54.50 ; HTTP

HTTP_name = r"HTTP"

# HTTP-version = HTTP-name "/" DIGIT "." DIGIT

HTTP_version = r"{HTTP_name} / {DIGIT} . {DIGIT}".format(**locals())

# method = token

method = token

# request-target = origin-form / absolute-form / authority-form / asterisk-form

request_target = r"(?: {origin_form} | {absolute_form} | {authority_form} | {asterisk_form} )".format(**locals())

# request-line = method SP request-target SP HTTP-version CRLF

request_line = r"(?: {method} [ ] {request_target} [ ] {HTTP_version} {CRLF} )".format(**locals())

# status-code = 3DIGIT

status_code = r"(?: {DIGIT}{{3}} )".format(**locals())

# reason-phrase = *( HTAB / SP / VCHAR / obs-text )

reason_phrase = r"(?: {HTAB} | {SP} | {VCHAR} | {obs_text} )*".format(**locals())

# status-line = HTTP-version SP status-code SP reason-phrase CRLF

status_line = r"(?: {HTTP_version} [ ] {status_code} [ ] {reason_phrase} {CRLF} )".format(**locals())

# start-line = request-line / status-line

start_line = r"(?: {request_line} | {status_line} )".format(**locals())

# message-body = *OCTET

message_body = r"(?: {OCTET}* )".format(**locals())
 
# HTTP-message = start-line *( header-field CRLF ) CRLF [ message-body ]

HTTP_message = r"(?: {start_line} (?: {header_field} {CRLF} )* {CRLF} (?: {message_body} )? )".format(**locals())

