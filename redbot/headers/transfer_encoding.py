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

from cgi import escape as e

import redbot.speak as rs
import redbot.headers as rh
import redbot.http_syntax as syntax


@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(syntax.TOK_PARAM, rh.rfc2616 % "sec-14.41")
# TODO: accommodate transfer-parameters
def parse(name, values, red):
    codings = []
    unwanted_codings = set()
    for value in values:
        try:
            coding, params = value.split(";", 1)
        except ValueError:
            coding, params = value, ""
        coding = coding.lower()
        codings.append(coding)
        param_dict = rh.parse_params(red, name, params, True)
        if param_dict:
            red.set_message(name, rs.TRANSFER_CODING_PARAM,
                encoding=e(coding))
        # check to see if there are any non-chunked encodings, because
        # that's the only one we ask for.
        if coding not in ['chunked', 'identity']:
            unwanted_codings.add(coding)
    if unwanted_codings:
        red.set_message(name, rs.TRANSFER_CODING_UNWANTED,
                unwanted_codings=e(", ".join(unwanted_codings)))
    if 'identity' in codings:
        red.set_message(name, rs.TRANSFER_CODING_IDENTITY)
    return codings

class TransferEncodingTest(rh.HeaderTest):
    name = 'Transfer-Encoding'
    inputs = ['chunked']
    expected_out = (['chunked'])
    expected_err = []

class TransferEncodingParamTest(rh.HeaderTest):
    name = 'Transfer-Encoding'
    inputs = ['chunked; foo=bar']
    expected_out = (['chunked'])
    expected_err = [rs.TRANSFER_CODING_PARAM]

class BadTransferEncodingTest(rh.HeaderTest):
    name = 'Transfer-Encoding'
    inputs = ['chunked=foo']
    expected_out = None
    expected_err = [rs.BAD_SYNTAX]

class TransferEncodingCaseTest(rh.HeaderTest):
    name = 'Transfer-Encoding'
    inputs = ['chUNked']
    expected_out = (['chunked'])
    expected_err = []

class TransferEncodingIdentityTest(rh.HeaderTest):
    name = 'Transfer-Encoding'
    inputs = ['identity']
    expected_out = (['identity'])
    expected_err = [rs.TRANSFER_CODING_IDENTITY]

class TransferEncodingUnwantedTest(rh.HeaderTest):
    name = 'Transfer-Encoding'
    inputs = ['foo']
    expected_out = (['foo'])
    expected_err = [rs.TRANSFER_CODING_UNWANTED]
    
class TransferEncodingMultTest(rh.HeaderTest):
    name = 'Transfer-Encoding'
    inputs = ['chunked', 'identity']
    expected_out = (['chunked', 'identity'])
    expected_err = [rs.TRANSFER_CODING_IDENTITY]

class TransferEncodingMultUnwantedTest(rh.HeaderTest):
    name = 'Transfer-Encoding'
    inputs = ['chunked', 'foo', 'bar']
    expected_out = (['chunked', 'foo', 'bar'])
    expected_err = [rs.TRANSFER_CODING_UNWANTED]
