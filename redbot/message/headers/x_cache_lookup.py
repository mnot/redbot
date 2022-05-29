from redbot.message import headers


class x_cache_lookup(headers.HttpHeader):
    canonical_name = "X-Cache-Lookup"
    description = """\
The `X-Cache-Lookup` header is used by some caches to show whether there was a response in cache
for this URL; if it contains `HIT`, it was in cache (but not necessarily used)."""
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
