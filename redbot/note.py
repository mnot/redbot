from httplint.note import Note
from redbot.i18n import _


class RedbotNote(Note):
    """
    A Note that uses REDbot's translation domain.
    """

    @property
    def summary(self) -> str:
        return str(_(self._summary) % self.vars)

    @property
    def text(self) -> str:
        return str(_(self._text) % self.vars)
