#!/usr/bin/env python

"""
CLI interface to REDbot
"""

from configparser import ConfigParser
from argparse import ArgumentParser
import sys

import thor

from redbot import __version__
from redbot.formatter import find_formatter, available_formatters
from redbot.resource import HttpResource


def main() -> None:
    parser = ArgumentParser()
    parser.set_defaults(
        version=False, descend=False, output_format="text", show_recommendations=False
    )

    parser.add_argument("url", help="URL to check")

    parser.add_argument(
        "-a",
        "--assets",
        action="store_true",
        dest="descend",
        help="check assets, if the response contains HTML",
    )
    parser.add_argument(
        "-o",
        "--output-format",
        action="store",
        dest="output_format",
        choices=available_formatters(),
        default="text",
        help="output format",
    )
    args = parser.parse_args()

    config_parser = ConfigParser()
    config_parser.read_dict({"redbot": {"enable_local_access": "True"}})
    config = config_parser["redbot"]

    resource = HttpResource(config, descend=args.descend)
    resource.set_request(args.url)

    formatter = find_formatter(args.output_format, "text", args.descend)(
        config,
        resource,
        output,
        {"tty_out": sys.stdout.isatty(), "descend": args.descend},
    )

    formatter.bind_resource(resource)

    @thor.events.on(formatter)
    def formatter_done() -> None:
        thor.stop()

    resource.check()
    thor.run()


def output(out: str) -> None:
    sys.stdout.write(out)


if __name__ == "__main__":
    main()
