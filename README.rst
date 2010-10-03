===
RED
===

This is RED, the Resource Expert Droid.

RED checks HTTP resources for feature support and common HTTP problems. For
more information, see <http://redbot.org/about/>.

Requirements
------------

RED needs:

1. Python 2.5 or greater; see <http://python.org/>
2. The nbhttp library; see <http://github.com/mnot/nbhttp/>
3. The json library (included with Python 2.6 or greater); see
   <http://pypi.python.org/pypi/simplejson/>
3. Optionally, RED will take advantage of the pyevent extension, if installed.
   See PyEvent <http://code.google.com/p/pyevent/>.
4. To use RED on the Web, you'll need a Web server that implements the CGI
   interface; e.g., Apache <http://httpd.apache.org/>.

Installing RED
--------------

Unpack the RED tarball. There are a number of interesting files:

- bin/webui.py - the Web CGI script for running RED
- bin/redbot - the command-line interface
- lib/ - RED's Python library files
- share/ - RED's CSS stylesheet and JavaScript libraries

Running:: 

  python setup.py install
  
installs RED's library as well as the command-line version as 'redbot'. 

Setting up your Web Server
--------------------------

To run RED from the Web, place webui.py where you wish it to be served from by
the Web server. For example, with Apache you can put it in a directory and add
these configuration directives (e.g., in .htaccess, if enabled)::

  AddHandler cgi-script .py
  DirectoryIndex webui.py
  
If the directory is the root directory for your server "example.com", 
this will configure RED to be at the URI "http://example.com/".

The contents of the share directory also need to be made available on the
server; by default, they're in the 'static' subdirectory of the script's URI.
This can be changed using the 'static_root' configuration variable in
webui.py.

Support, Reporting Issues and Contributing
------------------------------------------

See <http://REDbot.org/project> to give feedback, report issues, and
contribute to the project. You can also join the redbot-users mailing list
there.

Credits
-------

Icons by Momenticon <http://momenticon.com/>.

License
-------

Copyright (c) 2008-2010 Mark Nottingham

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
