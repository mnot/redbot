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
        try:
            return Markup(
                _markdown()
                .reset()
                .convert(_(self._text) % {k: escape(str(v)) for k, v in self.vars.items()})
            )
        except TypeError as err:
            raise TypeError(
                f"Detail formatting error in {self.__class__.__name__} "
                f"(locale: {get_locale()}): {err} (vars: {self.vars!r})"
            ) from err

    summary = property(_get_summary)
    detail = property(_get_detail)
