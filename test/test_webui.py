#!/usr/bin/env python
# coding=UTF-8

from playwright.sync_api import sync_playwright, TimeoutError, Response, APIResponse
import unittest
import sys
import os
from multiprocessing import Process
from test.server import Colors, colorize


TIMEOUT = 30 * 1000
ACTION_TIMEOUT = 10 * 1000


class NewlineTextTestResult(unittest.TextTestResult):
    def startTest(self, test):
        self.stream.write('\n')
        super().startTest(test)
        self.stream.write('\n')
    
    def addSuccess(self, test):
        super().addSuccess(test)
        self.stream.write('\n')
        
    def addError(self, test, err):
        test.failed = True
        super().addError(test, err)
        self.stream.write('\n')

    def addFailure(self, test, err):
        test.failed = True
        super().addFailure(test, err)
        self.stream.write('\n')


class NewlineTextTestRunner(unittest.TextTestRunner):
    resultclass = NewlineTextTestResult


class BasicWebUiTest(unittest.TestCase):
    test_uri = "http://127.0.0.1:8001/"

    def setUp(self):
        self.page = browser.new_page()
        self.page.set_default_timeout(ACTION_TIMEOUT)
        self.page.on(
            "console",
            lambda msg: print(colorize(f"BROWSER CONSOLE: {msg.text}", Colors.CYAN)),
        )
        self.page.goto(url=redbot_uri, wait_until="load")
        self.check_complete()
        self.page.fill("#uri", self.test_uri)
        self.page.press("#uri", "Enter")
        self.check_complete()

    def tearDown(self):
        import os
        if getattr(self, "failed", False):
            path = os.path.abspath(f"fail_{self._testMethodName}.png")
            self.page.screenshot(path=path, full_page=True)
            sys.stderr.write(
                colorize(
                    f"DEBUG: Test failed. Screenshot saved to {path}\n",
                    Colors.RED,
                )
            )
        self.page.close()

    def test_multi(self):
        self.page.click('input[value="check embedded"]')
        self.check_complete()

    def test_request_header(self):
        self.page.click("#add_req_hdr")
        self.page.wait_for_selector(".hdr_name select")
        self.page.select_option(".hdr_name select", "Cache-Control")
        self.page.evaluate("document.querySelector('.hdr_name select').dispatchEvent(new Event('change', {bubbles: true}))")
        
        self.page.wait_for_selector(".hdr_val select")
        self.page.select_option(".hdr_val select", "no-cache")
        self.page.evaluate("document.querySelector('.hdr_val select').dispatchEvent(new Event('change', {bubbles: true}))")

        # Verify hidden input
        val = self.page.input_value("input[name='req_hdr']")
        self.assertEqual(val, "Cache-Control:no-cache")
        
        # Wait for form elements to be reliably updated in the DOM serialization
        self.page.wait_for_timeout(1000)
        self.page.click("#go")
        self.check_complete()
        self.assertIn("Cache-Control", self.page.content())
        self.assertIn("no-cache", self.page.content())

    def test_view_har(self):
        with self.page.expect_response(lambda response: "format=har" in response.url) as response_info:
            self.page.click("input[value='view HAR']")
        response = response_info.value
        self.assertTrue(response.ok)
        har_content = response.json()

        self.assertIn("log", har_content)
        self.assertIn("version", har_content["log"])
        self.assertEqual(har_content["log"]["version"], "1.1")
        self.assertIn("entries", har_content["log"])
        self.assertTrue(len(har_content["log"]["entries"]) > 0)
        
        entry = har_content["log"]["entries"][0]
        self.assertEqual(entry["response"]["status"], 200)
        # Content-Type header
        headers = {h["name"].lower(): h["value"].strip() for h in entry["response"]["headers"]}
        self.assertIn("content-type", headers)
        self.assertEqual(headers["content-type"], "text/html")
        
    def test_save(self):
        from playwright.sync_api import expect
        self.page.click("#save")
        save_indicator = self.page.locator("span.save")
        expect(save_indicator).to_contain_text("saved")

    def test_active_check_range(self):
        self.page.click("text='Partial Content response'")
        self.check_complete()
        self.assertIn("Partial Content response", self.page.locator("h1").text_content() or "")

    def test_active_check_conneg(self):
        self.page.click("text='Content Negotiation response'")
        self.check_complete()
        self.assertIn("Content Negotiation response", self.page.locator("h1").text_content() or "")

    def test_active_check_etag(self):
        self.page.click("text='ETag Validation response'")
        self.check_complete()
        self.assertIn("ETag Validation response", self.page.locator("h1").text_content() or "")

    def test_active_check_lm(self):
        self.page.click("text='Last-Modified Validation response'")
        self.check_complete()
        self.assertIn("Last-Modified Validation response", self.page.locator("h1").text_content() or "")

    def check_complete(self):
        try:
            self.page.wait_for_selector("div.footer", timeout=TIMEOUT)
        except TimeoutError:
            raise AssertionError("Timeout waiting for completion")


class WebUiErrorTest(unittest.TestCase):
    def setUp(self):
        self.page = browser.new_page()

    def tearDown(self):
        import os
        if getattr(self, "failed", False):
            path = os.path.abspath(f"fail_{self._testMethodName}.png")
            self.page.screenshot(path=path, full_page=True)
            sys.stderr.write(
                colorize(
                    f"DEBUG: Test failed. Screenshot saved to {path}\n",
                    Colors.RED,
                )
            )
        self.page.close()

    def test_unsupported_method(self):
        response = self.page.request.put(redbot_uri)
        self.assertIsNotNone(response)
        assert isinstance(response, APIResponse)
        self.assertEqual(response.status, 404)

    def test_non_existent_resource(self):
        response = self.page.goto(redbot_uri + "does_not_exist")
        self.assertIsNotNone(response)
        assert isinstance(response, Response)
        self.assertEqual(response.status, 404)
        self.assertIn("The requested resource was not found", self.page.content())


def write_github_summary(tests):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    with open(summary_path, "a", encoding="utf-8") as f:
        f.write("## WebUI Test Results\n\n")
        f.write("| Test | Status | Details |\n")
        f.write("| --- | --- | --- |\n")

        # unittest.TestResult.successes is only available if we use a runner that tracks it.
        # Standard unittest.TestResult doesn't store successes by default in all versions,
        # but NewlineTextTestResult inherits from TextTestResult which might.
        # If not, we can infer successes.
        
        all_tests = []
        for cls in [BasicWebUiTest, WebUiErrorTest]:
            for name in dir(cls):
                if name.startswith("test_") and callable(getattr(cls, name)):
                    all_tests.append(name)

        failed_names = {t._testMethodName: err for t, err in tests.result.failures}
        error_names = {t._testMethodName: err for t, err in tests.result.errors}

        for test_name in sorted(all_tests):
            if test_name in error_names:
                status = "💥 Error"
            elif test_name in failed_names:
                status = "❌ Fail"
            else:
                status = "✅ Pass"
            f.write(f"| {test_name} | {status} | |\n")

        f.write("\n")

        all_failures = tests.result.failures + tests.result.errors
        if all_failures:
            f.write("### Failure Details\n\n")
            for test, err in all_failures:
                test_name = test._testMethodName
                f.write(f"#### {test_name}\n\n")
                f.write(f"```python\n{err}\n```\n\n")
                screenshot_path = os.path.abspath(f"fail_{test_name}.png")
                if os.path.exists(screenshot_path):
                    f.write("*Screenshot available in job artifacts.*\n\n")


def redbot_run():
    import redbot.daemon
    from configparser import ConfigParser
    import tempfile
    import shutil
    import atexit


    save_dir = tempfile.mkdtemp()
    
    def cleanup():
        shutil.rmtree(save_dir, ignore_errors=True)
        
    atexit.register(cleanup)

    conf = ConfigParser()
    conf.read("config.txt")
    conf["redbot"]["enable_local_access"] = "true"
    # Disable rate limits for tests
    if "limit_client_tests" in conf["redbot"]:
        del conf["redbot"]["limit_client_tests"]
    if "instant_limit" in conf["redbot"]:
        del conf["redbot"]["instant_limit"]
    redconf = conf["redbot"]
    redconf["save_dir"] = save_dir
    redconf["host"] = "127.0.0.1"
    server = redbot.daemon.RedBotServer(redconf)
    try:
        server.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    test_host = "127.0.0.1"
    test_port = 8000
    redbot_uri = "http://%s:%s/" % (test_host, test_port)
    
    sys.path.insert(0, "bin")

    # Start REDbot server
    p = Process(target=redbot_run)
    p.start()
    
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            # Hook up console log
            context = browser.new_context()
            
            tests = unittest.main(exit=False, verbosity=2, testRunner=NewlineTextTestRunner)
            write_github_summary(tests)
            browser.close()
            print("done webui test...")
    finally:
        p.terminate()
        p.join(timeout=2)
        if p.is_alive():
            print("Terminating process forcefully...")
            p.kill()
            p.join()

        if 'tests' in locals() and (len(tests.result.errors) > 0 or len(tests.result.failures) > 0):
            sys.exit(1)
