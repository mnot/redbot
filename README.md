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


## Web Bot Auth

REDbot can authenticate its outgoing requests using [Web Bot Auth](https://datatracker.ietf.org/doc/draft-meunier-web-bot-auth-architecture/), which signs requests with an Ed25519 key using [HTTP Message Signatures (RFC 9421)](https://www.rfc-editor.org/rfc/rfc9421). This lets origins verify that requests genuinely come from your REDbot instance. The implementation follows the IETF drafts and is not specific to any one verifier.

Requests are sent unsigned by default. REDbot only attaches a signature when the origin challenges for one -- that is, when it returns a `401`, `403`, or `429` response carrying an `Accept-Signature` header -- and then transparently retries the request signed. This avoids advertising the bot's identity to servers that don't ask for it.

### Generating a key

Create an Ed25519 private key in PEM form:

~~~ bash
> openssl genpkey -algorithm ed25519 -out web-bot-auth-key.pem
~~~

Keep this file private and readable by the REDbot process. The matching public key is published automatically (see below); you do not need to extract it yourself.

### Configuring

Set these in `config.txt` (for `redbot_daemon`):

~~~ ini
web_bot_auth_key = /path/to/web-bot-auth-key.pem
web_bot_auth_directory = https://your-redbot.example
~~~

`web_bot_auth_directory` is the HTTPS origin where your public key directory is hosted. When you run `redbot_daemon`, it serves that directory at `/.well-known/http-message-signatures-directory` (a JWKS, self-signed per the spec), so a verifier can fetch your public key. Make sure that path is reachable at the origin you configured.

`web_bot_auth_directory` is optional: if you omit it, REDbot uses the origin of `ui_uri`. Because `ui_uri` defaults to `https://redbot.org/`, **enabling signing requires `ui_uri` to be set to your instance's real public origin** — otherwise you would publish the wrong bot identity. Set `web_bot_auth_directory` explicitly if your key directory lives on a different origin than the UI.

For the command-line tool, pass the equivalent flags (there is no `ui_uri`, so the directory is required):

~~~ bash
> redbot --web-bot-auth-key web-bot-auth-key.pem --web-bot-auth-directory https://your-redbot.example https://example.com/
~~~

### Registering with a verifier

To be recognised by a specific verifier, register your directory URL with them according to their process.


## Credits

Icons by [Font Awesome](https://fontawesome.com/). REDbot includes code from [tippy.js](https://atomiks.github.io/tippyjs/) and [prettify.js](https://github.com/google/code-prettify).

