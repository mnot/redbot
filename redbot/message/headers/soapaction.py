#!/usr/bin/env python


from redbot.message import headers


class soapaction(headers.HttpHeader):
    canonical_name = "SoapAction"
    description = """\
The `SOAPAction` header is used by SOAP, which isn't really HTTP. Stop it."""
    reference = "http://www.w3.org/TR/2000/NOTE-SOAP-20000508/#_Toc478383528"
    list_header = False
    deprecated = False
    valid_in_requests = True
    valid_in_responses = False
    no_coverage = True
