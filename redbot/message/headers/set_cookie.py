#!/usr/bin/env python

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2013 Mark Nottingham

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

from calendar import timegm
from re import match, split
from urlparse import urlsplit

import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax

@rh.ResponseHeader
def parse(subject, value, red):
    path = urlsplit(red.base_uri).path # pylint: disable=E1103
    try:
        set_cookie = loose_parse(value, path, red.start_time, subject, red)
    except ValueError:
        set_cookie = None
    return set_cookie

def join(subject, values, red):
    return values


# TODO: properly escape note
def loose_parse(set_cookie_string, uri_path, current_time, subject, red):
    """
    Parse a Set-Cookie string, as per RFC6265, Section 5.2.
    """
    name = "Set-Cookie"
    if ';' in set_cookie_string:
        name_value_pair, unparsed_attributes = set_cookie_string.split(";", 1)
    else:
        name_value_pair, unparsed_attributes = set_cookie_string, ""
    try:
        name, value = name_value_pair.split("=", 1)
    except ValueError:
        red.add_note(subject, rs.SET_COOKIE_NO_VAL,
            name_value_pair.strip()
        )
        raise ValueError, "Cookie doesn't have a value"
    name, value = name.strip(), value.strip()
    if name == "":
        red.add_note(subject, rs.SET_COOKIE_NO_NAME)
        raise ValueError, "Cookie doesn't have a name"
    cookie_name, cookie_value = name, value
    cookie_attribute_list = []
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
            except ValueError, why:
                red.add_note(subject, rs.SET_COOKIE_BAD_DATE, why=why,
                    cookie_name=cookie_name
                )
                continue
            cookie_attribute_list.append(("Expires", expiry_time))
        elif case_norm_attribute_name == "max-age":
            if attribute_value == "":
                red.add_note(subject, rs.SET_COOKIE_EMPTY_MAX_AGE,
                    cookie_name=cookie_name
                )
                continue
            if attribute_value[0] == "0":
                red.add_note(subject, rs.SET_COOKIE_LEADING_ZERO_MAX_AGE,
                    cookie_name=cookie_name
                )
                continue
            if not attribute_value.isdigit():
                red.add_note(subject, rs.SET_COOKIE_NON_DIGIT_MAX_AGE,
                    cookie_name=cookie_name
                )
                continue
            delta_seconds = int(attribute_value)
            cookie_attribute_list.append(("Max-Age", delta_seconds))
        elif case_norm_attribute_name == "domain":
            if attribute_value == "":
                red.add_note(subject, rs.SET_COOKIE_EMPTY_DOMAIN,
                    cookie_name=cookie_name
                )
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
                    cookie_path = uri_path[:uri_path.rindex("/")]
            else:
                cookie_path = attribute_value
            cookie_attribute_list.append(("Path", cookie_path))
        elif case_norm_attribute_name == "secure":
            cookie_attribute_list.append(("Secure", ""))
        elif case_norm_attribute_name == "httponly":
            cookie_attribute_list.append(("HttpOnly", ""))
        else:
            red.add_note(subject, rs.SET_COOKIE_UNKNOWN_ATTRIBUTE,
                cookie_name=cookie_name,
                attribute=attribute_name
            )
    return (cookie_name, cookie_value, cookie_attribute_list)


DELIMITER = r'(?:[\x09\x20-\x2F\x3B-\x40\x5B-\x60\x7B-\x7E])'
NON_DELIMTER = r'(?:[\x00-\x08\x0A-\x1F0-0\:a-zA-Z\x7F-\xFF])'
MONTHS = {
    'jan': 1,
    'feb': 2,
    'mar': 3,
    'apr': 4,
    'may': 5,
    'jun': 6,
    'jul': 7,
    'aug': 8,
    'sep': 9,
    'oct': 10,
    'nov': 11,
    'dec': 12
}
def loose_date_parse(cookie_date):
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
            re_match = match(r'^(\d{2}:\d{2}:\d{2})(?:\D)?', date_token)
            if re_match:
                found_time = True
                hour_value, minute_value, second_value = [
                    int(v) for v in re_match.group(1).split(":")
                ]
                continue
        if not found_day_of_month:
            re_match = match(r'^(\d\d?)(?:\D)?', date_token)
            if re_match:
                found_day_of_month = True
                day_of_month_value = int(re_match.group(1))
                continue
        # TODO: shorter than three chars
        if not found_month and date_token[:3].lower() in MONTHS.keys():
            found_month = True
            month_value = MONTHS[date_token[:3].lower()]
            continue
        if not found_year:
            re_match = match(r'^(\d{2,4})(?:\D)?', date_token)
            if re_match:
                found_year = True
                year_value = int(re_match.group(1))
                continue
    if 99 >= year_value >= 70:
        year_value += 1900
    if 69 >= year_value >= 0:
        year_value += 2000
    if False in [found_time, found_day_of_month, found_month, found_year]:
        missing = []
        if not found_time: missing.append("time")
        if not found_day_of_month: missing.append("day")
        if not found_month: missing.append("month")
        if not found_year: missing.append("year")
        raise ValueError, "didn't have a: %s" % ",".join(missing)
    if day_of_month_value < 1 or day_of_month_value > 31:
        raise ValueError, "%s is out of range for day_of_month" % \
            day_of_month_value
    if year_value < 1601:
        raise ValueError, "%s is out of range for year" % year_value
    if hour_value > 23:
        raise ValueError, "%s is out of range for hour" % hour_value
    if minute_value > 59:
        raise ValueError, "%s is out of range for minute" % minute_value
    if second_value > 59:
        raise ValueError, "%s is out of range for second" % second_value
    parsed_cookie_date = timegm((
        year_value,
        month_value,
        day_of_month_value,
        hour_value,
        minute_value,
        second_value
    ))
    return parsed_cookie_date


class BasicSCTest(rh.HeaderTest):
    name = 'Set-Cookie'
    inputs = ['SID=31d4d96e407aad42']
    expected_out = [("SID", "31d4d96e407aad42", [])]
    expected_err = []

class ParameterSCTest(rh.HeaderTest):
    name = 'Set-Cookie'
    inputs = ['SID=31d4d96e407aad42; Path=/; Domain=example.com']
    expected_out = [("SID", "31d4d96e407aad42",
        [("Path", "/"), ("Domain", "example.com")])]
    expected_err = []

class TwoSCTest(rh.HeaderTest):
    name = 'Set-Cookie'
    inputs = [
        "SID=31d4d96e407aad42; Path=/; Secure; HttpOnly",
        "lang=en-US; Path=/; Domain=example.com"
    ]
    expected_out = [
        ("SID", "31d4d96e407aad42", [("Path", "/"), ("Secure", ""), ("HttpOnly", "")]),
        ("lang", "en-US", [("Path", "/"), ("Domain", "example.com")])
    ]
    expected_err = []

class ExpiresScTest(rh.HeaderTest):
    name = "Set-Cookie"
    inputs = ["lang=en-US; Expires=Wed, 09 Jun 2021 10:18:14 GMT"]
    expected_out = [("lang", "en-US", [("Expires", 1623233894)])]
    expected_err = []

class ExpiresSingleScTest(rh.HeaderTest):
    name = "Set-Cookie"
    inputs = ["lang=en-US; Expires=Wed, 9 Jun 2021 10:18:14 GMT"]
    expected_out = [("lang", "en-US", [("Expires", 1623233894)])]
    expected_err = []

class MaxAgeScTest(rh.HeaderTest):
    name = "Set-Cookie"
    inputs = ["lang=en-US; Max-Age=123"]
    expected_out = [("lang", "en-US", [("Max-Age", 123)])]
    expected_err = []

class MaxAgeLeadingZeroScTest(rh.HeaderTest):
    name = "Set-Cookie"
    inputs = ["lang=en-US; Max-Age=0123"]
    expected_out = [("lang", "en-US", [])]
    expected_err = [rs.SET_COOKIE_LEADING_ZERO_MAX_AGE]

class RemoveSCTest(rh.HeaderTest):
    name = "Set-Cookie"
    inputs = ["lang=; Expires=Sun, 06 Nov 1994 08:49:37 GMT"]
    expected_out = [("lang", "", [("Expires", 784111777)])]
    expected_err = []

class WolframSCTest(rh.HeaderTest):
    name = "Set-Cookie"
    inputs = ["WR_SID=50.56.234.188.1393830943825054; path=/; max-age=315360000; domain=.wolframalpha.com"]
    expected_out = [("WR_SID","50.56.234.188.1393830943825054", [('Path', '/'), ('Max-Age', 315360000), ('Domain', 'wolframalpha.com')])]
    expected_err = []