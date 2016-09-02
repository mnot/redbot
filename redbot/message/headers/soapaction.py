#!/usr/bin/env python


import redbot.message.headers as headers
from redbot.speak import Note, categories, levels
from redbot.message.headers import HttpHeader, HeaderTest

class soapaction(HttpHeader):
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