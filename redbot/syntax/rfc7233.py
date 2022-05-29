"""
Regex for RFC7233

These regex are directly derived from the collected ABNF in RFC7233.

  <http://httpwg.org/specs/rfc7233.html#collected.abnf>

They should be processed with re.VERBOSE.
"""

# pylint: disable=invalid-name


from .rfc5234 import DIGIT, SP, VCHAR
from .rfc7230 import list_rule, token
from .rfc7231 import HTTP_date
from .rfc7232 import entity_tag

SPEC_URL = "http://httpwg.org/specs/rfc7233"


# bytes-unit = "bytes"

bytes_unit = r"bytes"

# other-range-unit = token

other_range_unit = token

# range-unit = bytes-unit / other-range-unit

range_unit = rf"(?: {bytes_unit} | {other_range_unit} )"

# acceptable-ranges = 1#range-unit / "none"

acceptable_ranges = rf"(?: {list_rule(range_unit, 1)} | none )"

# Accept-Ranges = acceptable-ranges

Accept_Ranges = acceptable_ranges

# first-byte-pos = 1*DIGIT

first_byte_pos = rf"{DIGIT}+"

# last-byte-pos = 1*DIGIT

last_byte_pos = rf"{DIGIT}+"

# byte-range = first-byte-pos "-" last-byte-pos

byte_range = rf"(?: {first_byte_pos} \- {last_byte_pos} )"

# complete-length = 1*DIGIT

complete_length = rf"{DIGIT}+"

# byte-range-resp = byte-range "/" ( complete-length / "*" )

byte_range_resp = rf"(?: {byte_range} / (?: {complete_length} | \* ) )"

# unsatisfied-range = "*/" complete-length

unsatisfied_range = rf"(?: \*/ {complete_length} )"

# byte-content-range = bytes-unit SP ( byte-range-resp / unsatisfied-range )

byte_content_range = (
    rf"(?: {bytes_unit} {SP} (?: {byte_range_resp} | {unsatisfied_range} )  )"
)

# other-range-resp = *CHAR

other_range_resp = rf"{VCHAR}*"

# other-content-range = other-range-unit SP other-range-resp

other_content_range = rf"(?: {other_range_unit} {SP} {other_range_resp} )"

# Content-Range = byte-content-range / other-content-range

Content_Range = rf"(?: {byte_content_range} | {other_content_range} )"

# If-Range = entity-tag / HTTP-date

If_Range = rf"(?: {entity_tag} | {HTTP_date} )"

# suffix-length = 1*DIGIT

suffix_length = rf"{DIGIT}+"

# suffix-byte-range-spec = "-" suffix-length

suffix_byte_range_spec = rf"(?: \- {suffix_length} )+"

# byte-range-spec = first-byte-pos "-" [ last-byte-pos ]

byte_range_spec = rf"(?: {first_byte_pos} \- {last_byte_pos} )+"

# byte-range-set = 1#( byte-range-spec / suffix-byte-range-spec )

byte_range_set = list_rule(rf"(?: {byte_range_spec} | {suffix_byte_range_spec} )", 1)

# byte-ranges-specifier = bytes-unit "=" byte-range-set

byte_ranges_specifier = rf"(?: {bytes_unit} = {byte_range_set} )+"

# other-range-set = 1*VCHAR

other_range_set = rf"{VCHAR}+"

# other-ranges-specifier = other-range-unit "=" other-range-set

other_ranges_specifier = rf"(?: {other_range_unit} = {other_range_set} )+"

# Range = byte-ranges-specifier / other-ranges-specifier

Range = rf"(?: {byte_ranges_specifier} | {other_ranges_specifier} )"
