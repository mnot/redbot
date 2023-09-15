#!/usr/bin/env python
# coding=UTF-8

from playwright.sync_api import sync_playwright, TimeoutError

import time
import unittest

TIMEOUT = 30 * 1000

class BasicWebUiTest(unittest.TestCase):
    test_uri = "https://www.mnot.net/"

    def setUp(self):
        self.page = browser.new_page()
        self.page.goto(url=redbot_uri, wait_until="load")
        self.check_complete()
        self.page.fill("#uri", self.test_uri)
        self.page.press("#uri", "Enter")

    def test_multi(self):
        self.page.click('input[value="check embedded"]')
        self.check_complete()

    def check_complete(self):
        try:
            self.page.wait_for_selector("div.footer", timeout=TIMEOUT)
        except TimeoutError:
            self.page.screenshot(path="error.png", full_page=True)
            raise AssertionError("Timeout")


#class CnnWebUiTest(BasicWebUiTest):
#    test_uri = "https://edition.cnn.com/"


def redbot_run():
    import redbot.daemon
    from configparser import ConfigParser

    conf = ConfigParser()
    conf.read("config.txt")
    redconf = conf["redbot"]
    redbot.daemon.RedBotServer(redconf)


if __name__ == "__main__":
    test_host = "localhost"
    test_port = 8000
    redbot_uri = "http://%s:%s/" % (test_host, test_port)
    import sys

    sys.path.insert(0, "bin")
    from multiprocessing import Process

    p = Process(target=redbot_run)
    p.start()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        tests = unittest.main(exit=False, verbosity=2)
        browser.close()
    print("done webui test...")
    p.terminate()
    if len(tests.result.errors) > 0 or len(tests.result.failures) > 0:
        sys.exit(1)
