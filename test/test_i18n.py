
import unittest
from unittest.mock import MagicMock, patch
from redbot.webui import RedWebUi
from redbot.formatter import Formatter, f_num, relative_time
from redbot.i18n import get_locale
import time

class TestI18n(unittest.TestCase):
    def test_negotiate_locale(self):
        config = MagicMock()
        config.get.return_value = "utf-8"
        
        # Mock request headers
        req_headers = [
            (b"Accept-Language", b"fr-FR, fr;q=0.9, en;q=0.8")
        ]
        
        # We need to mock negotiate_locale because we might not have 'fr' translations yet
        with patch("redbot.webui.negotiate_locale", return_value="fr") as mock_neg:
            ui = RedWebUi(
                config, 
                "GET", 
                b"", 
                req_headers, 
                b"", 
                MagicMock(), 
                "127.0.0.1"
            )
            self.assertEqual(ui.locale, "fr")
            
    def test_content_language_header(self):
        config = MagicMock()
        config.get.return_value = "utf-8"
        req_headers = [(b"Accept-Language", b"fr")]
        exchange = MagicMock()
        
        with patch("redbot.webui.negotiate_locale", return_value="fr"):
            ui = RedWebUi(
                config, 
                "GET", 
                b"", 
                req_headers, 
                b"", 
                exchange, 
                "127.0.0.1"
            )
            ui.show_default()
            
            # Check if response_start was called with Content-Language header
            args, _ = exchange.response_start.call_args
            headers = args[2]
            self.assertIn((b"Content-Language", b"fr"), headers)

    def test_formatter_context(self):
        config = MagicMock()
        resource = MagicMock()
        # Mock resource attributes needed by bind_resource
        resource.check_done = False
        resource.request.complete = False
        resource.response_content_processors = []
        
        output = MagicMock()
        params = {"locale": "fr"}
        
        class TestFormatter(Formatter):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.captured_locale = None

            def start_output(self):
                self.captured_locale = get_locale()

        tf = TestFormatter(config, resource, output, params)
        
        # Mock resource.on to capture callbacks
        resource.on = MagicMock()
        
        tf.bind_resource(resource)
        
        # Find the callback for "response_headers_available"
        callback = None
        for call in resource.on.call_args_list:
            if call[0][0] == "response_headers_available":
                callback = call[0][1]
                break
        
        self.assertIsNotNone(callback, "Callback for response_headers_available not found")
        
        # Execute the callback
        callback()
        
        # Verify locale was set during callback execution
        self.assertEqual(tf.captured_locale, "fr")

    def test_f_num(self):
        # Test with default locale (en)
        # We need to ensure context is set. 
        # f_num uses get_locale().
        
        # Test with 'en'
        with patch("redbot.formatter.get_locale", return_value="en"):
            self.assertEqual(f_num(1000), "1,000")
            
        # Test with 'de' (uses dot as thousands separator)
        with patch("redbot.formatter.get_locale", return_value="de"):
            self.assertEqual(f_num(1000), "1.000")

    def test_relative_time(self):
        now = time.time()
        past = now - 3600 # 1 hour ago
        
        with patch("redbot.formatter.get_locale", return_value="en"):
            self.assertEqual(relative_time(past, now), "60 minutes ago")
            
        with patch("redbot.formatter.get_locale", return_value="fr"):
            # Babel's output for 1 hour ago in French
            # "il y a 1 heure" or similar. 
            # We should check what Babel actually returns or just that it's different/valid.
            # For now, let's just check it runs without error and returns a string.
            res = relative_time(past, now)
            self.assertIsInstance(res, str)
            self.assertTrue("heure" in res or "minute" in res) # Assuming 'heure' or 'minute' is in the output

if __name__ == "__main__":
    unittest.main()
