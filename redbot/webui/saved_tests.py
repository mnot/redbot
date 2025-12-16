from configparser import SectionProxy
import gzip
import os
import pickle
import tempfile
import time
from typing import TYPE_CHECKING, cast, IO, Tuple, Optional
import zlib

import thor

from redbot.formatter import find_formatter
from redbot.resource import HttpResource

if TYPE_CHECKING:
    from redbot.webui import RedWebUi  # pylint: disable=cyclic-import,unused-import


def init_save_file(webui: "RedWebUi") -> Optional[str]:
    if webui.config.get("save_dir", None) and os.path.exists(webui.config["save_dir"]):
        try:
            fd, webui.save_path = tempfile.mkstemp(
                prefix="", dir=webui.config["save_dir"]
            )
            os.close(fd)
            return os.path.split(webui.save_path)[1]
        except OSError:
            # Don't try to store it.
            pass
    return None  # should already be None, but make sure


def save_test(webui: "RedWebUi", top_resource: HttpResource) -> None:
    """Save a test by test_id."""
    if webui.config.get("save_dir", None) and os.path.exists(webui.config["save_dir"]):
        try:
            with cast(IO[bytes], gzip.open(webui.save_path, "w")) as tmp_file:
                pickle.dump(top_resource, tmp_file)
        except (OSError, zlib.error, pickle.PickleError):
            pass  # we don't cry if we can't store it.


def extend_saved_test(webui: "RedWebUi") -> None:
    """Extend the expiry time of a previously run test_id."""
    test_id = webui.query_string.get("id", [None])[0]
    assert test_id, "test_id not set in extend_saved_test"
    try:
        # touch the save file so it isn't deleted.
        now = time.time()
        state_dir = webui.config.get("save_dir", "")
        if not os.path.exists(state_dir):
            raise OSError
        os.utime(
            os.path.join(state_dir, test_id),
            (
                now,
                now + (webui.config.getint("save_days", fallback=30) * 24 * 60 * 60),
            ),
        )
        location = b"?id=%s" % test_id.encode("ascii")
        if "descend" in webui.query_string:
            location = b"%s&descend=True" % location
        webui.exchange.response_start(b"303", b"See Other", [(b"Location", location)])
        webui.output("Redirecting to the saved test page...")
    except OSError:
        webui.exchange.response_start(
            b"500",
            b"Internal Server Error",
            [(b"Content-Type", b"text/html; charset=%s" % webui.charset_bytes)],
        )
        webui.output("Sorry, I couldn't save that.")
    webui.exchange.response_done([])


def clean_saved_tests(config: SectionProxy) -> Tuple[int, int, int]:
    """Clean old files from the saved tests directory."""
    now = time.time()
    state_dir = config.get("save_dir", "")
    if not os.path.exists(state_dir):
        return (0, 0, 0)
    save_secs = config.getint("no_save_mins", fallback=20) * 60
    files = [
        os.path.join(state_dir, f)
        for f in os.listdir(state_dir)
        if os.path.isfile(os.path.join(state_dir, f))
    ]
    removed = 0
    errors = 0
    for path in files:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            errors += 1
            continue
        if now - mtime > save_secs:
            try:
                os.remove(path)
                removed += 1
            except OSError:
                errors += 1
                continue
    return (len(files), removed, errors)


def load_saved_test(webui: "RedWebUi") -> None:
    """Load a saved test by test_id."""
    test_id = webui.query_string.get("id", [None])[0]
    assert test_id, "test_id not set in load_saved_test"
    state_dir = webui.config.get("save_dir", "")
    if not os.path.exists(state_dir):
        webui.exchange.response_start(
            b"404",
            b"Not Found",
            [
                (b"Content-Type", b"text/html; charset=%s" % webui.charset_bytes),
                (b"Cache-Control", b"max-age=600, must-revalidate"),
            ],
        )
        webui.output("Saving not configured.")
        webui.exchange.response_done([])
        return
    try:
        with cast(
            IO[bytes],
            gzip.open(os.path.join(state_dir, os.path.basename(test_id))),
        ) as fd:
            mtime = os.fstat(fd.fileno()).st_mtime
            is_saved = mtime > time.time()
            top_resource = pickle.load(fd)
    except (OSError, TypeError):
        webui.exchange.response_start(
            b"404",
            b"Not Found",
            [
                (b"Content-Type", b"text/html; charset=%s" % webui.charset_bytes),
                (b"Cache-Control", b"max-age=600, must-revalidate"),
            ],
        )
        webui.output("I'm sorry, I can't find that saved response.")
        webui.exchange.response_done([])
        return
    except (pickle.PickleError, zlib.error, EOFError):
        webui.exchange.response_start(
            b"500",
            b"Internal Server Error",
            [
                (b"Content-Type", b"text/html; charset=%s" % webui.charset_bytes),
                (b"Cache-Control", b"max-age=600, must-revalidate"),
            ],
        )
        webui.output("I'm sorry, I had a problem loading that.")
        webui.exchange.response_done([])
        return

    if "check_name" in webui.query_string:
        check_name = webui.query_string.get("check_name", [None])[0]
        display_resource = top_resource.subreqs.get(check_name, top_resource)
    else:
        display_resource = top_resource

    format_ = webui.query_string.get("format", ["html"])[0]
    formatter = find_formatter(format_, "html", top_resource.descend)(
        webui.config,
        display_resource,
        webui.output,
        {
            "allow_save": (not is_saved),
            "is_saved": True,
            "save_mtime": mtime,
            "test_id": test_id,
            "nonce": webui.nonce,
        },
    )

    webui.exchange.response_start(
        b"200",
        b"OK",
        [
            (b"Content-Type", formatter.content_type()),
            (b"Cache-Control", b"max-age=3600, must-revalidate"),
        ],
    )

    @thor.events.on(formatter)
    def formatter_done() -> None:
        webui.exchange.response_done([])

    formatter.bind_resource(display_resource)
