import gzip
import os
import pickle
import tempfile
from typing import TYPE_CHECKING
import zlib

import thor

from redbot.formatter import Formatter, find_formatter

if TYPE_CHECKING:
    from redbot.webui import RedWebUi  # pylint: disable=cyclic-import,unused-import


def init_save_file(webui: "RedWebUi") -> str:
    if webui.config.get("save_dir", "") and os.path.exists(webui.config["save_dir"]):
        try:
            fd, webui.save_path = tempfile.mkstemp(
                prefix="", dir=webui.config["save_dir"]
            )
            return os.path.split(webui.save_path)[1]
        except (OSError, IOError):
            # Don't try to store it.
            pass
    return None  # should already be None, but make sure


def save_test(webui: "RedWebUi", top_resource: Formatter) -> None:
    """Save a test by test_id."""
    if webui.test_id:
        try:
            tmp_file = gzip.open(webui.save_path, "w")
            pickle.dump(top_resource, tmp_file)
            tmp_file.close()
        except (IOError, zlib.error, pickle.PickleError):
            pass  # we don't cry if we can't store it.


def extend_saved_test(webui: "RedWebUi") -> None:
    """Extend the expiry time of a previously run test_id."""
    try:
        # touch the save file so it isn't deleted.
        os.utime(
            os.path.join(webui.config["save_dir"], webui.test_id),
            (
                thor.time(),
                thor.time() + (int(webui.config["save_days"]) * 24 * 60 * 60),
            ),
        )
        location = b"?id=%s" % webui.test_id.encode("ascii")
        if webui.descend:
            location = b"%s&descend=True" % location
        webui.response_start(b"303", b"See Other", [(b"Location", location)])
        webui.response_body(
            "Redirecting to the saved test page...".encode(webui.config["charset"])
        )
    except (OSError, IOError):
        webui.response_start(
            b"500",
            b"Internal Server Error",
            [(b"Content-Type", b"text/html; charset=%s" % webui.charset_bytes)],
        )
        webui.response_body(webui.show_error("Sorry, I couldn't save that."))
    webui.response_done([])


def load_saved_test(webui: "RedWebUi") -> None:
    """Load a saved test by test_id."""
    try:
        fd = gzip.open(
            os.path.join(webui.config["save_dir"], os.path.basename(webui.test_id))
        )
        mtime = os.fstat(fd.fileno()).st_mtime
    except (OSError, IOError, TypeError, zlib.error):
        webui.response_start(
            b"404",
            b"Not Found",
            [
                (b"Content-Type", b"text/html; charset=%s" % webui.charset_bytes),
                (b"Cache-Control", b"max-age=600, must-revalidate"),
            ],
        )
        webui.response_body(
            webui.show_error("I'm sorry, I can't find that saved response.")
        )
        webui.response_done([])
        return
    is_saved = mtime > thor.time()
    try:
        top_resource = pickle.load(fd)
    except (pickle.PickleError, IOError, EOFError):
        webui.response_start(
            b"500",
            b"Internal Server Error",
            [
                (b"Content-Type", b"text/html; charset=%s" % webui.charset_bytes),
                (b"Cache-Control", b"max-age=600, must-revalidate"),
            ],
        )
        webui.response_body(
            webui.show_error("I'm sorry, I had a problem loading that.")
        )
        webui.response_done([])
        return
    finally:
        fd.close()

    if webui.check_name:
        display_resource = top_resource.subreqs.get(webui.check_name, top_resource)
    else:
        display_resource = top_resource

    formatter = find_formatter(webui.format, "html", top_resource.descend)(
        webui.config,
        webui.output,
        allow_save=(not is_saved),
        is_saved=True,
        test_id=webui.test_id,
    )

    webui.response_start(
        b"200",
        b"OK",
        [
            (b"Content-Type", formatter.content_type()),
            (b"Cache-Control", b"max-age=3600, must-revalidate"),
        ],
    )

    @thor.events.on(formatter)
    def formatter_done() -> None:
        webui.response_done([])

    formatter.bind_resource(display_resource)
