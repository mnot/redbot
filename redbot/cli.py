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

    resource.check()
    thor.run()


def output(out: str) -> None:
    sys.stdout.write(out)


if __name__ == "__main__":
    main()
