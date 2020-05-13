
# Contributing to REDbot

The following is a set of guidelines for contributing to REDbot. These are just guidelines, not
rules, use your best judgment and feel free to propose changes to this document in a pull request.


## Code of Conduct

This project adheres to the [Contributor Covenant code of
conduct](http://contributor-covenant.org/version/1/4/). By participating, you are expected to
uphold this code. Please report unacceptable behavior to [red@redbot.org](mailto:red@redbot.org).


## Intellectual Property

By contributing code, bugs or enhancement requests to this project (whether that be through pull requests, the issues list, Twitter, e-mail or other means), you are licensing your contribution under the [project's terms](LICENSE.md).


## Reporting Bugs and Suggesting Enhancements

The [issues list](https://github.com/mnot/redbot/issues) is the best place to report
problems or suggest new features. Before you submit something, it would be great if you had a look
through the current issues to see if it's already there.

You can also report problems or ask questions to our [twitter
account](https://twitter.com/redbotorg); if you don't hear an answer from us in a reasonable amount
of time, please try the issues list!

Finally, you can e-mail us at [red@redbot.org](mailto:red@redbot.org).


## Writing Code for REDbot

Code contributions are very welcome!

### Understanding REDbot

First, a quick overview of the repository contents.

* `bin/` has the command-line and Web (CGI and standalone daemon) executables that are the glue between the outside world and REDbot
* `redbot/` contains the redbot Python module:
  * `assets/` contains static assets for the Web UI
  * `formatter/` holds the different output formatters (e.g., HTML, plaintext, [HAR](http://www.softwareishard.com/blog/har-12-spec/)) for the check results
  * `message/` checks one message, either request or response (but currently, mostly responses)
    * `headers/` checks individual HTTP headers
  * `resource/` defines the actual checker for a given URL, as `HTTPResource` in `__init__.py`. Lower-level fetching of resources is handled in `fetch.py`.
    * `active_check/` doing a check on a resource might involve making additional requests, e.g., for ETag validation. Those checks are defined here
  * `syntax/` has a collection of [ABNF](https://tools.ietf.org/html/rfc5234) translated into regex, for checking syntax
  * `webui/` contains the engine for Web-based interaction with REDbot
* `src/` contains the source files for the JavaScript and CSS files
* `test/` guess what's here?

Generally, running a check involves instantiating a new `HTTPResource` object, which is a subclass
of `RedFetcher`. It's in charge of making all of the HTTP requests necessary to test that resource,
and feeds the results into `HttpMessage` objects that then checks its various aspects, especially
headers. If `descend` is true, the response will be parsed for links and `HTTPResource`s will be
created for each of them. When it's all done, the "root" `HTTPResource` will be fed to a
`Formatter` for presentation.

If you plan to support a new HTTP header in REDbot (a very common task), see the [guide for Header
Development](https://github.com/mnot/redbot/blob/master/redbot/message/headers/README.md).


### Coding Conventions

We use [black](https://pypi.org/project/black/) for Python formatting, and [standard](https://standardjs.com) for JavaScript; both can be run with `make tidy`.


### Helpful Make Targets

* `make lint` - run pylint with REDbot-specific configuration
* `make tidy` - format Python and JavaScript source
* `make redbot/assets` - re-generate the JavaScript and CSS in the `assets/` directory
* `make server` - run a local standalong Web server on port 8000 for testing
* `make test` - run the tests


### Before you Submit

The best way to submit changes to REDbot is through a pull request. A few things to keep in mind when you're doing so:

* Please follow [PEP8](https://www.python.org/dev/peps/pep-0008/); that means four spaces, not tabs :)
* That said, our convention for line length is **100 characters**.
* Check your code with [pylint](https://www.pylint.org). It doesn't need to be a perfect 10, but please make sure indentation and whitespace are OK and it doesn't complain about anything major.
* Every new header and every new `Note` should have a test covering it.

If you're not sure how to dig in, feel free to ask for help, or sketch out an idea in an issue
first.


