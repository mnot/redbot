"""
http_client.py - asynchronous HTTP client library.

Copyright (c) 2008-2009 Mark Nottingham

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
"""

import sys
import re
import errno
from urlparse import urlsplit, urlunsplit

import push_tcp

LWS = re.compile("\r?\n[ \t]+", re.M)
HDR_END = re.compile(r"\r?\n\r?\n", re.M)

# conn_modes
CLOSE = 0
COUNTED = 1
CHUNKED = 2

# states
WAITING = 0
HEADERS_DONE = 1
BODY_DONE = 2

# TODO: make object reusable for pipelining?
# TODO: expect/continue
# TODO: proxy support
# TODO: review HTTP requirements

class HttpClient:
    safe_methods = ['GET', 'HEAD']
    retry_limit = 2

    def __init__(self, res_start_cb, res_body_write_cb, res_body_done_cb, timeout=None):
        self.res_start_cb = res_start_cb
        self.res_body_write_cb = res_body_write_cb
        self.res_body_done_cb = res_body_done_cb
        self.method = ""
        self.uri = ""
        self.req_headers = []
        self.tcp_conn = None
        self._conn_mode = None
        self._conn_reusable = False
        self._input_buffer = ""
        self._req_state = WAITING
        self._req_body_sent = 0
        self._res_state = WAITING
        self._res_body_left = 0
        self._paused = False
        self._retries = 0
        self._timeout_event = None
        
    def start_request(self, method, uri, req_headers={}):
        self.method = method
        self.uri = uri
        self.req_headers = req_headers
        (scheme, authority, path, query, fragment) = urlsplit(self.uri)
        assert scheme.lower() == 'http', "Only HTTP URLs are supported"
        if ":" in authority:
            host, port = authority.rsplit(":", 1)
            assert port.isdigit(), "Non-integer port"
            port = int(port)
        else:
            host, port = authority, 80
        self.req_headers.append(("Host", authority)) # FIXME: make sure it's the only one
        self.req_headers.append(("Connection", "keep-alive"))
        self.uri = urlunsplit(('', '', path, query, ''))
        pool.attach(host, port, self.handle_connect, self.handle_connect_error)
        return self.req_body_write, self.req_body_done

    def handle_connect(self, tcp_conn):
        self.tcp_conn = tcp_conn
        hdr_block = ["%s %s HTTP/1.1" % (self.method, self.uri)]
        [hdr_block.append("%s: %s" % (k,v)) for k, v in self.req_headers]
        hdr_block.append("")
        hdr_block.append("")
        self.tcp_conn.write("\r\n".join(hdr_block))
        self._req_state = HEADERS_DONE
        return self.handle_input, self.conn_closed, self.pause_request

    def handle_connect_error(self, host, port, err):
        import os
        self._http_error("504", "Gateway Timeout", os.strerror(err)) 

    def req_body_write(self, data):
        assert self._req_state == HEADERS_DONE, "Can't send request body without headers."
        assert self.req_headers.has_key('content-length'), "Request bodies require content-length"
        #TODO: deal with pausing
        self._req_body_sent += len(data)
        self.tcp_conn.write(data)
        assert self._req_body_sent <= int(self.req_headers['content-length'][0]), \
            "Too many request body bytes sent"
        
    def req_body_done(self, data):
        self._req_state = BODY_DONE

    def handle_input(self, instr):
        if self._input_buffer:
            instr = self._input_buffer + instr # TODO: perf
            self._input_buffer = ""
        if self._res_state == WAITING:
            if re.search(HDR_END, instr): # found one
                self._res_state = HEADERS_DONE
                rest = self._parse_response(instr)
                self.handle_input(rest)
            else: # partial headers; store it and wait for more
                self._input_buffer = instr
        else:
            if self._conn_mode == CLOSE:
                self.res_body_write_cb(instr)
            elif self._conn_mode == CHUNKED:
                if self._res_body_left > 0:
                    if self._res_body_left < len(instr): # got more than the chunk
                        this_chunk = self._res_body_left
                        self.res_body_write_cb(instr[:this_chunk])
                        self._res_body_left = -1
                        return self.handle_input(instr[this_chunk+2:]) # +2 consumes the CRLF
                    elif self._res_body_left == len(instr): # got the whole chunk exactly
                        self.res_body_write_cb(instr)
                        self._res_body_left = -1
                    else: # got partial chunk
                        self.res_body_write_cb(instr)
                        self._res_body_left -= len(instr)
                elif self._res_body_left == 0: # done
                    self.res_body_done(True) # TODO: trailers, consume last CRLF
                else: # new chunk
                    try:
                        # they really need to use CRLF
                        chunk_size, instr = instr.split("\r\n", 1) 
                    except ValueError:
                        # got a CRLF without anything behind it.. wait.
                        self._input_buffer += instr
                        return
                    if chunk_size.strip() == "": # ignore bare lines
                        return self.handle_input(instr)
                    if ";" in chunk_size: # ignore chunk extensions
                        chunk_size = chunk_size.split(";", 1)[0]
                    self._res_body_left = int(chunk_size, 16)
                    self.handle_input(instr)
            elif self._conn_mode == COUNTED:
                assert self._res_body_left >= 0, "response bytecounting problem! (%s)" % self._res_body_left
                # process response body
                if self._res_body_left <= len(instr): # got it all (and more?)
                    self.res_body_write_cb(instr[:self._res_body_left])
                    self.res_body_done(True)
                    # TODO: will we ever get anything on instr[self._res_body_left:]?
                else: # got some of it
                    self.res_body_write_cb(instr)
                    self._res_body_left -= len(instr)
            else:
                raise Exception, "Unknown conn_mode"

    def conn_closed(self):
        if self._input_buffer:
            self.handle_input("")
            if self._res_state == BODY_DONE:
                return # we've seen the whole body now.
        if self._conn_mode == CLOSE:
            self.res_body_done(True)
        else:
            if self.method in self.safe_methods and self._retries < self.retry_limit:
                # FIXME: this is probably dangerous past WAITING. Clean up state before we retry.
                self._retries += 1
                pool.attach(self.tcp_conn.host, self.tcp_conn.port, 
                    self.handle_connect, self.handle_connect_error)                
            else:
                self._http_error("504", "Gateway Timeout", "connection closed") 

    def res_body_done(self, complete):
        self._res_state = BODY_DONE
        if self.tcp_conn and self.tcp_conn.tcp_connected:                
            def unexpected_read(data):
                if data:
                    self._conn_mode = CLOSE
                    self.res_body_write_cb(data)
            self.tcp_conn.read_cb = unexpected_read
            def idle_close():
                pass
            self.tcp_conn.close_cb = idle_close
            if self._conn_reusable:
                pool.release(self.tcp_conn)
            else:
                del self.tcp_conn
        self.res_body_done_cb(complete)

    def pause_request(self, paused):
        self._paused = paused

    def _parse_response(self, instr):
        top, rest = re.split(HDR_END, instr, 1)
        res_hdr_lines = LWS.sub(" ", top).splitlines()
        res_line = res_hdr_lines.pop(0)
        try: 
            res_version, status_txt = res_line.split(None, 1)
            res_version = float(res_version.rsplit('/', 1)[1])
        except (ValueError, IndexError), why:
            return self._http_error("502", "Bad Gateway", why)
        try:
            res_code, res_phrase = status_txt.split(None, 1)
        except ValueError:
            res_code = status_txt
            res_phrase = ""
        res_headers = []
        connection_tokens = []
        transfer_codes = []
        content_length = None
        for line in res_hdr_lines:
            try:
                fn, fv = line.split(":", 1)
                fn = fn.strip()
                res_headers.append((fn, fv.strip()))
            except ValueError, why:
                return self._http_error("502", "Bad Gateway", why)
            f_name = fn.lower()
            if f_name == "connection":
                connection_tokens += [v.strip().lower() for v in fv.split(',')]
            elif f_name == "transfer-encoding":
                transfer_codes += [v.strip().lower() for v in fv.split(',')]
            elif f_name == "content-length":
                try:
                    content_length = int(fv)
                except ValueError, why:
                    return self._http_error("502" "Bad Gateway", why) 

        if self.method == "HEAD" or res_code in ["304"]: # responses that have no body.
            self._conn_mode = COUNTED
            self._res_body_left = 0
        elif res_version > 1.0: # HTTP/1.1
            if len(transfer_codes) > 0:
                if 'chunked' in transfer_codes:
                    self._conn_mode = CHUNKED
                    self._res_body_left = -1 # flag that we don't know
                else:
                    self._conn_mode = CLOSE
            elif content_length != None:
                self._conn_mode = COUNTED
                self._res_body_left = content_length
            elif 'close' in connection_tokens:
                self._conn_mode = CLOSE
            else: # assume 0 length body
                self._conn_mode = COUNTED
                self._res_body_left = 0
        else: # HTTP/1.0
            if content_length != None and 'keep-alive' in connection_tokens:
                self._conn_mode = COUNTED
                if self._res_body_left == None:
                    self._res_body_left = 0
            else:
                self._conn_mode = CLOSE
        if 'close' not in connection_tokens:
            if (res_version == 1.0 and 'keep-alive' in connection_tokens) or \
                res_version > 1.0:
                self._conn_reusable = True
        self.res_start_cb(res_version, res_code, res_phrase, res_headers)
        return rest

    def _http_error(self, status_code, status_phrase, body=""):
        self._conn_mode = CLOSE
        self.res_start_cb("1.1", status_code, status_phrase, [])
        self.res_body_write_cb(str(body))
        self.res_body_done(False)
        if hasattr(self, 'tcp_conn') and self.tcp_conn and self.tcp_conn.tcp_connected:
            self.tcp_conn.close()
        return ""



class HttpClientConnectionPool:
    connect_timeout = 3
    _conns = {} # TODO: clean up old conns

    def attach(self, host, port, handle_connect, handle_connect_error):
        while True:
            try:
                idle_conn = self._conns[(host, port)].pop()
            except (IndexError, KeyError):
                push_tcp.Client(host, port, handle_connect, handle_connect_error, self.connect_timeout)
                break        
            if idle_conn.tcp_connected:
                idle_conn.read_cb, idle_conn.close_cb, idle_conn.pause_cb = handle_connect(idle_conn)
                break
        
    def release(self, tcp_conn):
        if tcp_conn.tcp_connected:
            if not self._conns.has_key((tcp_conn.host, tcp_conn.port)):
                self._conns[(tcp_conn.host, tcp_conn.port)] = [tcp_conn]
            else:
                self._conns[(tcp_conn.host, tcp_conn.port)].append(tcp_conn)

# create a singleton pool.
pool = HttpClientConnectionPool()

run = push_tcp.run
stop = push_tcp.stop
            
if __name__ == "__main__":
    request_uri = sys.argv[1]
    def printer(version, status, phrase, headers):
        print version, status, phrase
        print repr(headers)
    def done(self, complete):
        stop()
    c = HttpClient(printer, sys.stdout.write, done)
    req_body_write, req_body_done = c.start_request("GET", request_uri)
    run()
