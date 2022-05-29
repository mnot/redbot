"""
Regex for RFC7230

These regex are directly derived from the collected ABNF in RFC7230:

  <http://httpwg.org/specs/rfc7230.html#collected.abnf>

They should be processed with re.VERBOSE.
"""

# pylint: disable=invalid-name, line-too-long

from .rfc5234 import (
    ALPHA,
    CRLF,
    DIGIT,
    HEXDIG,
    HTAB,
    OCTET,
    SP,
    VCHAR,
)
from .rfc3986 import (
    absolute_URI,
    authority,
    fragment,
    path_abempty,
    port,
    query,
    relative_part,
    segment,
    host as uri_host,
)

SPEC_URL = "http://httpwg.org/specs/rfc7230"


## Basics

# OWS = *( SP / HTAB )

OWS = rf"(?: {SP} | {HTAB} )*"

# BWS = OWS

BWS = OWS

# RWS = 1*( SP / HTAB )

RWS = rf"(?: {SP} | {HTAB} )+"

# obs-fold = CRLF 1*( SP / HTAB )

obs_fold = rf"(?: {CRLF} (?: {SP} | {HTAB} )+ )"

# obs-text = %x80-FF

obs_text = r"[\x80-\xff]"

# tchar = "!" / "#" / "$" / "%" / "&" / "'" / "*" / "+" / "-" / "." / "^" / "_" / "`" / "|" / "~" / DIGIT / ALPHA

tchar = rf"(?: ! | \# | \$ | % | & | ' | \* | \+ | \- | \. | \^ | _ | ` | \| | \~ | {DIGIT} | {ALPHA} )"

# token = 1*tchar

token = rf"{tchar}+"

# qdtext = HTAB / SP / "!" / %x23-5B ; '#'-'['
#  / %x5D-7E ; ']'-'~'
#  / obs-text

qdtext = r"[\t !\x23-\x5b\x5d-\x7e\x80-\xff]"

# quoted-pair = "\" ( HTAB / SP / VCHAR / obs-text )

quoted_pair = rf"(?: \\ (?: {HTAB} | {SP} | {VCHAR} | {obs_text} ) )"

# quoted-string = DQUOTE *( qdtext / quoted-pair ) DQUOTE

quoted_string = rf"(?: \" (?: {qdtext} | {quoted_pair} )* \" )"


class list_rule:
    """
    Given a piece of ABNF, wrap it in the "list rule"
    as per RFC7230, Section 7.

    <http://httpwg.org/specs/rfc7230.html#abnf.extension>

    Uses the sender syntax, not the more lenient recipient syntax.
    """

    def __init__(self, element: str, minimum: int = None) -> None:
        self.element = element
        self.minimum = minimum

    def __str__(self) -> str:
        if self.minimum == 1:
            # 1#element => element *( OWS "," OWS element )
            return r"(?: {element} (?: {OWS} , {OWS} {element} )* )".format(
                element=self.element, OWS=OWS
            )
        if self.minimum > 1:
            # <n>#<m>element => element <n-1>*<m-1>( OWS "," OWS element )
            adj_min = self.minimum - 1
            return (
                r"(?: {element} (?: {OWS} , {OWS} {element} ){{{adj_min},}} )".format(
                    element=self.element, OWS=OWS, adj_min=adj_min
                )
            )
        # element => [ 1#element ]
        return r"(?: {element} (?: {OWS} , {OWS} {element} )* )?".format(
            element=self.element, OWS=OWS
        )


## Header Definitions

# connection-option = token

connection_option = token

# Connection = 1#connection-option

Connection = list_rule(connection_option, 1)

# Content-Length = 1*DIGIT

Content_Length = rf"{DIGIT}+"

# Host = uri-host [ ":" port ]

Host = rf"{uri_host} (?: : {port} )?"

# transfer-parameter = token BWS "=" BWS ( token / quoted-string )

transfer_parameter = rf"(?: {token} {BWS} = {BWS} (?: {token} | {quoted_string} ) )"

# transfer-extension = token *( OWS ";" OWS transfer-parameter )

transfer_extension = rf"(?: {token} (?: {OWS} ; {OWS} {transfer_parameter} )* )"

# rank = ( "0" [ "." *3DIGIT ] ) / ( "1" [ "." *3"0" ] )

rank = rf"(?: 0 (?: \. {DIGIT}{{,3}} ) | (?: 1 \. [0]{{,3}} ) )"

# t-ranking = OWS ";" OWS "q=" rank

t_ranking = rf"(?: {OWS} \; {OWS} q\= {rank} )"

# transfer-coding = "chunked" / "compress" / "deflate" / "gzip" / transfer-extension

transfer_coding = rf"(?: chunked | compress | deflate | gzip | {transfer_extension} )"

# t-codings = "trailers" / ( transfer-coding [ t-ranking ] )

t_codings = rf"(?: trailers | (?: {transfer_coding} (?: {t_ranking}? ) ) )"

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

protocol = rf"(?: {protocol_name} (?: {protocol_version} )? )"

# Upgrade = 1#protocol

Upgrade = list_rule(protocol, 1)

# pseudonym = token

pseudonym = token

# received-by = ( uri-host [ ":" port ] ) / pseudonym

received_by = rf"(?: (?: {uri_host} (?: : {port} )? ) | {pseudonym} )"

# received-protocol = [ protocol-name "/" ] protocol-version

received_protocol = rf"(?: (?: {protocol_name} / )? {protocol_version} )"

# ctext = HTAB / SP / %x21-27 ; '!'-'''
#  / %x2A-5B ; '*'-'['
#  / %x5D-7E ; ']'-'~'
#  / obs-text

ctext = rf"(?: {HTAB} | {SP} | [\x21-\x27] | [\x2A-\x5b] | \x5D-\x7E | {obs_text} )"

# comment = "(" *( ctext / quoted-pair / comment ) ")"

comment = rf"(?: \( (?: {ctext} | {quoted_pair} )* \) ) "

# Via = 1#( received-protocol RWS received-by [ RWS comment ] )

Via = list_rule(
    rf"(?: {received_protocol} {RWS} {received_by} (?: {RWS} {comment} )? )",
    1,
)


## Headers (generic)

# field-vchar = VCHAR / obs-text

field_vchar = rf"(?: {VCHAR} | {obs_text} )"

# field-content = field-vchar [ 1*( SP / HTAB ) field-vchar ]

field_content = rf"(?: {field_vchar} (?: (?: {SP} | {HTAB} )+ {field_vchar} )? )"

# field-value = *( field-content / obs-fold )

field_value = rf"(?: {field_content} | {obs_fold} )*"

# header-field = field-name ":" OWS field-value OWS

header_field = rf"(?: {field_name} : {OWS} {field_value} {OWS} )"


## Chunked Encoding

# chunk-size = 1*HEXDIG

chunk_size = rf"(?: {HEXDIG}+ )"

# chunk-ext-name = token

chunk_ext_name = token

# chunk-ext-val = token / quoted-string

chunk_ext_val = rf"(?: {token} | {quoted_string} )"

# chunk-ext = *( ";" chunk-ext-name [ "=" chunk-ext-val ] )

chunk_ext = rf"(?: \; {chunk_ext_name} (?: \= {chunk_ext_val} )? )"

# chunk-data = 1*OCTET

chunk_data = rf"{OCTET}+"

# chunk = chunk-size [ chunk-ext ] CRLF chunk-data CRLF

chunk = rf"(?: {chunk_size} (?: {chunk_ext} )? {CRLF} {chunk_data} {CRLF} )"

# last-chunk = 1*"0" [ chunk-ext ] CRLF

last_chunk = rf"(?: (?: 0 )+ (?: {chunk_ext} )? {CRLF} )"

# trailer-part = *( header-field CRLF )

trailer_part = rf"(?: {header_field} {CRLF} )*"

# chunked-body = *chunk last-chunk trailer-part CRLF

chunked_body = rf"(?: (?: chunk )* {last_chunk} {trailer_part} {CRLF} )"


## HTTP(S) URIs

# absolute-form = absolute-URI

absolute_form = absolute_URI

# absolute-path = 1*( "/" segment )

absolute_path = rf"(?: / {segment} )+"

# asterisk-form = "*"

asterisk_form = r"\*"

# authority-form = authority

authority_form = authority

# http-URI = "http://" authority path-abempty [ "?" query ] [ "#" fragment ]

http_URI = (
    rf"(?: http:// {authority} {path_abempty} (?: \? {query} )? (?: \# {fragment} )? )"
)

# https-URI = "https://" authority path-abempty [ "?" query ] [ "#" fragment ]

https_URI = (
    rf"(?: https:// {authority} {path_abempty} (?: \? {query} )? (?: \# {fragment} )? )"
)

# origin-form = absolute-path [ "?" query ]

origin_form = rf"(?: {absolute_path} (?: {query} )? )"

# partial-URI = relative-part [ "?" query ]

partial_URI = rf"(?: {relative_part} (?: {query} )? )"


## Message

# HTTP-name = %x48.54.54.50 ; HTTP

HTTP_name = r"HTTP"

# HTTP-version = HTTP-name "/" DIGIT "." DIGIT

HTTP_version = rf"{HTTP_name} / {DIGIT} . {DIGIT}"

# method = token

method = token

# request-target = origin-form / absolute-form / authority-form / asterisk-form

request_target = (
    rf"(?: {origin_form} | {absolute_form} | {authority_form} | {asterisk_form} )"
)

# request-line = method SP request-target SP HTTP-version CRLF

request_line = rf"(?: {method} [ ] {request_target} [ ] {HTTP_version} {CRLF} )"

# status-code = 3DIGIT

status_code = rf"(?: {DIGIT}{{3}} )"

# reason-phrase = *( HTAB / SP / VCHAR / obs-text )

reason_phrase = rf"(?: {HTAB} | {SP} | {VCHAR} | {obs_text} )*"

# status-line = HTTP-version SP status-code SP reason-phrase CRLF

status_line = rf"(?: {HTTP_version} [ ] {status_code} [ ] {reason_phrase} {CRLF} )"

# start-line = request-line / status-line

start_line = rf"(?: {request_line} | {status_line} )"

# message-body = *OCTET

message_body = rf"(?: {OCTET}* )"

# HTTP-message = start-line *( header-field CRLF ) CRLF [ message-body ]

HTTP_message = (
    rf"(?: {start_line} (?: {header_field} {CRLF} )* {CRLF} (?: {message_body} )? )"
)
