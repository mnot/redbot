from httplint.note import Note
from markupsafe import Markup, escape
from redbot.i18n import _


class RedbotNote(Note):
    """
    A Note that uses REDbot's translation domain.
    """

    def _get_summary(self) -> Markup:
        return Markup(_(self._summary) % self.vars)

    def _get_detail(self) -> Markup:
        return Markup(
            self._markdown.reset().convert(
                _(self._text) % {k: escape(str(v)) for k, v in self.vars.items()}
            )
        )

    summary = property(_get_summary)
    detail = property(_get_detail)
