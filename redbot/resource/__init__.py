"""
The Resource Expert Droid.

REDbot will examine a HTTP resource for problems and other interesting
characteristics, making a list of these observation notes available
for presentation to the user. It does so by potentially making a number
of requests to probe the resource's behaviour.

See webui.py for the Web front-end.
"""

import sys
from configparser import SectionProxy
from typing import Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urljoin

import thor
from thor.http.error import HttpError, UrlError
from thor.http.uri import parse_uri

from redbot.resource import link_parse
from redbot.resource.active_check import active_checks
from redbot.resource.fetch import RedFetcher
from redbot.type import StrHeaderListType

# Withheld from linked resources on other origins.
CREDENTIAL_HEADERS = {"authorization", "cookie", "proxy-authorization"}


def origin_of(uri: Optional[str]) -> Optional[Tuple[str, str, int]]:
    """
    The (scheme, host, port) the client will connect to for this (normalised) request URI, parsed
    the way the client does it; None if that can't be determined.
    """
    if not uri:
        return None
    try:
        scheme, host, port, _authority, _target = parse_uri(uri.encode("ascii"))
    except (UrlError, UnicodeError, ValueError):
        return None
    return (scheme, host.lower(), port)


def split_credentials(headers: StrHeaderListType) -> Tuple[StrHeaderListType, StrHeaderListType]:
    "Split request headers into (credentials, others)."
    credentials = [(n, v) for (n, v) in headers if n.strip().lower() in CREDENTIAL_HEADERS]
    others = [(n, v) for (n, v) in headers if n.strip().lower() not in CREDENTIAL_HEADERS]
    return credentials, others


class HttpResource(RedFetcher):
    """
    Given a URI (optionally with method, request headers and content), examine the URI for issues
    and notable conditions, making any necessary additional requests.

    After processing the response-specific attributes of RedFetcher will be populated, as well as
    its notes; see that class for details.

    if descend is true, the response will be parsed for links and HttpResources started for each
    link, enumerated in .linked. Linked resources don't run active checks.

    Emits "check_done" once, when everything has finished.
    """

    check_name = "default"
    check_id = "default"

    def __init__(
        self, config: SectionProxy, descend: bool = False, active_checks_enabled: bool = True
    ) -> None:
        RedFetcher.__init__(self, config)
        self.descend: bool = descend
        self.active_checks_enabled: bool = active_checks_enabled
        self.check_done: bool = False
        # None: not checked.
        unchecked: Optional[bool] = None if not active_checks_enabled else False
        self.partial_support: Optional[bool] = unchecked
        self.inm_support: Optional[bool] = unchecked
        self.ims_support: Optional[bool] = unchecked
        self.gzip_support: Optional[bool] = unchecked
        self.gzip_savings: int = 0
        self._task_map: Set[RedFetcher] = set([])
        self.subreqs = {ac.check_id: ac(config, self) for ac in active_checks}
        self.once("fetch_done", self.run_active_checks)

        self.links: Dict[str, Set[str]] = {}
        self.link_count: int = 0
        self.linked: List[Tuple[HttpResource, str]] = []  # linked HttpResources
        self._link_parser = link_parse.HTMLLinkParser(
            self.response, [self.process_link], err=self._link_error
        )
        if self.descend or config.getboolean("content_links", False):
            self.response.decoded.processors.append(self._link_parser.feed_bytes)

    def run_active_checks(self) -> None:
        """
        Response is available; perform subordinate requests (e.g., conneg check).
        """
        if self.response.complete and self.active_checks_enabled:
            # Register every check before starting any: one that finishes synchronously mustn't
            # empty the task map while others are still to be started.
            active = list(self.subreqs.values())
            self.add_check(*active)
            for active_check in active:
                active_check.check()
        else:
            self.finish_check()

    def descendable(self) -> bool:
        """
        Return whether this resource can be descended.
        """
        return (
            self.response.headers.parsed.get("content-type", [None])[0]
            in self._link_parser.link_parseable_types
        )

    def add_check(self, *resources: RedFetcher) -> None:
        "Remember a subordinate check on one or more HttpResource instance."
        for resource in resources:
            self._bind_events(resource)

    def _bind_events(self, resource: RedFetcher) -> None:
        "Bind events for a subordinate check."
        self._task_map.add(resource)

        @thor.events.on(resource)
        def status(message: str) -> None:
            self.emit("status", message)

        @thor.events.on(resource)
        def debug(message: str) -> None:
            self.emit("debug", message)

        @thor.events.on(resource)
        def check_done() -> None:
            self.finish_check(resource)

    def finish_check(self, resource: Optional[RedFetcher] = None) -> None:
        "A check is done. Was that the last one?"
        if resource:
            try:
                self._task_map.remove(resource)
            except KeyError:
                raise KeyError(f"* Can't find {resource} in task map: {self._task_map}") from None
        tasks_left = len(self._task_map)
        #        self.emit("debug", "%s checks remaining: %i" % (repr(self), tasks_left))
        # Links that fail immediately mustn't complete us while we're still reading the response.
        if tasks_left == 0 and self.fetch_done and not self.check_done:
            self.check_done = True
            self.emit("check_done")

    def show_task_map(self, watch: bool = False) -> Union[str, None]:
        """
        Show the task map for debugging.
        """
        if self._task_map and watch:
            sys.stderr.write(f"* {self} - {self._task_map}\n")
            thor.schedule(5, self.show_task_map)
            return None
        return repr(self._task_map)

    def process_link(self, base: str, link: str, tag: str, title: str) -> None:
        "Handle a link from content."
        self.link_count += 1
        if tag not in self.links:
            self.links[tag] = set()
        max_links = self.config.getint("max_links", fallback=100)
        if self.link_count > max_links:
            if not self.response.base_uri:
                self.response.base_uri = base
            return
        if self.descend and tag not in ["a"] and link not in self.links[tag]:
            linked = HttpResource(self.config, active_checks_enabled=False)
            credentials, other_headers = split_credentials(self.request.headers.text)
            uri: Optional[str]
            try:
                uri = urljoin(base, link)
            except ValueError:
                uri = None
            linked.set_request(uri if uri is not None else link, headers=other_headers)
            # Compare the normalised URIs, not the link text: normalisation can change the host.
            # Credentials stay off unless both origins are known and equal.
            linked_origin = origin_of(linked.request.uri)
            if credentials and linked_origin and linked_origin == origin_of(self.request.uri):
                linked.request.process_headers(
                    [(n.encode("utf-8"), v.encode("utf-8")) for (n, v) in credentials]
                )
            self.linked.append((linked, tag))
            self.add_check(linked)
            if uri is None:  # can't be resolved; list it as failed and carry on
                self._fail_link(linked, UrlError("link could not be resolved"))
            else:
                try:
                    linked.check()
                except Exception as why:  # pylint: disable=broad-except
                    self._fail_link(linked, HttpError(str(why)))
        self.links[tag].add(link)
        if not self.response.base_uri:
            self.response.base_uri = base

    def _fail_link(self, linked: "HttpResource", error: HttpError) -> None:
        "Record why a linked resource couldn't be checked, and complete it."
        linked.fetch_error = linked.fetch_error or error
        linked.stop()
        if linked in self._task_map:  # stop() didn't complete it
            self.finish_check(linked)
        try:  # after cleanup, so a failing listener can't undo it
            uri = (linked.request.uri or "")[:200]
            self.emit("debug", f"checking link {uri} failed: {error!r}")
        except Exception:  # pylint: disable=broad-except
            pass

    def _link_error(self, message: str) -> None:
        "Report a problem parsing or handling links."
        self.emit("debug", f"link parsing: {message}")

    def stop(self) -> None:
        "Stop the resource and any sub-resources."
        for task in list(self._task_map):
            task.stop()
        RedFetcher.stop(self)
