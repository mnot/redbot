"""
The text formatter must not pass control characters from a response through to the
terminal (mnot/redbot#448).
"""

import re
import unittest
from configparser import ConfigParser
from typing import List

import thor.http.error as httperr
from httplint.note import categories, levels

from redbot.formatter.text import (
    TextFormatter,
    TextListFormatter,
    VerboseTextFormatter,
    escape_controls,
)
from redbot.note import RedbotNote
from redbot.resource import HttpResource

EVIL = "a\x1b]52;c;ZXZpbA==\x07\x1b[2Jb"
EVIL_ESCAPED = "a\\x1b]52;c;ZXZpbA==\\x07\\x1b[2Jb"

# Anything a terminal might act on, other than tab and newline.
BAD_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
# The formatter's own colour sequences.
OWN_ANSI = re.compile(r"\x1b\[[01];?[0-9]*m")


class EVIL_NOTE(RedbotNote):
    category = categories.GENERAL
    level = levels.WARN
    _summary = "bad value %(value)s"
    _text = "The value was %(value)s, which is bad."


class MULTILINE_NOTE(RedbotNote):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "multi-line note"
    _text = "first line\nsecond line"


def make_resource()-> HttpResource:
    conf = ConfigParser()
    conf.add_section("redbot")
    resource = HttpResource(conf["redbot"])
    resource.request.uri = f"http://example.com/{EVIL}"
    resource.response.process_response_topline(b"1.1", b"200", EVIL.encode("latin-1"))
    resource.response.process_headers(
        [
            (b"X-Evil", EVIL.encode("latin-1")),
            (b"X-C1", b"c1\x9b31m"),
            (b"Content-Type", b"text/plain"),
        ]
    )
    resource.response.complete = True
    return resource


def render(formatter_class: type, resource: HttpResource, tty_out: bool = False) -> str:
    chunks: List[str] = []
    formatter = formatter_class(
        resource.config, resource, chunks.append, {"tty_out": tty_out, "descend": False}
    )
    formatter.bind_resource(resource)
    formatter.finish_output()
    return "".join(chunks)


class TestEscapeControls(unittest.TestCase):
    def test_issue_example(self) -> None:
        self.assertEqual(escape_controls(EVIL), EVIL_ESCAPED)

    def test_c0_c1_and_del(self) -> None:
        self.assertEqual(escape_controls("\x00\x07\x7f\x80\x9b"), "\\x00\\x07\\x7f\\x80\\x9b")

    def test_tab_kept(self) -> None:
        self.assertEqual(escape_controls("a\tb"), "a\tb")

    def test_newlines(self) -> None:
        self.assertEqual(escape_controls("a\r\nb"), "a\\x0d\\x0ab")
        self.assertEqual(escape_controls("a\nb", keep_newlines=True), "a\nb")
        self.assertEqual(escape_controls("a\rb", keep_newlines=True), "a\\x0db")

    def test_ordinary_text_untouched(self) -> None:
        text = "h\u00e9llo ~ \u00a0 \u2603"
        self.assertEqual(escape_controls(text), text)


class TestEscapeInvisibles(unittest.TestCase):
    def test_invisible_and_bidi(self) -> None:
        cases = {
            "bidi marks": ("\u200e\u200f\u061c", "\\u200e\\u200f\\u061c"),
            "bidi embeddings": (
                "\u202a\u202b\u202c\u202d\u202e",
                "\\u202a\\u202b\\u202c\\u202d\\u202e",
            ),
            "bidi isolates": ("\u2066\u2067\u2068\u2069", "\\u2066\\u2067\\u2068\\u2069"),
            "zero-width": ("\u200b\u200c\u200d\u2060", "\\u200b\\u200c\\u200d\\u2060"),
            "invisible operators": (
                "\u2061\u2062\u2063\u2064",
                "\\u2061\\u2062\\u2063\\u2064",
            ),
            "BOM, soft hyphen, Mongolian vowel separator": (
                "\ufeff\u00ad\u180e",
                "\\ufeff\\xad\\u180e",
            ),
            "line and paragraph separators": ("\u2028\u2029", "\\u2028\\u2029"),
            "tag characters": ("\U000e0041\U000e007f", "\\U000e0041\\U000e007f"),
        }
        for name, (raw, escaped) in cases.items():
            with self.subTest(name):
                self.assertEqual(escape_controls(raw), escaped)

    def test_spoofing_example(self) -> None:
        self.assertEqual(escape_controls("evil\u202egnp.exe"), "evil\\u202egnp.exe")

    def test_legitimate_unicode(self) -> None:
        for text in (
            "caf\u00e9 na\u00efve \u00fcber",
            "\u65e5\u672c\u8a9e \u4e2d\u6587 \ud55c\uad6d\uc5b4",
            "\u0645\u0631\u062d\u0628\u0627 \u05e9\u05dc\u05d5\u05dd",
            "\U0001f600 \u2603 \u2764\ufe0f",
            "a\u00a0b\u2003c\tD",
        ):
            with self.subTest(text):
                self.assertEqual(escape_controls(text), text)

    def test_emoji_zwj_escaped(self) -> None:
        "The joiner in an emoji sequence is a Cf character, and is escaped with the rest."
        family = "\U0001f468\u200d\U0001f469\u200d\U0001f467"
        self.assertEqual(
            escape_controls(family), "\U0001f468\\u200d\U0001f469\\u200d\U0001f467"
        )


class TestTextFormatterOutput(unittest.TestCase):
    def check_clean(self, out: str, tty_out: bool = False) -> None:
        if tty_out:
            out = OWN_ANSI.sub("", out)
        self.assertIsNone(BAD_CHARS.search(out), repr(out))

    def test_headers_and_status_phrase(self) -> None:
        out = render(TextFormatter, make_resource())
        self.check_clean(out)
        self.assertIn(f"X-Evil:{EVIL_ESCAPED}", out)
        self.assertIn(f"HTTP/1.1 200 {EVIL_ESCAPED}", out)
        self.assertIn("X-C1:c1\\x9b31m", out)

    def test_bidi_end_to_end(self) -> None:
        resource = make_resource()
        resource.response.status_phrase = "OK\u202e"
        resource.response.headers.text.append(("X-Bidi", "a\u202eb\u200bc\u2028d"))
        resource.response.notes.add("header-x-evil", EVIL_NOTE, value="x\u2066y")
        out = render(VerboseTextFormatter, resource)
        self.assertIn("HTTP/1.1 200 OK\\u202e", out)
        self.assertIn("X-Bidi:a\\u202eb\\u200bc\\u2028d", out)
        self.assertIn("bad value x\\u2066y", out)
        self.assertIn("The value was x\\u2066y", out)
        self.assertIsNone(re.search("[\u202a-\u202e\u2066-\u2069\u200b-\u200f\u2028\u2029]", out))

    def test_header_newline_forgery(self) -> None:
        resource = make_resource()
        resource.response.headers.text.append(("X-Split", "a\r\nHTTP/1.1 200 Forged"))
        out = render(TextFormatter, resource)
        self.assertIn("X-Split:a\\x0d\\x0aHTTP/1.1 200 Forged", out)
        self.assertNotIn("\nHTTP/1.1 200 Forged", out)

    def test_note_summary_and_detail(self) -> None:
        for formatter_class in (TextFormatter, VerboseTextFormatter):
            resource = make_resource()
            resource.response.notes.add("header-x-evil", EVIL_NOTE, value=EVIL)
            for tty_out in (False, True):
                out = render(formatter_class, resource, tty_out)
                self.check_clean(out, tty_out)
                self.assertIn("bad value", out)

    def test_note_detail_charref(self) -> None:
        "A character reference in note text must not become a raw control character."
        resource = make_resource()
        resource.response.notes.add("header-x-evil", EVIL_NOTE, value="&#27;[2J&#7;")
        out = render(VerboseTextFormatter, resource)
        self.check_clean(out)

    def test_own_colours_preserved(self) -> None:
        resource = make_resource()
        resource.response.notes.add("header-x-evil", EVIL_NOTE, value=EVIL)
        out = render(TextFormatter, resource, tty_out=True)
        self.assertIn("\x1b[1;33mbad value " + EVIL_ESCAPED + "\x1b[0;39m", out)

    def test_fetch_error(self) -> None:
        resource = make_resource()
        resource.response.complete = False
        resource.fetch_error = httperr.ConnectError(EVIL)
        out = render(TextFormatter, resource)
        self.check_clean(out)
        self.assertIn(EVIL_ESCAPED, out)

    def test_fetch_error_desc(self) -> None:
        class EvilDescError(httperr.HttpError):
            desc = EVIL

        for detail in (None, EVIL):
            resource = make_resource()
            resource.response.complete = False
            resource.fetch_error = EvilDescError(detail)
            out = render(TextFormatter, resource)
            self.check_clean(out)
            self.assertIn(EVIL_ESCAPED, out)

    def test_note_detail_newlines(self) -> None:
        "A newline in a note's own text is wrapped as whitespace, not shown as an escape."
        resource = make_resource()
        resource.response.notes.add("header-x-evil", MULTILINE_NOTE)
        out = render(VerboseTextFormatter, resource)
        self.assertIn("first line second line", out)
        self.assertNotIn("\\x0a", out)

    def test_error_output(self) -> None:
        resource = make_resource()
        chunks: List[str] = []
        formatter = TextFormatter(resource.config, resource, chunks.append, {})
        formatter.error_output(EVIL)
        self.assertEqual("".join(chunks), f"Error: {EVIL_ESCAPED}\n")

    def test_linked_resources(self) -> None:
        resource = make_resource()
        linked = make_resource()
        resource.linked.append((linked, "link"))
        out = render(TextListFormatter, resource)
        self.check_clean(out)
        self.assertIn(f"http://example.com/{EVIL_ESCAPED}", out)


if __name__ == "__main__":
    unittest.main()
