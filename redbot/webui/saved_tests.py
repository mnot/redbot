from configparser import SectionProxy
import os
import random
import shelve
import string
import time
from typing import TYPE_CHECKING, Tuple, Optional, Callable, cast

from redbot.resource import HttpResource

if TYPE_CHECKING:
    from redbot.webui import RedWebUi


class SavedTests:
    """
    Save test results for later display.
    """

    def __init__(self, config: SectionProxy, console: Callable[[str], None]) -> None:
        self.config = config
        self.console = console
        self.save_db: Optional[shelve.Shelf] = None
        save_dir = config.get("save_dir", "")
        if not save_dir:
            return
        if not os.path.exists(save_dir):
            self.console(f"WARNING: Save directory '{save_dir}' does not exist.")
            return
        try:
            self.save_db = shelve.open(f"{save_dir}/redbot_saved_tests")
        except (OSError, IOError) as why:
            self.console(f"WARNING: Save DB not initialised: {why}")

    def shutdown(self) -> None:
        if self.save_db is not None:
            self.save_db.close()

    def get_test_id(self) -> str:
        """Get a unique test id."""
        test_id = "".join(random.choice(string.ascii_lowercase) for i in range(16))
        if self.save_db is None:
            return test_id
        if test_id in self.save_db.keys():
            return self.get_test_id()
        return test_id

    def save(self, webui: "RedWebUi", top_resource: HttpResource) -> None:
        """Save a test by test_id."""
        if webui.test_id and self.save_db is not None:
            top_resource.save_expires = (
                time.time() + self.config.getint("no_save_mins", fallback=20) * 60
            )
            self.save_db[webui.test_id] = top_resource

    def extend(self, test_id: str) -> None:
        """Extend the expiry time of a previously run test_id."""
        if self.save_db is None:
            return
        entry = self.save_db[test_id]
        entry.save_expires = (
            time.time() + self.config.getint("save_days", fallback=30) * 24 * 60 * 60
        )
        self.save_db[test_id] = entry

    def clean(self) -> Tuple[int, int, int]:
        """Clean old files from the saved tests directory."""
        if self.save_db is None:
            return (0, 0, 0)
        now = time.time()
        count = removed = errors = 0
        for test_id in self.save_db:
            count += 1
            entry = self.save_db[test_id]
            if entry.save_expires < now:
                try:
                    del self.save_db[test_id]
                    removed += 1
                except KeyError:
                    errors += 1
        return (count, removed, errors)

    def load(self, webui: "RedWebUi") -> HttpResource:
        """Return a saved test by test_id."""
        if not webui.test_id or self.save_db is None:
            raise ValueError
        return cast(HttpResource, self.save_db[webui.test_id])
