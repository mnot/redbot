#!/usr/bin/env python


import redbot.speak as rs

description = u"""\
The `Upgrade` header allows the client to specify what additional communication
protocols it supports and would like to use if the server finds it appropriate
to switch protocols. Servers use it to confirm upgrade to a specific
protocol."""

reference = u"%s#header.upgrade" % rs.rfc7230