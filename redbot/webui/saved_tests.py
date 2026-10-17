import gzip
import os
import pickle
import re
import tempfile
import time
import traceback
from configparser import SectionProxy
from typing import IO, Optional, Tuple, cast

from redbot.resource import HttpResource
from redbot.type import RedWebUiProtocol

_TEST_ID_RE = re.compile(r"[A-Za-z0-9_]+")


def valid_test_id(test_id: str) -> bool:
    "Whether test_id could be a name made by init_save_file (a tempfile.mkstemp name)."
    return _TEST_ID_RE.fullmatch(test_id) is not None


def init_save_file(webui: RedWebUiProtocol) -> Optional[str]:
    if webui.config.get("save_dir", None) and os.path.exists(webui.config["save_dir"]):
        try:
            fd, webui.save_path = tempfile.mkstemp(prefix="", dir=webui.config["save_dir"])
            os.close(fd)
            return os.path.split(webui.save_path)[1]
        except OSError as why:
            webui.error_log(f"Can't create a file in save_dir, so tests won't be saved: {why}")
    return None


def save_test(webui: RedWebUiProtocol, top_resource: HttpResource) -> None:
    """Save a test by test_id."""
    if not webui.save_path:
        return  # init_save_file couldn't make a file
    if webui.config.get("save_dir", None) and os.path.exists(webui.config["save_dir"]):
        try:
            with cast(IO[bytes], gzip.open(webui.save_path, "w")) as tmp_file:
                pickle.dump(top_resource, tmp_file)
        except Exception:  # pylint: disable=broad-exception-caught
            # Pickling can fail in many ways, and saving must never take down the daemon.
            webui.error_log(
                f"Can't save test {os.path.basename(webui.save_path)}:\n{traceback.format_exc()}"
            )
            try:
                os.remove(webui.save_path)  # don't leave a file that can't be loaded
            except OSError:
                pass


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
