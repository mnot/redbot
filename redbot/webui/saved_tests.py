from configparser import SectionProxy
import gzip
import os
import pickle
import tempfile
import time
from typing import cast, IO, Tuple, Optional
import zlib

from redbot.resource import HttpResource
from redbot.type import RedWebUiProtocol


def init_save_file(webui: RedWebUiProtocol) -> Optional[str]:
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


def save_test(webui: RedWebUiProtocol, top_resource: HttpResource) -> None:
    """Save a test by test_id."""
    if webui.config.get("save_dir", None) and os.path.exists(webui.config["save_dir"]):
        try:
            with cast(IO[bytes], gzip.open(webui.save_path, "w")) as tmp_file:
                pickle.dump(top_resource, tmp_file)
        except (OSError, zlib.error, pickle.PickleError):
            pass  # we don't cry if we can't store it.


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
