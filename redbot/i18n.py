"""
Internationalization for REDbot.
"""

from contextlib import contextmanager
from contextvars import ContextVar
import os
from typing import Union, Generator, Any
from babel.support import Translations, NullTranslations
from httplint.i18n import set_locale as httplint_set_locale

_LOCALE: ContextVar[str] = ContextVar("locale", default="en")
LOCALE_DIR = os.path.join(os.path.dirname(__file__), "translations")

AVAILABLE_LOCALES = ["en", "fr"]
DEFAULT_LOCALE = "en"


@contextmanager
def set_locale(locale: str) -> Generator[None, None, None]:
    """
    Set the locale for the current context.
    """
    token = _LOCALE.set(locale)
    with httplint_set_locale(locale):
        try:
            yield
        finally:
            _LOCALE.reset(token)


def get_locale() -> str:
    """
    Get the current locale.
    """
    return _LOCALE.get()


class LazyProxy:
    def __init__(self, message: str):
        self.message = message

    def __str__(self) -> str:
        return str(get_translator().ugettext(self.message))

    def __mod__(self, other: object) -> str:
        return str(self) % other

    def __repr__(self) -> str:
        return f"LazyProxy({self.message!r})"


def _(message: str) -> Any:
    """
    Mark a string for translation, and translate it lazily.
    """
    return LazyProxy(message)


def ngettext(singular: str, plural: str, num: int) -> str:
    """
    Translate a plural string.
    """
    return get_translator().ungettext(singular, plural, num)


def get_translator() -> Union[Translations, NullTranslations]:
    """
    Get the translator for the current locale.
    """
    locale = get_locale()
    # In a real implementation, we would cache these
    return Translations.load(LOCALE_DIR, [locale])
