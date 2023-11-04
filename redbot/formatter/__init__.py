"""
Formatters for REDbot output.
"""


from collections import defaultdict
from configparser import SectionProxy
import inspect
import locale
import sys
import time
from typing import Any, Callable, List, Dict, Type, TYPE_CHECKING
import unittest

from markdown import Markdown
import thor
from thor.events import EventEmitter

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


class Formatter(EventEmitter):
    """
    A formatter for HttpResources.

    Is available to UIs based upon the 'name' attribute.
    """

    media_type: str = None  # the media type of the format.
    name: str = None  # the name of the format.
    can_multiple = False  # formatter can represent multiple responses.

    def __init__(
        self,
        config: SectionProxy,
        resource: "HttpResource",
        output: Callable[[str], None],
        **kw: Any,
    ) -> None:
        """
        Formatter for the given URI, writing
        to the callable output(uni_str). Output is Unicode; callee
        is responsible for encoding correctly.
        """
        EventEmitter.__init__(self)
        self.config = config
        self.resource = resource
        self.lang = config["lang"]
        self.output = output  # output file object
        self.kw = kw  # extra keyword arguments
        self._markdown = Markdown(output_format="html")

    def bind_resource(self, display_resource: "HttpResource") -> None:
        """
        Bind a resource to the formatter, listening for nominated events
        and calling the corresponding methods.
        """
        self.resource = display_resource
        if display_resource.check_done:
            self.start_output()
            self._done()
        else:
            if display_resource.request.complete:
                self.start_output()
            else:
                display_resource.on("response_headers_available", self.start_output)
            display_resource.response_content_processors.append(self.feed)
            display_resource.on("status", self.status)
            display_resource.on("debug", self.debug)

            # we want to wait just a little bit, for extra data.
            @thor.events.on(display_resource)
            def check_done() -> None:
                thor.schedule(0.1, self._done)

    def _done(self) -> None:
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
        Debug output.
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
        return f"{self.media_type}; charset={self.config['charset']}".encode("ascii")


def f_num(i: int, by1024: bool = False) -> str:
    "Format a number according to the locale."
    if by1024:
        kilo = int(i / 1024)
        mega = int(kilo / 1024)
        giga = int(mega / 1024)
        if giga:
            return locale.format_string("%d", giga, grouping=True) + "g"
        if mega:
            return locale.format_string("%d", mega, grouping=True) + "m"
        if kilo:
            return locale.format_string("%d", kilo, grouping=True) + "k"
    return locale.format_string("%d", i, grouping=True)


def relative_time(utime: float, now: float = None, show_sign: int = 1) -> str:
    """
    Given two times, return a string that explains how far apart they are.
    show_sign can be:
        0 - don't show
        1 - ago / from now  [DEFAULT]
        2 - early / late
    """

    signs = {
        0: ("0", "", ""),
        1: ("now", "ago", "from now"),
        2: ("none", "behind", "ahead"),
    }

    if utime is None:
        return None
    if now is None:
        now = time.time()
    age = round(now - utime)
    if age == 0:
        return signs[show_sign][0]

    aa = abs(age)
    yrs = int(aa / 60 / 60 / 24 / 365)
    day = int(aa / 60 / 60 / 24) % 365
    hrs = int(aa / 60 / 60) % 24
    mnt = int(aa / 60) % 60
    sec = int(aa % 60)

    if age > 0:
        sign = signs[show_sign][1]
    else:
        sign = signs[show_sign][2]
    if not sign:
        sign = signs[show_sign][0]

    arr = []
    if yrs == 1:
        arr.append(str(yrs) + " year")
    elif yrs > 1:
        arr.append(str(yrs) + " years")
    if day == 1:
        arr.append(str(day) + " day")
    elif day > 1:
        arr.append(str(day) + " days")
    if hrs:
        arr.append(str(hrs) + " hr")
    if mnt:
        arr.append(str(mnt) + " min")
    if sec:
        arr.append(str(sec) + " sec")
    arr = arr[:2]  # resolution
    if show_sign:
        arr.append(sign)
    return " ".join(arr)


class RelativeTimeTester(unittest.TestCase):
    minute = 60
    hour = minute * 60
    day = hour * 24
    year = day * 365
    cases = [
        (+year, "1 year from now"),
        (-year, "1 year ago"),
        (+year + 1, "1 year 1 sec from now"),
        (+year + 0.9, "1 year 1 sec from now"),
        (+year + day, "1 year 1 day from now"),
        (+year + (10 * day), "1 year 10 days from now"),
        (+year + (90 * day) + (3 * hour), "1 year 90 days from now"),
        (+(13 * day) - 0.4, "13 days from now"),
    ]

    def setUp(self) -> None:
        self.now = time.time()

    def test_relative_time(self) -> None:
        for delta, result in self.cases:
            self.assertEqual(relative_time(self.now + delta, self.now), result)
