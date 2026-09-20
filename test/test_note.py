"""
Tests for RedbotNote's Markdown/HTML escaping of interpolated vars.

RedbotNote._get_detail() must never let a wire-supplied var be parsed as
Markdown, whether or not the template wraps it in a code span.
"""

import unittest

from httplint.note import categories, levels

from redbot.note import RedbotNote


class UNPROTECTED(RedbotNote):
    """A var used in plain prose, like RANGE_INCORRECT's range_expected/received."""

    category = categories.GENERAL
    level = levels.INFO
    _summary = "unprotected"
    _text = """\
REDbot expected:

> %(expected)s

REDbot received:

> %(received)s"""


class CODE_SPAN(RedbotNote):
    """A var wrapped in a code span, like conneg.py's negotiated_val."""

    category = categories.GENERAL
    level = levels.INFO
    _summary = "code span"
    _text = "Negotiated: `%(negotiated_val)s`"


class PREFIXED_VARS(RedbotNote):
    """Var names that are prefixes of one another, like range/range_expected."""

    category = categories.GENERAL
    level = levels.INFO
    _summary = "prefixed"
    _text = "a=%(range)s b=%(range_expected)s c=%(range_expected_bytes)s"


class NO_VARS(RedbotNote):
    category = categories.GENERAL
    level = levels.INFO
    _summary = "no vars"
    _text = "Nothing to interpolate here."


class TestNoteEscaping(unittest.TestCase):
    def test_markdown_link_in_plain_text_is_inert(self) -> None:
        note = UNPROTECTED(
            "subject",
            expected="ok",
            received="[click me](javascript:alert(1))",
        )
        html = str(note.detail)
        self.assertNotIn('href="javascript', html)
        self.assertIn("[click me](javascript:alert(1))", html)

    def test_html_tag_in_var_is_escaped(self) -> None:
        note = UNPROTECTED(
            "subject",
            expected="ok",
            received="<script>alert(1)</script>",
        )
        html = str(note.detail)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_embedded_backtick_cannot_escape_code_span(self) -> None:
        note = CODE_SPAN("subject", negotiated_val="a`</code><script>alert(1)</script>")
        html = str(note.detail)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        # The literal backtick survives (isn't stripped), since it's never
        # parsed as Markdown syntax.
        self.assertIn("a`", html)

    def test_prefixed_var_names_do_not_collide(self) -> None:
        note = PREFIXED_VARS(
            "subject",
            range="RANGEVAL",
            range_expected="EXPECTEDVAL",
            range_expected_bytes="BYTESVAL",
        )
        html = str(note.detail)
        self.assertIn("a=RANGEVAL", html)
        self.assertIn("b=EXPECTEDVAL", html)
        self.assertIn("c=BYTESVAL", html)

    def test_no_vars_renders_normally(self) -> None:
        note = NO_VARS("subject")
        self.assertIn("Nothing to interpolate here.", str(note.detail))


if __name__ == "__main__":
    unittest.main()
