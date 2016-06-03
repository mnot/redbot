#!/usr/bin/env python


import redbot.speak as rs
from redbot.message import headers as rh
from redbot.message import http_syntax as syntax


description = u"""\
The `Transfer-Encoding` header indicates what (if any) type of transformation has been applied to
the message body.

This differs from `Content-Encoding` in that transfer-codings are a property of the message, not of
the representation; i.e., it will be removed by the next "hop", whereas content-codings are
end-to-end.

The most commonly used transfer-coding is `chunked`, which allows persistent connections to be used
without knowing the entire body's length."""

reference = u"%s#header.transfer-encoding" % rs.rfc7230


@rh.RequestOrResponseHeader
@rh.GenericHeaderSyntax
@rh.CheckFieldSyntax(syntax.TOK_PARAM, rh.rfc2616 % "section-14.41")
def parse(subject, value, red):
    try:
        coding, params = value.split(";", 1)
    except ValueError:
        coding, params = value, ""
    coding = coding.lower()
    param_dict = rh.parse_params(red, subject, params, True)
    if param_dict:
        red.add_note(subject, rs.TRANSFER_CODING_PARAM)
    return coding

def join(subject, values, red):
    unwanted = set([c for c in values if c not in
        ['chunked', 'identity']]
    ) or False
    if unwanted:
        red.add_note(subject, rs.TRANSFER_CODING_UNWANTED,
                unwanted_codings=", ".join(unwanted))
    if 'identity' in values:
        red.add_note(subject, rs.TRANSFER_CODING_IDENTITY)
    return values


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
    expected_out = []
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
