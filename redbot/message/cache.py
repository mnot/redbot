"""
Cacheability checking function.
"""

# pylint: disable=too-many-branches,too-many-statements

from redbot.formatter import relative_time, f_num
from redbot.message import HttpRequest, HttpResponse
from redbot.speak import Note, categories, levels

### configuration
CACHEABLE_METHODS = ["GET"]
HEURISTIC_CACHEABLE_STATUS = ["200", "203", "206", "300", "301", "410"]
MAX_CLOCK_SKEW = 5  # seconds


def check_caching(response: HttpResponse, request: HttpRequest = None) -> None:
    "Examine HTTP caching characteristics."

    # get header values
    lm_hdr = response.parsed_headers.get("last-modified", None)
    date_hdr = response.parsed_headers.get("date", None)
    expires_hdr = response.parsed_headers.get("expires", None)
    etag_hdr = response.parsed_headers.get("etag", None)
    age_hdr = response.parsed_headers.get("age", None)
    cc_set = response.parsed_headers.get("cache-control", [])
    cc_list = [k for (k, v) in cc_set]
    cc_dict = dict(cc_set)
    cc_keys = list(cc_dict.keys())

    # Last-Modified
    if lm_hdr:
        serv_date = date_hdr or response.start_time
        if lm_hdr > serv_date:
            response.add_note("header-last-modified", LM_FUTURE)
        else:
            response.add_note(
                "header-last-modified",
                LM_PRESENT,
                last_modified_string=relative_time(lm_hdr, serv_date),
            )

    # known Cache-Control directives that don't allow duplicates
    known_cc = [
        "max-age",
        "no-store",
        "s-maxage",
        "public",
        "private",
        "pre-check",
        "post-check",
        "stale-while-revalidate",
        "stale-if-error",
    ]

    # check for miscapitalised directives /
    # assure there aren't any dup directives with different values
    for cc in cc_keys:
        if cc.lower() in known_cc and cc != cc.lower():
            response.add_note(
                "header-cache-control", CC_MISCAP, cc_lower=cc.lower(), cc=cc
            )
        if cc in known_cc and cc_list.count(cc) > 1:
            response.add_note("header-cache-control", CC_DUP, cc=cc)

    # Who can store this?
    if request and request.method not in CACHEABLE_METHODS:
        response.store_shared = response.store_private = False
        request.add_note("method", METHOD_UNCACHEABLE, method=request.method)
        return  # bail; nothing else to see here
    if "no-store" in cc_keys:
        response.store_shared = response.store_private = False
        response.add_note("header-cache-control", NO_STORE)
        return  # bail; nothing else to see here
    if "private" in cc_keys:
        response.store_shared = False
        response.store_private = True
        response.add_note("header-cache-control", PRIVATE_CC)
    elif (
        request
        and "authorization" in [k.lower() for k, v in request.headers]
        and "public" not in cc_keys
    ):
        response.store_shared = False
        response.store_private = True
        response.add_note("header-cache-control", PRIVATE_AUTH)
    else:
        response.store_shared = response.store_private = True
        response.add_note("header-cache-control", STORABLE)

    # no-cache?
    if "no-cache" in cc_keys:
        if lm_hdr is None and etag_hdr is None:
            response.add_note("header-cache-control", NO_CACHE_NO_VALIDATOR)
        else:
            response.add_note("header-cache-control", NO_CACHE)
        return

    # pre-check / post-check
    if "pre-check" in cc_keys or "post-check" in cc_keys:
        if "pre-check" not in cc_keys or "post-check" not in cc_keys:
            response.add_note("header-cache-control", CHECK_SINGLE)
        else:
            pre_check = post_check = None
            try:
                pre_check = int(cc_dict["pre-check"])
                post_check = int(cc_dict["post-check"])
            except ValueError:
                response.add_note("header-cache-control", CHECK_NOT_INTEGER)
            if pre_check is not None and post_check is not None:
                if pre_check == 0 and post_check == 0:
                    response.add_note("header-cache-control", CHECK_ALL_ZERO)
                elif post_check > pre_check:
                    response.add_note("header-cache-control", CHECK_POST_BIGGER)
                    post_check = pre_check
                elif post_check == 0:
                    response.add_note("header-cache-control", CHECK_POST_ZERO)
                else:
                    response.add_note(
                        "header-cache-control",
                        CHECK_POST_PRE,
                        pre_check=pre_check,
                        post_check=post_check,
                    )

    # vary?
    vary = response.parsed_headers.get("vary", set())
    if "*" in vary:
        response.add_note("header-vary", VARY_ASTERISK)
        return  # bail; nothing else to see here
    if len(vary) > 3:
        response.add_note("header-vary", VARY_COMPLEX, vary_count=f_num(len(vary)))
    else:
        if "user-agent" in vary:
            response.add_note("header-vary", VARY_USER_AGENT)
        if "host" in vary:
            response.add_note("header-vary", VARY_HOST)

    # calculate age
    response.age = age_hdr or 0
    age_str = relative_time(response.age, 0, 0)
    if date_hdr and date_hdr > 0:
        apparent_age = max(0, int(response.start_time - date_hdr))
    else:
        apparent_age = 0
    current_age = max(apparent_age, response.age)
    current_age_str = relative_time(current_age, 0, 0)
    if response.age >= 1:
        response.add_note("header-age header-date", CURRENT_AGE, age=age_str)

    # Check for clock skew and dateless origin server.
    if not date_hdr:
        response.add_note("", DATE_CLOCKLESS)
        if expires_hdr or lm_hdr:
            response.add_note(
                "header-expires header-last-modified", DATE_CLOCKLESS_BAD_HDR
            )
    else:
        skew = date_hdr - response.start_time + (response.age)
        if response.age > MAX_CLOCK_SKEW > (current_age - skew):
            response.add_note("header-date header-age", AGE_PENALTY)
        elif abs(skew) > MAX_CLOCK_SKEW:
            response.add_note(
                "header-date",
                DATE_INCORRECT,
                clock_skew_string=relative_time(skew, 0, 2),
            )
        else:
            response.add_note("header-date", DATE_CORRECT)

    # calculate freshness
    freshness_lifetime = 0
    has_explicit_freshness = False
    has_cc_freshness = False
    freshness_hdrs = ["header-date"]
    if "s-maxage" in cc_keys:
        freshness_lifetime = cc_dict["s-maxage"]
        freshness_hdrs.append("header-cache-control")
        has_explicit_freshness = True
        has_cc_freshness = True
    elif "max-age" in cc_keys:
        freshness_lifetime = cc_dict["max-age"]
        freshness_hdrs.append("header-cache-control")
        has_explicit_freshness = True
        has_cc_freshness = True
    elif "expires" in response.parsed_headers:
        # An invalid Expires header means it's automatically stale
        has_explicit_freshness = True
        freshness_hdrs.append("header-expires")
        freshness_lifetime = (expires_hdr or 0) - (date_hdr or int(response.start_time))

    freshness_left = freshness_lifetime - current_age
    freshness_left_str = relative_time(abs(int(freshness_left)), 0, 0)
    freshness_lifetime_str = relative_time(int(freshness_lifetime), 0, 0)

    response.freshness_lifetime = freshness_lifetime
    fresh = freshness_left > 0
    if has_explicit_freshness:
        if fresh:
            response.add_note(
                " ".join(freshness_hdrs),
                FRESHNESS_FRESH,
                freshness_lifetime=freshness_lifetime_str,
                freshness_left=freshness_left_str,
                current_age=current_age_str,
            )
        elif has_cc_freshness and response.age > freshness_lifetime:
            response.add_note(
                " ".join(freshness_hdrs),
                FRESHNESS_STALE_CACHE,
                freshness_lifetime=freshness_lifetime_str,
                freshness_left=freshness_left_str,
                current_age=current_age_str,
            )
        else:
            response.add_note(
                " ".join(freshness_hdrs),
                FRESHNESS_STALE_ALREADY,
                freshness_lifetime=freshness_lifetime_str,
                freshness_left=freshness_left_str,
                current_age=current_age_str,
            )

    # can heuristic freshness be used?
    elif response.status_code in HEURISTIC_CACHEABLE_STATUS:
        response.add_note("header-last-modified", FRESHNESS_HEURISTIC)
    else:
        response.add_note("", FRESHNESS_NONE)

    # can stale responses be served?
    if "must-revalidate" in cc_keys:
        if fresh:
            response.add_note("header-cache-control", FRESH_MUST_REVALIDATE)
        elif has_explicit_freshness:
            response.add_note("header-cache-control", STALE_MUST_REVALIDATE)
    elif "proxy-revalidate" in cc_keys or "s-maxage" in cc_keys:
        if fresh:
            response.add_note("header-cache-control", FRESH_PROXY_REVALIDATE)
        elif has_explicit_freshness:
            response.add_note("header-cache-control", STALE_PROXY_REVALIDATE)
    else:
        if fresh:
            response.add_note("header-cache-control", FRESH_SERVABLE)
        elif has_explicit_freshness:
            response.add_note("header-cache-control", STALE_SERVABLE)

    # public?
    if "public" in cc_keys:
        response.add_note("header-cache-control", PUBLIC)


class LM_FUTURE(Note):
    category = categories.CACHING
    level = levels.BAD
    summary = "The Last-Modified time is in the future."
    text = """\
The `Last-Modified` header indicates the last point in time that the resource has changed.
%(response)s's `Last-Modified` time is in the future, which doesn't have any defined meaning in
HTTP."""


class LM_PRESENT(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "The resource last changed %(last_modified_string)s."
    text = """\
The `Last-Modified` header indicates the last point in time that the resource has changed. It is
used in HTTP for validating cached responses, and for calculating heuristic freshness in caches.

This resource last changed %(last_modified_string)s."""


class METHOD_UNCACHEABLE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "Responses to the %(method)s method can't be stored by caches."
    text = """\
"""


class CC_MISCAP(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = "The %(cc)s Cache-Control directive appears to have incorrect \
capitalisation."
    text = """\
Cache-Control directive names are case-sensitive, and will not be recognised by most
implementations if the capitalisation is wrong.

Did you mean to use %(cc_lower)s instead of %(cc)s?"""


class CC_DUP(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = "The %(cc)s Cache-Control directive appears more than once."
    text = """\
The %(cc)s Cache-Control directive is only defined to appear once; it is used more than once here,
so implementations may use different instances (e.g., the first, or the last), making their
behaviour unpredictable."""


class NO_STORE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "%(response)s can't be stored by a cache."
    text = """\
The `Cache-Control: no-store` directive indicates that this response can't be stored by a cache."""


class PRIVATE_CC(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "%(response)s only allows a private cache to store it."
    text = """\
The `Cache-Control: private` directive indicates that the response can only be stored by caches
that are specific to a single user; for example, a browser cache. Shared caches, such as those in
proxies, cannot store it."""


class PRIVATE_AUTH(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "%(response)s only allows a private cache to store it."
    text = """\
Because the request was authenticated and this response doesn't contain a `Cache-Control: public`
directive, this response can only be stored by caches that are specific to a single user; for
example, a browser cache. Shared caches, such as those in proxies, cannot store it."""


class STORABLE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = """\
%(response)s allows all caches to store it."""
    text = """\
A cache can store this response; it may or may not be able to use it to satisfy a particular
request."""


class NO_CACHE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "%(response)s cannot be served from cache without validation."
    text = """\
The `Cache-Control: no-cache` directive means that while caches **can** store this
response, they cannot use it to satisfy a request unless it has been validated (either with an
`If-None-Match` or `If-Modified-Since` conditional) for that request."""


class NO_CACHE_NO_VALIDATOR(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "%(response)s cannot be served from cache without validation."
    text = """\
The `Cache-Control: no-cache` directive means that while caches **can** store this response, they
cannot use it to satisfy a request unless it has been validated (either with an `If-None-Match` or
`If-Modified-Since` conditional) for that request.

%(response)s doesn't have a `Last-Modified` or `ETag` header, so it effectively can't be used by a
cache."""


class VARY_ASTERISK(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = "Vary: * effectively makes this response uncacheable."
    text = """\
`Vary *` indicates that responses for this resource vary by some aspect that can't (or won't) be
described by the server. This makes this response effectively uncacheable."""


class VARY_USER_AGENT(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "Vary: User-Agent can cause cache inefficiency."
    text = """\
Sending `Vary: User-Agent` requires caches to store a separate copy of the response for every
`User-Agent` request header they see.

Since there are so many different `User-Agent`s, this can "bloat" caches with many copies of the
same thing, or cause them to give up on storing these responses at all.

Consider having different URIs for the various versions of your content instead; this will give
finer control over caching without sacrificing efficiency."""


class VARY_HOST(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = "Vary: Host is not necessary."
    text = """\
Some servers (e.g., [Apache](http://httpd.apache.org/) with
[mod_rewrite](http://httpd.apache.org/docs/2.4/mod/mod_rewrite.html)) will send `Host` in the
`Vary` header, in the belief that since it affects how the server selects what to send back, this
is necessary.

This is not the case; HTTP specifies that the URI is the basis of the cache key, and the URI
incorporates the `Host` header.

The presence of `Vary: Host` may make some caches not store an otherwise cacheable response (since
some cache implementations will not store anything that has a `Vary` header)."""


class VARY_COMPLEX(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = "This resource varies in %(vary_count)s ways."
    text = """\
The `Vary` mechanism allows a resource to describe the dimensions that its responses vary, or
change, over; each listed header is another dimension.

Varying by too many dimensions makes using this information impractical."""


class PUBLIC(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = "Cache-Control: public is rarely necessary."
    text = """\
The `Cache-Control: public` directive makes a response cacheable even when the request had an
`Authorization` header (i.e., HTTP authentication was in use).

Therefore, HTTP-authenticated (NOT cookie-authenticated) resources _may_ have use for `public` to
improve cacheability, if used judiciously.

However, other responses **do not need to contain `public`**; it does not make the
response "more cacheable", and only makes the response headers larger."""


class CURRENT_AGE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "%(response)s has been cached for %(age)s."
    text = """\
The `Age` header indicates the age of the response; i.e., how long it has been cached since it was
generated. HTTP takes this as well as any apparent clock skew into account in computing how old the
response already is."""


class FRESHNESS_FRESH(Note):
    category = categories.CACHING
    level = levels.GOOD
    summary = "%(response)s is fresh until %(freshness_left)s from now."
    text = """\
A response can be considered fresh when its age (here, %(current_age)s) is less than its freshness
lifetime (in this case, %(freshness_lifetime)s)."""


class FRESHNESS_STALE_CACHE(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = "%(response)s has been served stale by a cache."
    text = """\
An HTTP response is stale when its age (here, %(current_age)s) is equal to or exceeds its freshness
lifetime (in this case, %(freshness_lifetime)s).

HTTP allows caches to use stale responses to satisfy requests only under exceptional circumstances;
e.g., when they lose contact with the origin server. Either that has happened here, or the cache
has ignored the response's freshness directives."""


class FRESHNESS_STALE_ALREADY(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "%(response)s is already stale."
    text = """\
A cache considers a HTTP response stale when its age (here, %(current_age)s) is equal to or exceeds
its freshness lifetime (in this case, %(freshness_lifetime)s).

HTTP allows caches to use stale responses to satisfy requests only under exceptional circumstances;
e.g., when they lose contact with the origin server."""


class FRESHNESS_HEURISTIC(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = "%(response)s allows a cache to assign its own freshness lifetime."
    text = """\
When responses with certain status codes don't have explicit freshness information (like a `
Cache-Control: max-age` directive, or `Expires` header), caches are allowed to estimate how fresh
it is using a heuristic.

Usually, but not always, this is done using the `Last-Modified` header. For example, if your
response was last modified a week ago, a cache might decide to consider the response fresh for a
day.

Consider adding a `Cache-Control` header; otherwise, it may be cached for longer or shorter than
you'd like."""


class FRESHNESS_NONE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = (
        "%(response)s can only be served by a cache under exceptional circumstances."
    )
    text = """\
%(response)s doesn't have explicit freshness information (like a ` Cache-Control: max-age`
directive, or `Expires` header), and this status code doesn't allow caches to calculate their own.

Therefore, while caches may be allowed to store it, they can't use it, except in unusual
circumstances, such a when the origin server can't be contacted.

This behaviour can be prevented by using the `Cache-Control: must-revalidate` response directive.

Note that many caches will not store the response at all, because it is not generally useful to do
so."""


class FRESH_SERVABLE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "%(response)s may still be served by a cache once it becomes stale."
    text = """\
HTTP allows stale responses to be served under some circumstances; for example, if the origin
server can't be contacted, a stale response can be used (even if it doesn't have explicit freshness
information).

This behaviour can be prevented by using the `Cache-Control: must-revalidate` response directive."""


class STALE_SERVABLE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "%(response)s might be served by a cache, even though it is stale."
    text = """\
HTTP allows stale responses to be served under some circumstances; for example, if the origin
server can't be contacted, a stale response can be used (even if it doesn't have explicit freshness
information).

This behaviour can be prevented by using the `Cache-Control: must-revalidate` response directive."""


class FRESH_MUST_REVALIDATE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "%(response)s cannot be served by a cache once it becomes stale."
    text = """\
The `Cache-Control: must-revalidate` directive forbids caches from using stale responses to satisfy
requests.

For example, caches often use stale responses when they cannot connect to the origin server; when
this directive is present, they will return an error rather than a stale response."""


class STALE_MUST_REVALIDATE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "%(response)s cannot be served by a cache, because it is stale."
    text = """\
The `Cache-Control: must-revalidate` directive forbids caches from using stale responses to satisfy
requests.

For example, caches often use stale responses when they cannot connect to the origin server; when
this directive is present, they will return an error rather than a stale response."""


class FRESH_PROXY_REVALIDATE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "%(response)s cannot be served by a shared cache once it becomes stale."
    text = """\
The presence of the `Cache-Control: proxy-revalidate` and/or `s-maxage` directives forbids shared
caches (e.g., proxy caches) from using stale responses to satisfy requests.

For example, caches often use stale responses when they cannot connect to the origin server; when
this directive is present, they will return an error rather than a stale response.

These directives do not affect private caches; for example, those in browsers."""


class STALE_PROXY_REVALIDATE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "%(response)s cannot be served by a shared cache, because it is stale."
    text = """\
The presence of the `Cache-Control: proxy-revalidate` and/or `s-maxage` directives forbids shared
caches (e.g., proxy caches) from using stale responses to satisfy requests.

For example, caches often use stale responses when they cannot connect to the origin server; when
this directive is present, they will return an error rather than a stale response.

These directives do not affect private caches; for example, those in browsers."""


class CHECK_SINGLE(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = (
        "Only one of the pre-check and post-check Cache-Control directives is present."
    )
    text = """\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

%(response)s uses only one of these directives; as a result, Internet Explorer will ignore the
directive, since it requires both to be present.

See [this blog entry](http://bit.ly/rzT0um) for more information.
     """


class CHECK_NOT_INTEGER(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = "One of the pre-check/post-check Cache-Control directives has a non-integer value."
    text = """\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

Their values are required to be integers, but here at least one is not. As a result, Internet
Explorer will ignore the directive.

See [this blog entry](http://bit.ly/rzT0um) for more information."""


class CHECK_ALL_ZERO(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = "The pre-check and post-check Cache-Control directives are both '0'."
    text = """\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

%(response)s gives a value of "0" for both; as a result, Internet Explorer will ignore the
directive, since it requires both to be present.

In other words, setting these to zero has **no effect** (besides wasting bandwidth),
and may trigger bugs in some beta versions of IE.

See [this blog entry](http://bit.ly/rzT0um) for more information."""


class CHECK_POST_BIGGER(Note):
    category = categories.CACHING
    level = levels.WARN
    summary = (
        "The post-check Cache-control directive's value is larger than pre-check's."
    )
    text = """\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

%(response)s assigns a higher value to `post-check` than to `pre-check`; this means that Internet
Explorer will treat `post-check` as if its value is the same as `pre-check`'s.

See [this blog entry](http://bit.ly/rzT0um) for more information."""


class CHECK_POST_ZERO(Note):
    category = categories.CACHING
    level = levels.BAD
    summary = "The post-check Cache-control directive's value is '0'."
    text = """\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

%(response)s assigns a value of "0" to `post-check`, which means that Internet Explorer will reload
the content as soon as it enters the browser cache, effectively **doubling the load on the server**.

See [this blog entry](http://bit.ly/rzT0um) for more information."""


class CHECK_POST_PRE(Note):
    category = categories.CACHING
    level = levels.INFO
    summary = "%(response)s may be refreshed in the background by Internet Explorer."
    text = """\
Microsoft Internet Explorer implements two `Cache-Control` extensions, `pre-check` and
`post-check`, to give more control over how its cache stores responses.

Once it has been cached for more than %(post_check)s seconds, a new request will result in the
cached response being served while it is refreshed in the background. However, if it has been
cached for more than %(pre_check)s seconds, the browser will download a fresh response before
showing it to the user.

Note that these directives do not have any effect on other clients or caches.

See [this blog entry](http://bit.ly/rzT0um) for more information."""


class DATE_CORRECT(Note):
    category = categories.GENERAL
    level = levels.GOOD
    summary = "The server's clock is correct."
    text = """\
HTTP's caching model assumes reasonable synchronisation between clocks on the server and client;
using RED's local clock, the server's clock appears to be well-synchronised."""


class DATE_INCORRECT(Note):
    category = categories.GENERAL
    level = levels.BAD
    summary = "The server's clock is %(clock_skew_string)s."
    text = """\
Using RED's local clock, the server's clock does not appear to be well-synchronised.

HTTP's caching model assumes reasonable synchronisation between clocks on the server and client;
clock skew can cause responses that should be cacheable to be considered uncacheable (especially if
their freshness lifetime is short).

Ask your server administrator to synchronise the clock, e.g., using
[NTP](http://en.wikipedia.org/wiki/Network_Time_Protocol Network Time Protocol).

Apparent clock skew can also be caused by caching the response without adjusting the `Age` header;
e.g., in a reverse proxy or Content Delivery network. See [this
paper](https://www.usenix.org/legacy/events/usits01/full_papers/cohen/cohen_html/index.html) for more information. """  # pylint: disable=line-too-long


class AGE_PENALTY(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "It appears that the Date header has been changed by an intermediary."
    text = """\
It appears that this response has been cached by a reverse proxy or Content Delivery Network,
because the `Age` header is present, but the `Date` header is more recent than it indicates.

Generally, reverse proxies should either omit the `Age` header (if they have another means of
determining how fresh the response is), or leave the `Date` header alone (i.e., act as a normal
HTTP cache).

See [this paper](http://j.mp/S7lPL4) for more information."""


class DATE_CLOCKLESS(Note):
    category = categories.GENERAL
    level = levels.WARN
    summary = "%(response)s doesn't have a Date header."
    text = """\
Although HTTP allows a server not to send a `Date` header if it doesn't have a local clock, this
can make calculation of the response's age inexact."""


class DATE_CLOCKLESS_BAD_HDR(Note):
    category = categories.CACHING
    level = levels.BAD
    summary = "Responses without a Date aren't allowed to have Expires or Last-Modified values."
    text = """\
Because both the `Expires` and `Last-Modified` headers are date-based, it's necessary to know when
the message was generated for them to be useful; otherwise, clock drift, transit times between
nodes as well as caching could skew their application."""
