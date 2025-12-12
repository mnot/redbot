"""
Formatters for REDbot output.
"""

from collections import defaultdict
from configparser import SectionProxy
import inspect
import locale
import sys
import time
from typing import Optional, Any, Callable, List, Dict, Tuple, Type, TYPE_CHECKING
import unittest

from babel.numbers import format_decimal
from markdown import Markdown
import thor
from thor.events import EventEmitter
from typing_extensions import TypedDict
from httplint.util import relative_time as _relative_time

from redbot.i18n import get_locale, set_locale

if TYPE_CHECKING:
    from redbot.resource import HttpResource  # pylint: disable=cyclic-import

_formatters = ["html", "text", "har"]


def find_formatter(
    name: str, default: str = "html", multiple: bool = False
) -> Type["Formatter"]:
    """
    Find the formatter for name, and use default if it can't be found.
    If you need to represent more than one result, set multiple to True.

    Note that you MUST "from redbot.formatter import *" before calling.
    Yes, that's a hack that needs to be fixed.
    """
    if name not in _formatters:
        name = default
    try:
        module_name = f"redbot.formatter.{name}"
        __import__(module_name)
        module = sys.modules[module_name]
    except (ImportError, KeyError, TypeError):
        return find_formatter(default)
    formatter_candidates = [
        v
        for k, v in list(module.__dict__.items())
        if inspect.isclass(v)
        and issubclass(v, Formatter)
        and getattr(v, "name") == name
    ]
    # find single-preferred formatters first
    if not multiple:
        for candidate in formatter_candidates:
            if not candidate.can_multiple:
                return candidate
    for candidate in formatter_candidates:
        if candidate.can_multiple:
            return candidate
    raise RuntimeError(f"Can't find a format in {_formatters}")


def available_formatters() -> List[str]:
    """
    Return a list of the available formatter names.

    Note that you MUST "from redbot.formatter import *" before calling.
    Yes, that's a hack that needs to be fixed.
    """
    return _formatters


class FormatterParams(TypedDict):
    config: SectionProxy
    resource: "HttpResource"
    output: Callable[[str], None]
    params: Dict[str, Any]


FormatterArgs = Tuple[
    SectionProxy, "HttpResource", Callable[[str], None], Dict[str, Any]
]


class Formatter(EventEmitter):
    """
    A formatter for HttpResources.

    Is available to UIs based upon the 'name' attribute.
    """

    media_type: str  # the media type of the format.
    name: str = "base class"  # the name of the format.
    can_multiple = False  # formatter can represent multiple responses.

    def __init__(
        self,
        config: SectionProxy,
        resource: "HttpResource",
        output: Callable[[str], None],
        params: Dict[str, Any],
    ) -> None:
        """
        Formatter for the given URI, writing
        to the callable output(uni_str). Output is Unicode; callee
        is responsible for encoding correctly.
        """
        EventEmitter.__init__(self)
        self.config = config
        self.resource = resource
        self.output = output  # output file object
        self.kw = params
        self._markdown = Markdown(output_format="html")
        self.locale = params.get("locale", "en")

    def _wrap_context(self, func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with set_locale(self.locale):
                return func(*args, **kwargs)

        return wrapper

    def bind_resource(self, display_resource: "HttpResource") -> None:
        """
        Bind a resource to the formatter, listening for nominated events
        and calling the corresponding methods.
        """
        self.resource = display_resource
        if display_resource.check_done:
            with set_locale(self.locale):
                self.start_output()
            self._done()
        else:
            if display_resource.request.complete:
                with set_locale(self.locale):
                    self.start_output()
            else:
                display_resource.on(
                    "response_headers_available", self._wrap_context(self.start_output)
                )
            display_resource.response_content_processors.append(
                self._wrap_context(self.feed)
            )
            display_resource.on("status", self._wrap_context(self.status))
            display_resource.on("debug", self.debug)

            # we want to wait just a little bit, for extra data.
            @thor.events.on(display_resource)
            def check_done() -> None:
                thor.schedule(0.1, self._done)

    def _done(self) -> None:
        with set_locale(self.locale):
            self.finish_output()
        self.emit("formatter_done")

    def start_output(self) -> None:
        """
        Send preliminary output.
        """
        raise NotImplementedError

    def feed(self, sample: bytes) -> None:
        """
        Feed a body sample to processor(s).
        """
        raise NotImplementedError

    def status(self, status: str) -> None:
        """
        Output a status message.
        """
        raise NotImplementedError

    def debug(self, message: str) -> None:
        """
        Debug to console.
        """
        return

    def finish_output(self) -> None:
        """
        Finalise output.
        """
        raise NotImplementedError

    def error_output(self, message: str) -> None:
        """
        Output an error.
        """
        raise NotImplementedError

    def content_type(self) -> bytes:
        """
        Return binary suitable for the value of a Content-Type header field.
        """
        return (
            f"{self.media_type}; charset={self.config.get('charset', 'utf-8')}".encode(
                "ascii"
            )
        )


def f_num(i: int, by1024: bool = False) -> str:
    "Format a number according to the locale."
    current_locale = get_locale()
    if by1024:
        kilo = int(i / 1024)
        mega = int(kilo / 1024)
        giga = int(mega / 1024)
        if giga:
            return format_decimal(giga, locale=current_locale) + "g"
        if mega:
            return format_decimal(mega, locale=current_locale) + "m"
        if kilo:
            return format_decimal(kilo, locale=current_locale) + "k"
    return format_decimal(i or 0, locale=current_locale)


def relative_time(utime: float, now: Optional[float] = None, show_sign: int = 1) -> Any:
    """
    Given two times, return a string that explains how far apart they are.
    show_sign can be:
        0 - don't show
        1 - ago / from now  [DEFAULT]
        2 - early / late
    """
    if now is None:
        now = time.time()
    return _relative_time(utime, now, show_sign)
