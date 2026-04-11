from httplint.note import Note
from markupsafe import Markup, escape

from redbot.i18n import _, get_locale


class RedbotNote(Note):
    """
    A Note that uses REDbot's translation domain.
    """

    def _get_summary(self) -> Markup:
        try:
            return Markup(_(self._summary) % self.vars)
        except TypeError as err:
            raise TypeError(
                f"Summary formatting error in {self.__class__.__name__} "
                f"(locale: {get_locale()}): {err} (vars: {self.vars!r})"
            ) from err

    def _get_detail(self) -> Markup:
        try:
            return Markup(
                self._markdown.reset().convert(
                    _(self._text) % {k: escape(str(v)) for k, v in self.vars.items()}
                )
            )
        except TypeError as err:
            raise TypeError(
                f"Detail formatting error in {self.__class__.__name__} "
                f"(locale: {get_locale()}): {err} (vars: {self.vars!r})"
            ) from err

    summary = property(_get_summary)
    detail = property(_get_detail)
