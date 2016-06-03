#!/usr/bin/env python


import redbot.speak as rs

description = u"""\
The `TE` header indicates what transfer-codings the client is willing to accept in the response,
and whether or not it is willing to accept trailer fields after the body when the response uses
chunked transfer-coding.

The most common transfer-coding, `chunked`, doesn't need to be listed in `TE`."""

reference = u"%s#header.te" % rs.rfc7230
