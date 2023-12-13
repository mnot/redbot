import gzip
import os
from os import path
import time
from typing import Optional
import zlib


class CacheFile:
    """
    A gzipped cache file whose unix modification time indicates how long it
    is fresh for. No locking, so errors are discarded.
    """

    def __init__(self, my_path: str) -> None:
        self.path = my_path

    def read(self) -> Optional[bytes]:
        """
        Read the file, returning its contents. If it does not exist or
        cannot be read, returns None.
        """
        if not path.exists(self.path):
            return None

        try:
            fd = gzip.open(self.path)
        except (OSError, IOError, zlib.error):
            self.delete()
            return None

        try:
            mtime = os.fstat(fd.fileno()).st_mtime
            is_fresh = mtime > time.time()
            if not is_fresh:
                self.delete()
                return None
            content = fd.read()
        except IOError:
            self.delete()
            return None
        finally:
            if "fd" in locals():
                fd.close()
        return content

    def write(self, content: bytes, lifetime: int) -> None:
        """
        Write content to the file, marking it fresh for lifetime seconds.
        Discard errors silently.
        """
        try:
            fd = gzip.open(self.path, "w")
            fd.write(content)
            now = time.time()
            os.utime(self.path, (now, now + lifetime))
        except (OSError, IOError, zlib.error):
            return
        finally:
            if "fd" in locals():
                fd.close()

    def delete(self) -> None:
        "Remove the file, discarding errors silently."
        try:
            os.remove(self.path)
        except (OSError, IOError):
            pass
