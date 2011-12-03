#!/usr/bin/env python

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2011 Mark Nottingham

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
from cgi import escape as e
from re import match, split
import string
from urlparse import urlsplit

import redbot.speak as rs
import redbot.headers as rh
import redbot.http_syntax as syntax


def parse(name, values, red):
    set_cookies = []
    for value in values:
        path = urlsplit(red.uri).path
        try:
            set_cookie = loose_parse(set_cookie_string, path, red.res_done_ts)
        except ValueError:
            pass # TODO
        set_cookies.append(set_cookie)
    return set_cookies
    
    
def loose_parse(set_cookie_string, uri_path, current_time):
    """
    Parse a Set-Cookie string, as per RFC6265, Section 5.2.
    """
    if ';' in set_cookie_string:
        name_value_pair, unparsed_attributes = set_cookie_string.split(";", 1)
    else:
        name_value_pair, unparsed_attributes = set_cookie_string, ""
    try:
        name, value = name_value_pair.split("=", 1)
    except ValueError:
        return None
    name, value = name.strip(), value.strip()
    if name == "":
        return None
    cookie_name, cookie_value = name, value
    cookie_attribute_list = []
    while unparsed_attributes != "":
        if ";" in unparsed_attributes:
            cookie_av, unparsed_attributes = unparsed_attributes.split(";", 1)
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
                except ValueError:
                    continue
                cookie_attribute_list.append(("Expires", expiry_time))
            elif case_norm_attribute_name == "max-age":
                if attribute_value == "":
                    continue
                if attribute_value[0] not in string.digits + "-":
                    continue
                if attribute_value[1:] not in string.digits:
                    continue
                delta_seconds = int(attribute_value)
                if delta_seconds <= 0:
                    expiry_time = 0
                else:
                    expiry_time = current_time + delta_seconds
                cookie_attribute_list.append(("Max-Age", expiry_time))                
            elif case_norm_attribute_name == "domain":
                if attribute_value == "":
                    continue
                elif attribute_value[0] == ".":
                    cookie_domain = attribute_value[1:]
                else:
                    cookie_domain = attribute_value
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
                pass # unrecognised attribute
    return cookie_name, cookie_value, cookie_attribute_list


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
    found_time, found_day_of_month, found_month, found_year = False
    hour_value = minute_value = second_value = None
    day_of_month_value = month_value = year_value = None
    date_tokens = split(DELIMITER, cookie_date)
    for date_token in date_tokens:
        re_match = None
        if not found_time:
            re_match = match(r'^(\d{2}:\d{2}:\d{2})(?:\D)?')
            if re_match:
                found_time = True
                hour_value, minute_value, second_value = [
                    int(v for v in re_match.group(1).split(":"))
                ]
                continue
        if not found_day_of_month:
            re_match = match(r'^(\d{2})(?:\D)?', date_token)
            if re_match:
                found_day_of_month = True
                day_of_month_value = int(re_match.group(1))
                continue
        if not found_month and attribute_value[:3].lower in MONTHS.keys():
            found_month = True
            month_value = MONTHS[date_token]
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
        raise ValueError, "didn't find all date components"
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