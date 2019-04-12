# REDbot

REDbot is lint for HTTP.

It checks HTTP resources for feature support and common protocol problems. You can use the public
instance on <https://redbot.org/>, or you can install it locally and use it on the command line, or
even self-host your own Web checker.

[![Build Status](https://travis-ci.org/mnot/redbot.svg?branch=master)](https://travis-ci.org/mnot/redbot)


## Contributing to REDbot

Your ideas, questions and other contributions are most welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md) for details.


## Setting Up Your Own REDbot

### Requirements

REDbot needs:

1. [Python 3.6](https://python.org/) or greater
2. [thor](http://github.com/mnot/thor/)
3. [markdown](https://pythonhosted.org/Markdown/)
4. To use REDbot on the Web, you'll need a Web server that implements the CGI interface; e.g., [Apache](https://httpd.apache.org/)

Once you have Python, you can install the required libraries with:

> pip install thor markdown


### Installing RED

Unpack the REDbot tarball. The relevant files are:

- `bin/redbot_cgi.py` - the Web CGI script for running REDbot
- `bin/redbot_cli` - the command-line interface
- `redbot/` - REDbot's Python library files
- `redbot/assets/` - REDbot's CSS stylesheet and JavaScript library

To install from source (e.g., if you clone from github):

> python setup.py install

installs REDbot's libraries as well as the command-line version as `redbot_cli`.


### Setting up your Web Server

To run REDbot as a CGI script, `place redbot_cgi.py` where you wish it to be served from by the Web
server, and place config.txt in the same directory.

For example, with Apache you can put it in a directory and add these configuration directives
(e.g., in `.htaccess, if enabled):

```
  AddHandler cgi-script .py
  DirectoryIndex redbot_cgi.py
```

If the directory is the root directory for your server "example.com", this will configure REDbot to
be at the URI "http://example.com/".

You can also locate config.txt somewhere else, and indicate its path in an environment variable:

```
 SetEnv REDBOT_CONFIG /path/to/config.txt
```

The contents of the assets directory also need to be made available on the server; by default,
they're in the 'static' subdirectory of the script's URI. This can be changed using the
'static_root' configuration variable in config.txt.

You should also create the directory referenced by the 'save_dir' configuration variable, and make
sure that it's writable to the Web server process. This is where RED stores state files, and you
should configure a cron job to regularly clean it. For example:

> 0 * * * * find /var/state/redbot/ -mmin +360 -exec rm {} \;


### Running REDbot as a systemd Service

REDbot can run as a standalone service, managed by [systemd](https://freedesktop.org/wiki/Software/systemd/). This offers a degree of sandboxing and resource management, as well as process monitoring (including a watchdog function).

To do this, clone the repo to your system and copy `extra/redbot.service` into the appropriate directory (on most systems, `/etc/systemd/system/`.)

Modify the file appropriately; this is only a sample. In particular, you will need to adjust the first part of `BindReadOnlyPaths` to suit the location of the REDbot directory for you.

Then, as root:

> systemctl reload-daemon

> systemctl enable redbot

> systemctl start redbot

By default, REDbot will listen on localhost port 8000. This can be adjusted in `config.txt`. Running REDbot behind a reverse proxy is recommended, if it is to be exposed to the Internet.



### Running REDbot with Docker

If you wish to run REDbot using [Docker](https://www.docker.com), get a local copy of the repository, then:

> docker build -t redbot .

Start the webserver:

> docker run -p 8000:80 redbot

Or, just:

> make docker

to run REDbot on port 8000.


## Credits

Icons by Momenticon. REDbot includes code from [jQuery](https://jquery.com) and [prettify.js](https://github.com/google/code-prettify).

