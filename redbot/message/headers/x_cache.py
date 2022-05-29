from redbot.message import headers


class x_cache(headers.HttpHeader):
    canonical_name = "X-Cache"
    description = """\
The `X-Cache` header is used by some caches to indicate whether or not the response was served from
cache; if it contains `HIT`, it was."""
    list_header = True
    deprecated = False
    valid_in_requests = False
    valid_in_responses = True
