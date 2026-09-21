from httplint.note import Note

from redbot.i18n import _


class RedbotNote(Note):
    """
    A Note that uses REDbot's translation domain.
    """

    def _translate(self, message: str) -> str:
        return str(_(message))
