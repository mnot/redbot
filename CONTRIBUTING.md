# Contributing to REDbot

Contributions - in the form of code, bugs, or ideas - are very welcome!

## Reporting bugs and suggesting enhancements

The [issues list](https://github.com/mnot/redbot/issues) is the best place to report
problems or suggest new features. Before you submit something, it would be great if you had a look
through the current issues to see if it's already there.


## Making code contributions

### Understanding REDbot

A quick overview of the repository contents:

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

If you plan to support a new HTTP header in REDbot (a common task), see the [guide for Header
Development](https://github.com/mnot/redbot/blob/master/redbot/message/headers/README.md).


### Coding conventions

We use [black](https://pypi.org/project/black/) for Python formatting, and [standard](https://standardjs.com) for JavaScript; both can be run with `make tidy`.

All Python functions and methods need to have type annotations. See `pyproject.toml` for specific pylint and mypy settings.


### Setting up a development environment

It should be possible to develop REDbot on any modern Unix-like environment, provided that recent releases of Python and NodeJS are installed.

Thanks to [Makefile.venv](https://github.com/sio/Makefile.venv), a Python virtual environment is set up and run each time you use `make`. As long as you use `make`, Python dependencies will be installed automatically. `make` will also install npm dependencies for a few development tools into a local `node_modules` directory.


#### Helpful Make targets

* `make shell` - start a shell in the Python virtual environment
* `make python` - start an interactive Python interpreter in the virtual environment
* `make lint` - run pylint with REDbot-specific configuration
* `make typecheck` - run mypy to check Python types
* `make tidy` - format Python and JavaScript source
* `make redbot/assets` - re-generate the JavaScript and CSS in the `assets/` directory
* `make server` - run a local standalong Web server on port 8000 for testing
* `make test` - run the tests


### Before you submit

The best way to submit changes to REDbot is through a pull request. A few things to keep in mind when you're doing so:

* Run `make tidy`.
* Check your code with `make lint` and address any issues found.
* Check your code with `make typecheck` and address any issues found.
* Every new header and every new `Note` should have a test covering it.

If you're not sure how to dig in, feel free to ask for help, or sketch out an idea in an issue
first.


### Intellectual property

By contributing code, bugs or enhancement requests to this project (whether that be through pull requests, the issues list, Twitter, e-mail or other means), you are licensing your contribution under the [project's terms](LICENSE.md).
