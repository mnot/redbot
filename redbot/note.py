import re
import secrets
from threading import local

from httplint.note import Note
from markdown import Markdown
from markupsafe import Markup, escape

from redbot.i18n import _, get_locale


class _MdLocal(local):
    md: Markdown


_md_local = _MdLocal()


def _markdown() -> Markdown:
    if not hasattr(_md_local, "md"):
        _md_local.md = Markdown(output_format="html")
    return _md_local.md


class RedbotNote(Note):
    """
    A Note that uses REDbot's translation domain.
    """

    def _get_summary(self) -> str:
        try:
            return str(_(self._summary) % self.vars)
        except TypeError as err:
            raise TypeError(
                f"Summary formatting error in {self.__class__.__name__} "
                f"(locale: {get_locale()}): {err} (vars: {self.vars!r})"
            ) from err

    def _get_detail(self) -> Markup:
        """
        Every var is wire- or otherwise externally-derived data, never
        template text, so none of it is rendered as Markdown: each is
        swapped for an opaque, per-render placeholder token before
        conversion, and the tokens are swapped back for their
        HTML-escaped values afterwards. A var can therefore never be
        parsed as Markdown syntax, regardless of whether the template
        wraps it in a code span, and a value containing its own
        backtick (or brackets, asterisks, etc.) can't break out of one.
        """
        try:
            nonce = secrets.token_hex(16)
            tokens = {name: f"{nonce}:{name}" for name in self.vars}
            html = _markdown().reset().convert(_(self._text) % tokens)
            if tokens:
                values = {token: str(self.vars[name]) for name, token in tokens.items()}
                # Longest first: var names sharing a prefix (range/range_expected)
                # would otherwise let the shorter token match inside the longer one.
                ordered = sorted(values, key=len, reverse=True)
                pattern = re.compile("|".join(re.escape(token) for token in ordered))
                html = pattern.sub(lambda m: str(escape(values[m.group(0)])), html)
            return Markup(html)
        except TypeError as err:
            raise TypeError(
                f"Detail formatting error in {self.__class__.__name__} "
                f"(locale: {get_locale()}): {err} (vars: {self.vars!r})"
            ) from err

    summary = property(_get_summary)
    detail = property(_get_detail)
