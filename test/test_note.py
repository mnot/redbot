"""
RedbotNote no longer implements its own Markdown-escaping logic (see
mnot/redbot#431 and mnot/httplint#158/#160/#161): it relies entirely on
httplint's Note for rendering, overriding only _translate() to use redbot's
own message catalog. httplint has its own comprehensive tests for the
escaping mechanism itself; this file just guards against RedbotNote
reintroducing a custom, unsafe override of that behavior.
"""

import unittest

from httplint.note import categories, levels

from redbot.note import RedbotNote


class INJECTION_PRONE(RedbotNote):
    """A var used in plain prose, unprotected by a backtick span -- the
    shape of template that caused the original bug."""

    category = categories.GENERAL
    level = levels.INFO
    _summary = "injection prone"
    _text = "value: %(value)s"


class TestRedbotNoteRendering(unittest.TestCase):
    def test_markdown_injection_is_neutralized(self) -> None:
        note = INJECTION_PRONE("subject", value="[x](javascript:alert(1))")
        html = str(note.detail)
        self.assertNotIn('href="javascript', html)


if __name__ == "__main__":
    unittest.main()
