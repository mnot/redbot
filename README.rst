===
RED
===

This is RED, the Resource Expert Droid.

RED checks HTTP resources for feature support and common HTTP problems. For
more information, see <http://redbot.org/about/>.

.. image:: https://secure.travis-ci.org/mnot/redbot.png?branch=master
   :alt: build status
   :target: http://travis-ci.org/mnot/redbot


Requirements
------------

RED needs:

1. Python 2.6 or greater; see <http://python.org/>
2. The Thor HTTP library; see <http://github.com/mnot/thor/>
3. To use RED on the Web, you'll need a Web server that implements the CGI interface; e.g., Apache <http://httpd.apache.org/>.


Installing RED
--------------

Unpack the RED tarball. There are a number of interesting files:

- bin/webui.py - the Web CGI script for running RED
- bin/redbot - the command-line interface
- redbot/ - RED's Python library files
- share/ - RED's CSS stylesheet and JavaScript libraries

To install from source (e.g., if you clone from github)::

  python setup.py install

installs RED's libraries as well as the command-line version as 'redbot'.

Setting up your Web Server
--------------------------

To run RED from the Web, place webui.py where you wish it to be served from by
the Web server. For example, with Apache you can put it in a directory and add
these configuration directives (e.g., in .htaccess, if enabled)::

  AddHandler cgi-script .py
  DirectoryIndex webui.py

If the directory is the root directory for your server "example.com",
this will configure RED to be at the URI "http://example.com/".

The contents of the share directory* also need to be made available on the
server; by default, they're in the 'static' subdirectory of the script's URI.
This can be changed using the 'html.static_root' configuration variable in
webui.py.

You should also create the directory referenced by the 'save_dir'
configuration variable in webui.py, and make sure that it's writable to the
Web server process. This is where RED stores state files, and you should
configure a cron job to regularly clean it. For example::

  0 * * * * find /var/state/redbot/ -mmin +360 -exec rm {} \;

If you don't want to allow users to store responses, set save_dir to 'None'.

* Note that you really only need script.js and style.js, but it doesn't hurt to have the rest.

Running under mod_python
------------------------

It's also possible to run RED as a mod_python handler. For example::

  AddHandler mod_python .py
  PythonHandler webui::mod_python_handler

If you use mod_python, make sure your server has enough memory for the
number of Apache children you configure; each child should use anywhere from
20M-35M of RAM.

Docker deployment
-----------------

You can also build the project through docker, clone from github then :

  docker build -t redbot .

Start the webserver

   docker run -p 8080:80 redbot

Use the command line

  docker run --entrypoint=/redbot/bin/redbot redbot <url>



Support, Reporting Issues and Contributing
------------------------------------------

See <http://REDbot.org/project> to give feedback, report issues, and
contribute to the project. You can also join the redbot-users mailing list
there.

Credits
-------

Icons by Momenticon <http://momenticon.com/>. REDbot also includes code
from jQuery <http://jquery.com/> and prettify.js
<http://code.google.com/p/google-code-prettify/>.

License
-------

Copyright (c) 2008-2013 Mark Nottingham

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
