#!/usr/bin/env python


from calendar import timegm
from re import match, split
from urllib.parse import urlsplit
from typing import List, Tuple, Union

from redbot.message import headers
from redbot.speak import Note, categories, levels
from redbot.type import AddNoteMethodType

CookieType = Tuple[str, str, List[Tuple[str, Union[str, int]]]]


class set_cookie(headers.HttpHeader):
    canonical_name = "Set-Cookie"
    description = """\
The `Set-Cookie` response header sets a stateful "cookie" on the client, to be included in future
requests to the server."""
    syntax = False
    reference = headers.rfc6265
    list_header = False
    nonstandard_syntax = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True

    def parse(self, field_value: str, add_note: AddNoteMethodType) -> CookieType:
        path = urlsplit(self.message.base_uri).path
        start_time = self.message.start_time
        try:
            set_cookie_value = loose_parse(field_value, path, start_time, add_note)
        except ValueError:
            raise
        return set_cookie_value


# TODO: properly escape notes
def loose_parse(
    set_cookie_string: str,
    uri_path: str,
    current_time: float,
    add_note: AddNoteMethodType,
) -> CookieType:
    """
    Parse a Set-Cookie string, as per RFC6265, Section 5.2.
    """
    name = "Set-Cookie"
    if ";" in set_cookie_string:
        name_value_pair, unparsed_attributes = set_cookie_string.split(";", 1)
    else:
        name_value_pair, unparsed_attributes = set_cookie_string, ""
    try:
        name, value = name_value_pair.split("=", 1)
    except ValueError:
        add_note(SET_COOKIE_NO_VAL)
        raise ValueError("Cookie doesn't have a value")
    name, value = name.strip(), value.strip()
    if name == "":
        add_note(SET_COOKIE_NO_NAME)
        raise ValueError("Cookie doesn't have a name")
    cookie_name, cookie_value = name, value
    cookie_attribute_list = []  # type: List[Tuple[str, Union[str, int]]]
    while unparsed_attributes != "":
        if ";" in unparsed_attributes:
            cookie_av, unparsed_attributes = unparsed_attributes.split(";", 1)
        else:
            cookie_av, unparsed_attributes = unparsed_attributes, ""
        if "=" in cookie_av:
            attribute_name, attribute_value = cookie_av.split("=", 1)
        else:
            attribute_name, attribute_value = cookie_av, ""
        attribute_name = attribute_name.strip()
        attribute_value = attribute_value.strip()
        case_norm_attribute_name = attribute_name.lower()
        if case_norm_attribute_name == "expires":
            try:
                expiry_time = loose_date_parse(attribute_value)
            except ValueError as why:
                add_note(SET_COOKIE_BAD_DATE, why=why, cookie_name=cookie_name)
                continue
            cookie_attribute_list.append(("Expires", expiry_time))
        elif case_norm_attribute_name == "max-age":
            if attribute_value == "":
                add_note(SET_COOKIE_EMPTY_MAX_AGE, cookie_name=cookie_name)
                continue
            if attribute_value[0] == "0":
                add_note(SET_COOKIE_LEADING_ZERO_MAX_AGE, cookie_name=cookie_name)
                continue
            if not attribute_value.isdigit():
                add_note(SET_COOKIE_NON_DIGIT_MAX_AGE, cookie_name=cookie_name)
                continue
            delta_seconds = int(attribute_value)
            cookie_attribute_list.append(("Max-Age", delta_seconds))
        elif case_norm_attribute_name == "domain":
            if attribute_value == "":
                add_note(SET_COOKIE_EMPTY_DOMAIN, cookie_name=cookie_name)
                continue
            elif attribute_value[0] == ".":
                cookie_domain = attribute_value[1:]
            else:
                cookie_domain = attribute_value
            cookie_attribute_list.append(("Domain", cookie_domain))
        elif case_norm_attribute_name == "path":
            if attribute_value == "" or attribute_value[0] != "/":
                # use default path
                if uri_path == "" or uri_path[0] != "/":
                    cookie_path = "/"
                if uri_path.count("/") < 2:
                    cookie_path = "/"
                else:
                    cookie_path = uri_path[: uri_path.rindex("/")]
            else:
                cookie_path = attribute_value
            cookie_attribute_list.append(("Path", cookie_path))
        elif case_norm_attribute_name == "secure":
            cookie_attribute_list.append(("Secure", ""))
        elif case_norm_attribute_name == "httponly":
            cookie_attribute_list.append(("HttpOnly", ""))
        else:
            add_note(
                SET_COOKIE_UNKNOWN_ATTRIBUTE,
                cookie_name=cookie_name,
                attribute=attribute_name,
            )
    return (cookie_name, cookie_value, cookie_attribute_list)


DELIMITER = r"(?:[\x09\x20-\x2F\x3B-\x40\x5B-\x60\x7B-\x7E])"
NON_DELIMITER = r"(?:[\x00-\x08\x0A-\x1F0-0\:a-zA-Z\x7F-\xFF])"
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def loose_date_parse(cookie_date: str) -> int:
    """
    Parse a date, as per RFC 6265, Section 5.1.1.
    """
    found_time = found_day_of_month = found_month = found_year = False
    hour_value = minute_value = second_value = None
    day_of_month_value = month_value = year_value = None
    date_tokens = split(DELIMITER, cookie_date)
    for date_token in date_tokens:
        re_match = None
        if not found_time:
            re_match = match(r"^(\d{2}:\d{2}:\d{2})(?:\D)?", date_token)
            if re_match:
                found_time = True
                hour_value, minute_value, second_value = [
                    int(v) for v in re_match.group(1).split(":")
                ]
                continue
        if not found_day_of_month:
            re_match = match(r"^(\d\d?)(?:\D)?", date_token)
            if re_match:
                found_day_of_month = True
                day_of_month_value = int(re_match.group(1))
                continue
        if not found_month and date_token[:3].lower() in list(MONTHS.keys()):
            found_month = True
            month_value = MONTHS[date_token[:3].lower()]
            continue
        if not found_year:
            re_match = match(r"^(\d{2,4})(?:\D)?", date_token)
            if re_match:
                found_year = True
                year_value = int(re_match.group(1))
                continue
    if False in [found_time, found_day_of_month, found_month, found_year]:
        missing = []
        if not found_time:
            missing.append("time")
        if not found_day_of_month:
            missing.append("day")
        if not found_month:
            missing.append("month")
        if not found_year:
            missing.append("year")
        raise ValueError("didn't have a: %s" % ",".join(missing))
    if 99 >= year_value >= 70:
        year_value += 1900
    if 69 >= year_value >= 0:
        year_value += 2000
    if day_of_month_value < 1 or day_of_month_value > 31:
        raise ValueError("%s is out of range for day_of_month" % day_of_month_value)
    if year_value < 1601:
        raise ValueError("%s is out of range for year" % year_value)
    if hour_value > 23:
        raise ValueError("%s is out of range for hour" % hour_value)
    if minute_value > 59:
        raise ValueError("%s is out of range for minute" % minute_value)
    if second_value > 59:
        raise ValueError("%s is out of range for second" % second_value)
    parsed_cookie_date = timegm(
        (
            year_value,
            month_value,
            day_of_month_value,
            hour_value,
            minute_value,
            second_value,
        )
    )
    return parsed_cookie_date


class SET_COOKIE_NO_VAL(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "%(response)s has a Set-Cookie header that can't be parsed."
    text = """\
  This `Set-Cookie` header can't be parsed into a name and a value; it must start with a `name=value`
  structure.

  Browsers will ignore this cookie."""


class SET_COOKIE_NO_NAME(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "%(response)s has a Set-Cookie header without a cookie-name."
    text = """\
  This `Set-Cookie` header has an empty name; there needs to be a name before the `=`.

  Browsers will ignore this cookie."""


class SET_COOKIE_BAD_DATE(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "The %(cookie_name)s Set-Cookie header has an invalid Expires date."
    text = """\
  The `expires` date on this `Set-Cookie` header isn't valid; see
  [RFC6265](http://tools.ietf.org/html/rfc6265) for details of the correct format."""


class SET_COOKIE_EMPTY_MAX_AGE(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "The %(cookie_name)s Set-Cookie header has an empty Max-Age."
    text = """\
  The `max-age` parameter on this `Set-Cookie` header doesn't have a value.

  Browsers will ignore the `max-age` value as a result."""


class SET_COOKIE_LEADING_ZERO_MAX_AGE(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "The %(cookie_name)s Set-Cookie header has a Max-Age with a leading zero."
    text = """\
  The `max-age` parameter on this `Set-Cookie` header has a leading zero.

  Browsers will ignore the `max-age` value as a result."""


class SET_COOKIE_NON_DIGIT_MAX_AGE(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "The %(cookie_name)s Set-Cookie header has a non-numeric Max-Age."
    text = """\
  The `max-age` parameter on this `Set-Cookie` header isn't numeric.


  Browsers will ignore the `max-age` value as a result."""


class SET_COOKIE_EMPTY_DOMAIN(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "The %(cookie_name)s Set-Cookie header has an empty domain."
    text = """\
  The `domain` parameter on this `Set-Cookie` header is empty.

  Browsers will probably ignore it as a result."""


class SET_COOKIE_UNKNOWN_ATTRIBUTE(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "The %(cookie_name)s Set-Cookie header has an unknown attribute, '%(attribute)s'."
    text = """\
  This `Set-Cookie` header has an extra parameter, "%(attribute)s".

  Browsers will ignore it."""


class BasicSCTest(headers.HeaderTest):
    name = "Set-Cookie"
    inputs = [b"SID=31d4d96e407aad42"]
    expected_out = [("SID", "31d4d96e407aad42", [])]  # type: ignore
    expected_err = []  # type: ignore


class ParameterSCTest(headers.HeaderTest):
    name = "Set-Cookie"
    inputs = [b"SID=31d4d96e407aad42; Path=/; Domain=example.com"]
    expected_out = [
        ("SID", "31d4d96e407aad42", [("Path", "/"), ("Domain", "example.com")])
    ]
    expected_err = []  # type: ignore


class TwoSCTest(headers.HeaderTest):
    name = "Set-Cookie"
    inputs = [
        b"SID=31d4d96e407aad42; Path=/; Secure; HttpOnly",
        b"lang=en-US; Path=/; Domain=example.com",
    ]
    expected_out = [
        ("SID", "31d4d96e407aad42", [("Path", "/"), ("Secure", ""), ("HttpOnly", "")]),
        ("lang", "en-US", [("Path", "/"), ("Domain", "example.com")]),
    ]
    expected_err = []  # type: ignore


class ExpiresScTest(headers.HeaderTest):
    name = "Set-Cookie"
    inputs = [b"lang=en-US; Expires=Wed, 09 Jun 2021 10:18:14 GMT"]
    expected_out = [("lang", "en-US", [("Expires", 1623233894)])]
    expected_err = []  # type: ignore


class ExpiresSingleScTest(headers.HeaderTest):
    name = "Set-Cookie"
    inputs = [b"lang=en-US; Expires=Wed, 9 Jun 2021 10:18:14 GMT"]
    expected_out = [("lang", "en-US", [("Expires", 1623233894)])]
    expected_err = []  # type: ignore


class MaxAgeScTest(headers.HeaderTest):
    name = "Set-Cookie"
    inputs = [b"lang=en-US; Max-Age=123"]
    expected_out = [("lang", "en-US", [("Max-Age", 123)])]
    expected_err = []  # type: ignore


class MaxAgeLeadingZeroScTest(headers.HeaderTest):
    name = "Set-Cookie"
    inputs = [b"lang=en-US; Max-Age=0123"]
    expected_out = [("lang", "en-US", [])]  # type: ignore
    expected_err = [SET_COOKIE_LEADING_ZERO_MAX_AGE]


class RemoveSCTest(headers.HeaderTest):
    name = "Set-Cookie"
    inputs = [b"lang=; Expires=Sun, 06 Nov 1994 08:49:37 GMT"]
    expected_out = [("lang", "", [("Expires", 784111777)])]
    expected_err = []  # type: ignore


class WolframSCTest(headers.HeaderTest):
    name = "Set-Cookie"
    inputs = [
        b"WR_SID=50.56.234.188.1398; path=/; max-age=315360000; domain=.wolframalpha.com"
    ]
    expected_out = [
        (
            "WR_SID",
            "50.56.234.188.1398",
            [("Path", "/"), ("Max-Age", 315360000), ("Domain", "wolframalpha.com")],
        )
    ]
    expected_err = []  # type: ignore
