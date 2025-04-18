# REDbot

REDbot is lint for HTTP resources.

It checks HTTP resources for feature support and common protocol problems at the HTTP semantic and caching layers. You can use the public instance on <https://redbot.org/>, or you can install it locally.

[![Test](https://github.com/mnot/redbot/actions/workflows/test.yml/badge.svg)](https://github.com/mnot/redbot/actions/workflows/test.yml)


## Contributing to REDbot

Your ideas, questions and other contributions are most welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md) for details.


## Setting Up Your Own REDbot

### Installation

REDbot requires a current version of [Python](https://python.org/).

The recommended method for installing REDbot is using `pipx`. To install the latest release, do:

> pipx install redbot

Or, to use the most development version of REDbot, run:

> pipx install git+https://github.com/mnot/redbot.git

Both of these methods will install the following programs into your [pipx binary folder](https://pypa.github.io/pipx/installation/):

* `redbot` - the command-line interface
* `redbot_daemon` - Web interface as a standalone daemon


### Running REDbot as a systemd Service

REDbot can run as a standalone service, managed by [systemd](https://freedesktop.org/wiki/Software/systemd/). This offers a degree of sandboxing and resource management, as well as process monitoring (including a watchdog function).

To do this, install REDbot on your system with the `systemd` option. For example:

> pipx install redbot[systemd]

The copy `extra/redbot.service` into the appropriate directory (on most systems, `/etc/systemd/system/`.)

Modify the file appropriately; this is only a sample. Then, as root:

~~~ bash
> systemctl reload-daemon
> systemctl enable redbot
> systemctl start redbot
~~~

By default, REDbot will listen on localhost port 8000. This can be adjusted in `config.txt`. Running REDbot behind a reverse proxy is recommended, if it is to be exposed to the Internet.

If you want to allow people to save test results, create the directory referenced by the 'save_dir' configuration variable, and make sure that it's writable to the REDbot process.


### Running REDbot in a Container

[OCI](https://opencontainers.org)-compliant containers are [available on Github](https://github.com/mnot/redbot/pkgs/container/redbot), and it's easy to run REDbot one using a tool like [Docker](https://www.docker.com) or [Podman](https://podman.io). For example:

> docker run --rm -p 8000:8000 ghcr.io/mnot/redbot

or

> podman run --rm -p 8000:8000 ghcr.io/mnot/redbot


## Credits

Icons by [Font Awesome](https://fontawesome.com/). REDbot includes code from [tippy.js](https://atomiks.github.io/tippyjs/) and [prettify.js](https://github.com/google/code-prettify).

