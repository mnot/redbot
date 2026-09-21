import re
import secrets
from threading import local
from typing import Dict, Match

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


# Matches a single "%(name)[flags][width][.precision]conv" directive, e.g.
# "%(range_expected).100s". Used to evaluate each directive against the real
# value *before* Markdown ever sees the template -- see RedbotNote.detail.
_DIRECTIVE_RE = re.compile(r"%\((\w+)\)([-+0 #]*)(\d*)(\.\d+)?([a-zA-Z])")


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

    @property
    def detail(self) -> Markup:
        """
        Every var is wire- or otherwise externally-derived data, never
        template text, so none of it is rendered as Markdown.

        Each %(name)... directive -- including any width, flags or
        precision it carries -- is evaluated against the real value up
        front, exactly as Python's `%` operator would, and the
        resulting string is HTML-escaped and hidden behind an opaque,
        per-occurrence placeholder token before Markdown ever sees the
        template. Only tokens are substituted for Markdown conversion;
        the real (already-formatted) values are spliced into the
        rendered HTML afterwards. This handles any directive a
        template might use (not just bare %(name)s) the same way it
        would have behaved outside this scheme, while guaranteeing
        that no var -- or anything a format spec does to it -- can be
        parsed as Markdown syntax, and that a value containing its own
        backtick (or brackets, asterisks, etc.) can't break out of a
        code span.

        Cached per locale, not just per instance: _text/vars never
        change after construction, but the active i18n locale can, so
        a plain identity-keyed cache would risk serving one locale's
        rendering when another is asked for.
        """
        cache = self.__dict__.setdefault("_detail_cache", {})
        locale = get_locale()
        if locale not in cache:
            cache[locale] = self._render_detail()
        return cache[locale]  # type: ignore[no-any-return]

    def _render_detail(self) -> Markup:
        try:
            text = str(_(self._text))
            nonce = secrets.token_hex(16)
            values: Dict[str, str] = {}

            def _tokenize(match: Match[str]) -> str:
                name, flags, width, precision, conv = match.groups()
                spec = f"%{flags}{width}{precision or ''}{conv}"
                formatted = spec % (self.vars[name],)
                token = f"{nonce}:{len(values)}"
                values[token] = formatted
                return token

            tokenized_text = _DIRECTIVE_RE.sub(_tokenize, text)
            # No %(name)... directives remain; this only resolves any
            # literal "%%" left in the template into "%".
            html = _markdown().reset().convert(tokenized_text % {})
            if values:
                # Longest first: occurrence tokens share a "nonce:" prefix,
                # so e.g. token "…:1" would otherwise match inside "…:10".
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
