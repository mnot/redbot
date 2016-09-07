#!/usr/bin/env python


from redbot.message import headers
from redbot.speak import Note, categories, levels


class soapaction(headers.HttpHeader):
  canonical_name = u"SoapAction"
  description = u"""\
The `SOAPAction` header is used by SOAP, which isn't really HTTP. Stop it.
"""
  reference = u"http://www.w3.org/TR/2000/NOTE-SOAP-20000508/#_Toc478383528"
  list_header = False
  deprecated = False
  valid_in_requests = True
  valid_in_responses = False
  no_coverage = True