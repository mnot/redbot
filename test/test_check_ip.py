#!/usr/bin/env python3

"""
The address filter that keeps REDbot from fetching local and private resources (mnot/redbot#538).
"""

import unittest

from redbot.resource.fetch import is_public_address


class TestIsPublicAddress(unittest.TestCase):
    def test_public_addresses_are_allowed(self):
        for addr in ["8.8.8.8", "93.184.216.34", "2001:4860:4860::8888", "2606:4700::1111"]:
            self.assertTrue(is_public_address(addr), addr)

    def test_local_and_private_addresses_are_denied(self):
        for addr in [
            "127.0.0.1",
            "10.0.0.1",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "100.64.0.1",
            "0.0.0.0",
            "::",
            "::1",
            "fe80::1",
            "fd00::1",
            "::ffff:127.0.0.1",
        ]:
            self.assertFalse(is_public_address(addr), addr)

    def test_nat64_addresses_are_denied(self):
        for addr in [
            "64:ff9b::7f00:1",  # 127.0.0.1
            "64:ff9b::a00:1",  # 10.0.0.1
            "64:ff9b::a9fe:a9fe",  # 169.254.169.254
            "64:ff9b::808:808",  # 8.8.8.8: the gateway's destination can't be told apart
            "64:ff9b:1::1",
            "64:ff9b:1:ffff::1",
        ]:
            self.assertFalse(is_public_address(addr), addr)


if __name__ == "__main__":
    unittest.main()
