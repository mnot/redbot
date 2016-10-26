#!/usr/bin/env python

"""
The Resource Expert Droid.

REDbot will examine a HTTP resource for problems and other interesting
characteristics, making a list of these observation notes available
for presentation to the user. It does so by potentially making a number
of requests to probe the resource's behaviour.

See webui.py for the Web front-end.
"""

from typing import Set, Tuple, Union
from urllib.parse import urljoin

import thor

from redbot.formatter import f_num
from redbot.message import link_parse
from redbot.resource.fetch import RedFetcher
from redbot.resource.active_check import active_checks



class HttpResource(RedFetcher):
    """
    Given a URI (optionally with method, request headers and body), examine the URI for issues and
    notable conditions, making any necessary additional requests.

    After processing the response-specific attributes of RedFetcher will be populated, as well as
    its notes; see that class for details.

    if descend is true, the response will be parsed for links and HttpResources started for each
    link, enumerated in .linked.

    Emits "check_done" when everything has finished.
    """
    check_name = "default"
    response_phrase = "This response"

    def __init__(self, descend: bool=False) -> None:
        RedFetcher.__init__(self)
        self.descend = descend       # type: bool
        self.check_done = False      # type: bool
        self.partial_support = None  # type: bool
        self.inm_support = None      # type: bool
        self.ims_support = None      # type: bool
        self.gzip_support = None     # type: bool
        self.gzip_savings = 0        # type: int
        self._task_map = set([None]) # type: Set[RedFetcher]   # None is the original request
        self.subreqs = {ac.check_name:ac(self) for ac in active_checks}  # type: ignore
        self.response.once("content_available", self.run_active_checks)
        def finish_check() -> None:
            self.finish_check(None)
        self.on("fetch_done", finish_check)
        self.links = {}              # type: Dict[str, Set[str]]
        self.link_count = 0          # type: int
        self.linked = []             # type: List[Tuple[HttpResource, str]]  # linked HttpResources
        self._link_parser = link_parse.HTMLLinkParser(self.response, [self.process_link])
        self.response.on("chunk", self._link_parser.feed)
#        self.show_task_map(True) # for debugging

    def run_active_checks(self) -> None:
        """
        Response is available; perform subordinate requests (e.g., conneg check).
        """
        if self.response.complete:
            for active_check in list(self.subreqs.values()):
                self.add_check(active_check)
                active_check.check()

    def add_check(self, *resources: RedFetcher) -> None:
        "Remember a subordinate check on one or more HttpResource instance."
        for resource in resources:
            self._task_map.add(resource)
            @thor.events.on(resource)
            def status(message: str) -> None:
                self.emit('status', message)
            @thor.events.on(resource)
            def check_done() -> None:
                self.finish_check(resource)

    def finish_check(self, resource: RedFetcher) -> None:
        "A check is done. Was that the last one?"
        try:
            self._task_map.remove(resource)
        except KeyError:
            raise KeyError("* Can't find %s in task map: %s" % (resource, self._task_map))
        tasks_left = len(self._task_map)
#        self.emit("status", u"Checks remaining: %i" % tasks_left)
        if tasks_left == 0:
            self.check_done = True
            self.emit('check_done')

    def show_task_map(self, watch: bool=False) -> Union[str, None]:
        """
        Show the task map for debugging.
        """
        import sys
        if self._task_map and watch:
            sys.stderr.write("* %s - %s\n" % (self, self._task_map))
            thor.schedule(5, self.show_task_map)
        else:
            return repr(self._task_map)

    def process_link(self, base: str, link: str, tag: str, title: str) -> None:
        "Handle a link from content."
        self.link_count += 1
        if tag not in self.links:
            self.links[tag] = set()
        if self.descend and tag not in ['a'] and link not in self.links[tag]:
            linked = HttpResource()
            linked.set_request(urljoin(base, link), req_hdrs=self.request.headers)
            self.linked.append((linked, tag))
            self.add_check(linked)
            linked.check()
        self.links[tag].add(link)
        if not self.response.base_uri:
            self.response.base_uri = base


if __name__ == "__main__":
    import sys
    RED = HttpResource()
    RED.set_request(sys.argv[1])
    @thor.events.on(RED)
    def status(msg: str) -> None:
        print(msg)
    @thor.events.on(RED)
    def check_done() -> None:
        print('check_done')
        thor.stop()
    RED.check()
    thor.run()
    print(RED.notes)
