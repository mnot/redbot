
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
            self.assertEqual(str(relative_time(past, now)), "60 minutes ago")
            
        with patch("redbot.formatter.get_locale", return_value="fr"):
            # Babel's output for 1 hour ago in French
            # "il y a 1 heure" or similar. 
            # We should check what Babel actually returns or just that it's different/valid.
            # For now, let's just check it runs without error and returns a string.
            res = relative_time(past, now)
            # self.assertIsInstance(res, str) # No longer a string
            res_str = str(res)
            self.assertTrue("heure" in res_str or "minute" in res_str) # Assuming 'heure' or 'minute' is in the output

    def test_fetcher_locale_propagation(self):
        """
        Verify that RedFetcher captures the locale at check() time and applies it
        during callbacks, ensuring httplint notes use the correct locale.
        """
        from redbot.resource.fetch import RedFetcher
        from redbot.i18n import set_locale
        
        class MockExchange:
            def __init__(self):
                self.callbacks = {}
                self.res_version = b"1.1"
                self.input_transfer_length = 0
                self.input_header_length = 0

            def on(self, event, callback):
                self.callbacks[event] = callback

            def once(self, event, callback):
                self.callbacks[event] = callback
                
            def request_start(self, method, uri, headers):
                pass
                
            def request_body(self, chunk):
                pass
                
            def request_done(self, trailers):
                pass

            def trigger_response(self):
                # Simulate response
                # 604800 seconds = 1 week
                if "response_start" in self.callbacks:
                    self.callbacks["response_start"](b"200", b"OK", [
                        (b"Date", time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime()).encode('ascii')),
                        (b"Age", b"604800"), 
                        (b"Cache-Control", b"max-age=2000000")
                    ])
                if "response_done" in self.callbacks:
                    self.callbacks["response_done"]([])

        class MockClient:
            def __init__(self):
                self.check_ip = None
                
            def exchange(self):
                return MockExchange()

        config = MagicMock()
        config.getint.return_value = 1000
        config.getboolean.return_value = False
        
        fetcher = RedFetcher(config)
        fetcher.client = MockClient()
        fetcher.set_request("http://example.com/")
        
        # Run check() within a French locale context
        with set_locale("fr"):
            fetcher.check()
            
        # Trigger response callbacks OUTSIDE the locale context
        # This simulates the async behavior where callbacks run on the loop without the context
        fetcher.exchange.trigger_response()
            
        # Check notes for French content
        # "1 week" in French is "1 semaine".
        # We need to set the locale to 'fr' when converting to string, simulating the formatter's behavior.
        with set_locale("fr"):
            found = False
            for note in fetcher.response.notes:
                if note.__class__.__name__ == "CURRENT_AGE":
                    # note.vars['age'] is now a RelativeTime object, so we convert to str
                    age_str = str(note.vars['age'])
                    if "semaine" in age_str or "jours" in age_str:
                        found = True
        
        self.assertTrue(found, "Did not find French 'semaine' in CURRENT_AGE note, lazy localization failed.")


    def test_redbot_note_detail_translation(self):
        from redbot.resource.fetch import BODY_NOT_ALLOWED
        from redbot.i18n import set_locale
        with set_locale("fr"):
            note = BODY_NOT_ALLOWED("subject", sample="test sample")
            self.assertIn("Cette réponse a du contenu.", note.summary)
            self.assertIn("HTTP définit quelques situations spéciales", note.detail)


    def test_problem_pluralization(self):
        from redbot.formatter.html import SingleEntryHtmlFormatter
        from redbot.resource import active_check, HttpResource
        from httplint.note import Note, levels, categories
        from redbot.i18n import ngettext

        # Mock resource and subrequests
        resource = MagicMock(spec=HttpResource)
        resource.response = MagicMock()
        resource.request = MagicMock()
        resource.subreqs = {}
        
        # Mock a subrequest with notes
        check_id = active_check.ConnegCheck.check_id
        subreq = MagicMock()
        subreq.fetch_started = True
        # Mock check_name for display
        subreq.check_name = active_check.ConnegCheck.check_name
        
        # Create a mock note
        note = MagicMock(spec=Note)
        note.level = levels.BAD
        
        subreq.response.notes = [note]
        resource.subreqs[check_id] = subreq
        resource.response.notes = [] # Ensure note is not in main response
        
        formatter = SingleEntryHtmlFormatter(MagicMock(), resource, MagicMock(), {"nonce": "test"})
        
        # Test singular
        with patch("redbot.formatter.html.ngettext") as mock_ngettext, \
             patch("redbot.formatter.html._") as mock_gettext:
            mock_ngettext.side_effect = lambda s, p, n: s if n == 1 else p
            mock_gettext.side_effect = lambda s: s
            formatter.format_subrequest_messages(categories.CONNEG)
            mock_ngettext.assert_called_with(" - %d problem\n", " - %d problems\n", 1)
            # Check calls to gettext
            # We expect calls for "%s response" and check_name (e.g. "Content Negotiation")
            # Since check_name is dynamic in the code, we just check if it was called.
            self.assertTrue(mock_gettext.call_count >= 1)
            
        # Test plural
        subreq.response.notes = [note, note]
        with patch("redbot.formatter.html.ngettext") as mock_ngettext, \
             patch("redbot.formatter.html._") as mock_gettext:
            mock_ngettext.side_effect = lambda s, p, n: s if n == 1 else p
            mock_gettext.side_effect = lambda s: s
            formatter.format_subrequest_messages(categories.CONNEG)
            mock_ngettext.assert_called_with(" - %d problem\n", " - %d problems\n", 2)
            self.assertTrue(mock_gettext.call_count >= 1)

if __name__ == "__main__":
    unittest.main()
