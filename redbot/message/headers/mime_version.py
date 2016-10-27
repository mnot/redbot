#!/usr/bin/env python


from redbot.message import headers


class mime_version(headers.HttpHeader):
    canonical_name = "MIME-Version"
    description = """\
HTTP is not a MIME-compliant protocol. However, HTTP/1.1 messages can include a single MIME-Version
header field to indicate what version of the MIME protocol was used to construct the message. Use
of the MIME-Version header field indicates that the message is in full compliance with the MIME
protocol."""
    reference = "%s#section-19.4.1" % headers.rfc2616
    list_header = False
    deprecated = True
    valid_in_requests = True
    valid_in_responses = True
    no_coverage = True
