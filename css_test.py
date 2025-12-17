import sys
from unittest.mock import MagicMock
try:
    from redbot.resource.link_parse import CSSLinkParser
except ImportError:
    # Set path if needed, but running from root should work if installed or in pythonpath
    import os
    sys.path.append(os.getcwd())
    from redbot.resource.link_parse import CSSLinkParser

# Mock dependencies
class MockMessage:
    def __init__(self):
        self.headers = MagicMock()
        self.headers.parsed = {"content-type": ["text/css"]}
        self.character_encoding = "utf-8"
        self.base_uri = "http://example.com/style.css"

def link_proc(base, link, tag, title):
    print(f"Found link: {link} (tag: {tag})")

msg = MockMessage()
parser = CSSLinkParser(msg, [link_proc])

css_content = """
@import "imported.css";
@import url('imported2.css');
body {
    background-image: url('bg.png');
}
"""


print("Feeding CSS content...")
parser.feed(css_content)

# Inject debugging
import tinycss2
rules = tinycss2.parse_stylesheet(css_content, skip_comments=True, skip_whitespace=True)

def print_structure(items, indent=0):
    for item in items:
        print("  " * indent + str(type(item)) + ": " + str(item))
        if hasattr(item, 'prelude'):
            print("  " * indent + "  Prelude:")
            print_structure(item.prelude, indent + 2)
        if hasattr(item, 'content') and item.content:
            print("  " * indent + "  Content:")
            print_structure(item.content, indent + 2)
        if hasattr(item, 'arguments'):
            print("  " * indent + "  Arguments:")
            print_structure(item.arguments, indent + 2)

print("--- Parsed Structure ---")
print_structure(rules)
print("------------------------")

print("Closing parser...")
parser.close()
print("Done.")
