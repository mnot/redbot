#!/usr/bin/env python

__author__ = "Mark Nottingham <mnot@mnot.net>"
__copyright__ = """\
Copyright (c) 2008-2014 Mark Nottingham

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import gzip
import os
from os import path
import zlib

import thor

class CacheFile(object):
    """
    A gzipped cache file whose unix modification time indicates how long it
    is fresh for. No locking, so errors are discarded.
    """

    def __init__(self, my_path):
        self.path = my_path

    def read(self):
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
            is_fresh = mtime > thor.time()
            if not is_fresh:
                self.delete()
                return None
            content = fd.read()
        except IOError:
            self.delete()
            return None
        finally:
            fd.close()
        return content


    def write(self, content, lifetime):
        """
        Write content to the file, marking it fresh for lifetime seconds.
        Discard errors silently.
        """
        try:
            fd = gzip.open(self.path, 'w')
            fd.write(content)
        except (OSError, IOError, zlib.error):
            return
        finally:
            fd.close()
        os.utime(self.path, (
                thor.time(),
                thor.time() + lifetime
            )
        )

    def delete(self):
        "Remove the file, discarding errors silently."
        try:
            os.remove(self.path)
        except:
            pass
