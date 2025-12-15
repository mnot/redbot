#!/usr/bin/env python
# coding=UTF-8

from playwright.sync_api import sync_playwright, TimeoutError
import http.server
import threading
import time
import unittest
import sys
from multiprocessing import Process


TIMEOUT = 30 * 1000

class TestHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def prepare_response(self):
        if self.path == "/img.png":
            content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            ctype = "image/png"
        else:
            content = b"<html><body><h1>Hello World</h1><img src='img.png'></body></html>"
            ctype = "text/html"

        self.send_response(200)
        self.send_header("Content-type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "max-age=3600")
        self.send_header("Connection", "close")
        self.end_headers()
        return content

    def do_GET(self):
        content = self.prepare_response()
        self.wfile.write(content)
        self.wfile.flush()
        self.close_connection = True

    def do_HEAD(self):
        self.prepare_response()
        self.wfile.flush()
        self.close_connection = True


class TestServer(threading.Thread):
    def __init__(self):
        super().__init__()
        self.port = 8001  # Different from redbot port
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', self.port), TestHandler)
        self.server.allow_reuse_address = True
        self.daemon = True

    def run(self):
        self.server.serve_forever()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


class BasicWebUiTest(unittest.TestCase):
    test_uri = "http://127.0.0.1:8001/"

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


def redbot_run():
    import redbot.daemon
    from configparser import ConfigParser

    conf = ConfigParser()
    conf.read("config.txt")
    conf["redbot"]["enable_local_access"] = "true"
    redconf = conf["redbot"]
    server = redbot.daemon.RedBotServer(redconf)
    server.run()


if __name__ == "__main__":
    test_host = "localhost"
    test_port = 8000
    redbot_uri = "http://%s:%s/" % (test_host, test_port)
    
    sys.path.insert(0, "bin")

    # Start REDbot server
    p = Process(target=redbot_run)
    p.start()
    
    # Start local test server
    test_server = TestServer()
    test_server.start()
    
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            tests = unittest.main(exit=False, verbosity=2)
            browser.close()
            print("done webui test...")
    finally:
        p.terminate()
        # test_server.stop() # daemon thread dies with main
        if 'tests' in locals() and (len(tests.result.errors) > 0 or len(tests.result.failures) > 0):
            sys.exit(1)
