"""
Round-trip form values from the Web UI's serializeForm() (src/js/red_script.js)
through the server's query string parsing.

The JS side is run under node when it's available; the test is skipped otherwise.
test_webui.py covers the same ground in a real browser.
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from redbot.webui import RedWebUi

SCRIPT = Path(__file__).parent.parent / "src" / "js" / "red_script.js"
NODE = shutil.which("node")

URI = "http://example.com/search?q=a+b&x=100%25&y=%41"
HDR = "Authorization:Bearer ab+cd/ef==#frag&more=100%25;x,y?z"


def extract_function(source: str, name: str) -> str:
    """Return the text of a top-level `function name (...) { ... }`, by brace matching."""
    start = re.search(rf"^function {name}\b", source, re.M)
    if not start:
        raise AssertionError(f"can't find function {name} in {SCRIPT}")
    depth = 0
    seen_brace = False
    for pos in range(start.start(), len(source)):
        if source[pos] == "{":
            depth += 1
            seen_brace = True
        elif source[pos] == "}":
            depth -= 1
        if seen_brace and depth == 0:
            return source[start.start() : pos + 1]
    raise AssertionError(f"unbalanced braces in function {name} in {SCRIPT}")


def serialize_form(fields: list[tuple[str, str]]) -> str:
    """Run the real serializeForm() from red_script.js over a fake form, under node."""
    # Assumes serializeForm is a top-level function with no braces inside strings or
    # regexes, and that `secrets` is a one-line top-level const.
    source = SCRIPT.read_text(encoding="utf-8")
    secrets = re.search(r"^const secrets = .*$", source, re.M)
    if not secrets:
        raise AssertionError(f"can't find `const secrets` in {SCRIPT}")
    function = extract_function(source, "serializeForm")
    elements = [
        {"nodeName": "INPUT", "type": "hidden" if n != "uri" else "url", "name": n, "value": v}
        for n, v in fields
    ]
    program = (
        f"{secrets.group(0)}\n{function}\n"
        f"console.log(serializeForm({{ elements: {json.dumps(elements)} }}))"
    )
    result = subprocess.run(
        [NODE or "node", "-e", program], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise AssertionError(f"node exited {result.returncode}:\n{result.stderr}")
    return result.stdout.strip()


def parse_on_server(query_string: str) -> dict[str, list[str]]:
    config = MagicMock()
    config.get.return_value = "utf-8"
    with patch.object(RedWebUi, "handlers", []):
        ui = RedWebUi(
            config, "POST", b"/check", query_string.encode("ascii"), [], b"", MagicMock(), "::1"
        )
    return ui.query_string


@unittest.skipIf(NODE is None, "node not available")
class TestFormRoundTrip(unittest.TestCase):
    def test_uri_and_header_survive(self) -> None:
        fields = [
            ("uri", URI),
            ("req_hdr", HDR),
            ("req_hdr", "Cookie:a=1; b=2+3#4"),
            ("captcha_token", "must not be sent"),
            ("descend", "1"),
        ]
        query = serialize_form(fields)
        parsed = parse_on_server(query)
        self.assertEqual(parsed["uri"], [URI])
        self.assertEqual(parsed["req_hdr"], [HDR, "Cookie:a=1; b=2+3#4"])
        self.assertEqual(parsed["descend"], ["1"])
        self.assertNotIn("captcha_token", parsed)

    def test_no_raw_delimiters(self) -> None:
        query = serialize_form([("uri", "http://example.com/?a=b+c#d&e")])
        self.assertNotIn("#", query)
        self.assertEqual(len(query.split("&")), 1)
        self.assertNotIn("+", query)


if __name__ == "__main__":
    unittest.main()
