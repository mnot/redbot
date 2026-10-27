#!/usr/bin/env python

"""
CLI interface to REDbot
"""

import sys
from argparse import ArgumentParser
from configparser import ConfigParser

import thor

from redbot.formatter import available_formatters, find_formatter
from redbot.resource import HttpResource
from redbot.webbotauth import WebBotAuthError, load_signer

# The read timeout restarts whenever a byte arrives, so a slow server could keep us here for ever.
DEFAULT_TIMEOUT = 60.0


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
        help=(
            "output format; text_verbose adds an explanation of each note. "
            "With --assets, text and text_verbose list the linked assets as well"
        ),
    )
    parser.add_argument(
        "-t",
        "--timeout",
        action="store",
        dest="timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help=(
            "stop the check after this many seconds in all and show what was collected "
            f"(default {DEFAULT_TIMEOUT:g}; 0 for no limit)"
        ),
    )
    parser.add_argument(
        "--web-bot-auth-key",
        action="store",
        dest="web_bot_auth_key",
        help="path to an Ed25519 private key (PEM) for signing requests with Web Bot Auth",
    )
    parser.add_argument(
        "--web-bot-auth-directory",
        action="store",
        dest="web_bot_auth_directory",
        help="HTTPS origin hosting this bot's key directory (the Signature-Agent value)",
    )
    args = parser.parse_args()

    redbot_config = {"enable_local_access": "True"}
    if args.web_bot_auth_key:
        redbot_config["web_bot_auth_key"] = args.web_bot_auth_key
    if args.web_bot_auth_directory:
        redbot_config["web_bot_auth_directory"] = args.web_bot_auth_directory
    config_parser = ConfigParser()
    config_parser.read_dict({"redbot": redbot_config})
    config = config_parser["redbot"]

    try:
        load_signer(config)  # validate Web Bot Auth config up front
    except WebBotAuthError as why:
        sys.stderr.write(f"Web Bot Auth configuration error: {why}\n")
        sys.exit(1)

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

    def stop_checking() -> None:
        sys.stderr.write(
            f"redbot: stopped after {args.timeout:g} seconds; showing what was collected\n"
        )
        resource.stop()

    if args.timeout > 0:
        thor.schedule(args.timeout, stop_checking)
    resource.check()
    thor.run()


def output(out: str) -> None:
    sys.stdout.write(out)


if __name__ == "__main__":
    main()
