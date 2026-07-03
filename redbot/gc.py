#!/usr/bin/env python3

"""
One-shot garbage collection for REDbot's saved-tests directory.

Run periodically from an external scheduler (e.g. a systemd timer or cron)
rather than on the daemon's event loop. Doing the filesystem work in a
throwaway process means a slow or stalled `save_dir` can't block the loop
and trip the systemd watchdog. See extra/redbot-gc.{service,timer}.
"""

import argparse
import sys
from configparser import ConfigParser

from redbot.webui.saved_tests import clean_saved_tests


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean old files from REDbot's saved-tests directory."
    )
    parser.add_argument("config_file", type=str, help="configuration file")
    args = parser.parse_args()

    conf = ConfigParser()
    conf.read(args.config_file)

    seen, removed, errors = clean_saved_tests(conf["redbot"])
    sys.stdout.write(f"redbot_gc: {seen} files, {removed} removed, {errors} errors\n")

    # Exit non-zero on errors so the systemd oneshot (and its journal entry)
    # surfaces a stalled/failing save_dir instead of looking like a clean run.
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
