#!/usr/bin/env python3

import sys
import time
import gzip
import signal
import thor
import thor.http.server
from thor.loop import run, stop

class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    RESET = '\033[0m'

REQUEST_COUNT = 0
LOG_BUFFER = []

def colorize(text, color):
    # Check if we are in a TTY or if forced color output is desired
    if sys.stdout and sys.stdout.isatty():
        return f"{color}{text}{Colors.RESET}"
    return text

def test_handler(exchange):
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    
    method = exchange.method.decode('utf-8')
    uri = exchange.uri.decode('utf-8')
    req_hdrs = {k.decode('utf-8').lower(): v.decode('utf-8') for k, v in exchange.req_hdrs}

    resp_hdrs = {
        b"Cache-Control": b"max-age=3600",
        b"Connection": b"close"
    }

    status = b"200"
    phrase = b"OK"
    content = b""

    if uri == "/img.png":
        content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        resp_hdrs[b"Content-Type"] = b"image/png"
    elif method not in ["GET", "HEAD"]:
        status = b"501"
        phrase = b"Not Implemented"
    else:
        # Default content
        padding = b"<!-- padding -->\n" * 100
        content = b"<html><body><h1>Hello World</h1><img src='img.png'><p>Some text content.</p>" + padding + b"</body></html>"
        
        range_hdr = req_hdrs.get("range")
        ae_hdr = req_hdrs.get("accept-encoding", "")
        inm_hdr = req_hdrs.get("if-none-match")
        ims_hdr = req_hdrs.get("if-modified-since")

        resp_hdrs.update({
            b"Content-Type": b"text/html",
            b"Accept-Ranges": b"bytes",
            b"Vary": b"Accept-Encoding",
            b"ETag": b'"test-etag"',
            b"Last-Modified": b"Mon, 01 Jan 2000 00:00:00 GMT"
        })

        if inm_hdr == '"test-etag"' or ims_hdr == "Mon, 01 Jan 2000 00:00:00 GMT":
            status = b"304"
            phrase = b"Not Modified"
            content = b""
        elif "gzip" in ae_hdr:
            content = gzip.compress(content)
            resp_hdrs[b"Content-Encoding"] = b"gzip"
        elif range_hdr:
             try:
                start_str, end_str = range_hdr.replace("bytes=", "").split("-")
                start = int(start_str)
                end = int(end_str) if end_str else len(content) - 1
                full_len = len(content)
                content = content[start : end + 1]
                status = b"206"
                phrase = b"Partial Content"
                resp_hdrs[b"Content-Range"] = f"bytes {start}-{end}/{full_len}".encode('utf-8')
             except ValueError:
                pass

    if status != b"304":
        resp_hdrs[b"Content-Length"] = str(len(content)).encode('utf-8')
    
    # Convert headers list
    headers_list = [(k, v) for k, v in resp_hdrs.items()]
    
    exchange.response_start(status, phrase, headers_list)
    if method != "HEAD":
        exchange.response_body(content)
    exchange.response_done([])


class TestServer:
    def __init__(self):
        self.port = 8001
        self.host = b'127.0.0.1'
        self.server = thor.http.server.HttpServer(self.host, self.port)
        self.server.on("exchange", test_handler)

    def run(self):
        try:
            thor.run()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        thor.stop()
        for line in LOG_BUFFER:
            print(line)
        print(colorize(f"SERVER STATS: Requests: {REQUEST_COUNT}", Colors.CYAN))

if __name__ == "__main__":
    server = TestServer()
    
    def signal_handler(sig, frame):
        print(colorize("\nStopping server (signal)...", Colors.RED))
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    
    print(colorize(f"Test server running on port {server.port}", Colors.CYAN))
    server.run()
