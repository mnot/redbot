# pylint: disable=line-too-long, unused-import

"""
Regex for RFC7233

These regex are directly derived from the collected ABNF in RFC7233.

  <http://httpwg.org/specs/rfc7233.html#collected.abnf>

They should be processed with re.VERBOSE.
"""

from .rfc5234 import DIGIT, SP, VCHAR
from .rfc7230 import list_rule, OWS, token
from .rfc7231 import HTTP_date
from .rfc7232 import entity_tag

SPEC_URL = "http://httpwg.org/specs/rfc7233"


# bytes-unit = "bytes"

bytes_unit = r"bytes"

# other-range-unit = token

other_range_unit = token

# range-unit = bytes-unit / other-range-unit

range_unit = r"(?: {bytes_unit} | {other_range_unit} )".format(**locals())

# acceptable-ranges = 1#range-unit / "none"

acceptable_ranges = r"(?: %s | none )" % list_rule(range_unit, 1)

# Accept-Ranges = acceptable-ranges

Accept_Ranges = acceptable_ranges

# first-byte-pos = 1*DIGIT

first_byte_pos = r"{DIGIT}+".format(**locals())

# last-byte-pos = 1*DIGIT

last_byte_pos = r"{DIGIT}+".format(**locals())

# byte-range = first-byte-pos "-" last-byte-pos

byte_range = r"(?: {first_byte_pos} \- {last_byte_pos} )".format(**locals())

# complete-length = 1*DIGIT

complete_length = r"{DIGIT}+".format(**locals())

# byte-range-resp = byte-range "/" ( complete-length / "*" )

byte_range_resp = r"(?: {byte_range} / (?: {complete_length} | \* ) )".format(
    **locals()
)

# unsatisfied-range = "*/" complete-length

unsatisfied_range = r"(?: \*/ {complete_length} )".format(**locals())

# byte-content-range = bytes-unit SP ( byte-range-resp / unsatisfied-range )

byte_content_range = (
    r"(?: {bytes_unit} {SP} (?: {byte_range_resp} | {unsatisfied_range} )  )".format(
        **locals()
    )
)

# other-range-resp = *CHAR

other_range_resp = r"{VCHAR}*".format(**locals())

# other-content-range = other-range-unit SP other-range-resp

other_content_range = r"(?: {other_range_unit} {SP} {other_range_resp} )".format(
    **locals()
)

# Content-Range = byte-content-range / other-content-range

Content_Range = r"(?: {byte_content_range} | {other_content_range} )".format(**locals())

# If-Range = entity-tag / HTTP-date

If_Range = r"(?: {entity_tag} | {HTTP_date} )".format(**locals())

# suffix-length = 1*DIGIT

suffix_length = r"{DIGIT}+".format(**locals())

# suffix-byte-range-spec = "-" suffix-length

suffix_byte_range_spec = r"(?: \- {suffix_length} )+".format(**locals())

# byte-range-spec = first-byte-pos "-" [ last-byte-pos ]

byte_range_spec = r"(?: {first_byte_pos} \- {last_byte_pos} )+".format(**locals())

# byte-range-set = 1#( byte-range-spec / suffix-byte-range-spec )

byte_range_set = list_rule(
    r"(?: {byte_range_spec} | {suffix_byte_range_spec} )".format(**locals()), 1
)

# byte-ranges-specifier = bytes-unit "=" byte-range-set

byte_ranges_specifier = r"(?: {bytes_unit} = {byte_range_set} )+".format(**locals())

# other-range-set = 1*VCHAR

other_range_set = r"{VCHAR}+".format(**locals())

# other-ranges-specifier = other-range-unit "=" other-range-set

other_ranges_specifier = r"(?: {other_range_unit} = {other_range_set} )+".format(
    **locals()
)

# Range = byte-ranges-specifier / other-ranges-specifier

Range = r"(?: {byte_ranges_specifier} | {other_ranges_specifier} )".format(**locals())
