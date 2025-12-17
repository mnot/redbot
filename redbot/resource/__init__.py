"""
The Resource Expert Droid.

REDbot will examine a HTTP resource for problems and other interesting
characteristics, making a list of these observation notes available
for presentation to the user. It does so by potentially making a number
of requests to probe the resource's behaviour.

See webui.py for the Web front-end.
"""

from configparser import SectionProxy
import sys
from typing import Optional, List, Dict, Set, Tuple, Union
from urllib.parse import urljoin

import thor

from redbot.formatter import f_num
from redbot.resource import link_parse
from redbot.resource.fetch import RedFetcher
from redbot.resource.active_check import active_checks


class HttpResource(RedFetcher):
    """
    Given a URI (optionally with method, request headers and content), examine the URI for issues
    and notable conditions, making any necessary additional requests.

    After processing the response-specific attributes of RedFetcher will be populated, as well as
    its notes; see that class for details.

    if descend is true, the response will be parsed for links and HttpResources started for each
    link, enumerated in .linked.

    Emits "check_done" when everything has finished.
    """

    check_name = "default"
    check_id = "default"

    def __init__(self, config: SectionProxy, descend: bool = False) -> None:
        RedFetcher.__init__(self, config)
        self.descend: bool = descend
        self.check_done: bool = False
        self.partial_support: bool = False
        self.inm_support: bool = False
        self.ims_support: bool = False
        self.gzip_support: bool = False
        self.gzip_savings: int = 0
        self._task_map: Set[RedFetcher] = set([])
        self.subreqs = {ac.check_id: ac(config, self) for ac in active_checks}
        self.once("fetch_done", self.run_active_checks)

        self.links: Dict[str, Set[str]] = {}
        self.link_count: int = 0
        self.linked: List[Tuple[HttpResource, str]] = []  # linked HttpResources
        self._link_parser = link_parse.HTMLLinkParser(
            self.response, [self.process_link]
        )
        if self.descend or config.getboolean("content_links", False):
            self.response_content_processors.append(self._link_parser.feed_bytes)

    def run_active_checks(self) -> None:
        """
        Response is available; perform subordinate requests (e.g., conneg check).
        """
        if self.response.complete:
            for active_check in list(self.subreqs.values()):
                self.add_check(active_check)
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
        # pylint: disable=cell-var-from-loop
        for resource in resources:
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

        # pylint: enable=cell-var-from-loop

    def finish_check(self, resource: Optional[RedFetcher] = None) -> None:
        "A check is done. Was that the last one?"
        if resource:
            try:
                self._task_map.remove(resource)
            except KeyError:
                raise KeyError(  # pylint: disable=raise-missing-from
                    f"* Can't find {resource} in task map: {self._task_map}"
                )
        tasks_left = len(self._task_map)
        #        self.emit("debug", "%s checks remaining: %i" % (repr(self), tasks_left))
        if tasks_left == 0:
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
        if (
            self.descend
            and tag not in ["a"]
            and link not in self.links[tag]
            and self.link_count <= (self.config.getint("max_links", fallback=100))
        ):
            linked = HttpResource(self.config)
            linked.set_request(urljoin(base, link), headers=self.request.headers.text)
            self.linked.append((linked, tag))
            self.add_check(linked)
            linked.check()
        self.links[tag].add(link)
        if not self.response.base_uri:
            self.response.base_uri = base

    def stop(self) -> None:
        "Stop the resource and any sub-resources."
        for task in list(self._task_map):
            task.stop()
        RedFetcher.stop(self)
