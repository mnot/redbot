#!/usr/bin/env python3

"""
When local access is disabled, the shared client refuses DNS results that would
connect to a non-global address - including addresses that a NAT64 gateway
would translate to a non-global IPv4 address (#538).
"""

import unittest
from configparser import ConfigParser

from redbot.resource.fetch import RedFetcher


class TestCheckIp(unittest.TestCase):
    "the address check installed on the shared client"

    def setUp(self) -> None:
        # the client is shared by the whole process; keep our changes local
        self.saved_check_ip = RedFetcher.client.check_ip
        RedFetcher.client.check_ip = None
        config = ConfigParser()
        config.read_dict({"redbot": {"enable_local_access": "no"}})
        RedFetcher(config["redbot"])

    def tearDown(self) -> None:
        RedFetcher.client.check_ip = self.saved_check_ip

    def deny(self, dns_result: str) -> None:
        "assert the installed check refuses this DNS result"
        check_ip = RedFetcher.client.check_ip
        self.assertIsNotNone(check_ip)
        self.assertFalse(check_ip(dns_result))

    def allow(self, dns_result: str) -> None:
        "assert the installed check accepts this DNS result"
        check_ip = RedFetcher.client.check_ip
        self.assertIsNotNone(check_ip)
        self.assertTrue(check_ip(dns_result))

    def test_nat64_to_loopback_denied(self) -> None:
        "64:ff9b::7f00:1 is 127.0.0.1 behind the gateway"
        self.deny("64:ff9b::7f00:1")

    def test_nat64_to_private_denied(self) -> None:
        "64:ff9b::a00:1 is 10.0.0.1 behind the gateway"
        self.deny("64:ff9b::a00:1")

    def test_nat64_to_link_local_denied(self) -> None:
        "64:ff9b::a9fe:a9fe embeds the link-local metadata range (169.254/16)"
        self.deny("64:ff9b::a9fe:a9fe")

    def test_nat64_to_global_allowed(self) -> None:
        "64:ff9b::808:808 is 8.8.8.8 - still fine behind a gateway"
        self.allow("64:ff9b::808:808")

    def test_nat64_local_use_prefix_denied(self) -> None:
        "RFC 8215 64:ff9b:1::/48 is local-use, whatever it carries"
        self.deny("64:ff9b:1::a00:1")

    def test_plain_loopback_denied(self) -> None:
        self.deny("127.0.0.1")

    def test_private_denied(self) -> None:
        self.deny("10.0.0.1")

    def test_global_allowed(self) -> None:
        self.allow("8.8.8.8")

    def test_global_ipv6_allowed(self) -> None:
        self.allow("2606:4700::1111")


class TestNoCheckIpWhenLocalAccess(unittest.TestCase):
    "local access configured: no check is installed at all"

    def setUp(self) -> None:
        self.saved_check_ip = RedFetcher.client.check_ip
        RedFetcher.client.check_ip = None

    def tearDown(self) -> None:
        RedFetcher.client.check_ip = self.saved_check_ip

    def test_no_check_installed(self) -> None:
        config = ConfigParser()
        config.read_dict({"redbot": {"enable_local_access": "yes"}})
        RedFetcher(config["redbot"])
        self.assertIsNone(RedFetcher.client.check_ip)


if __name__ == "__main__":
    unittest.main()
