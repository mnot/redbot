#!/usr/bin/env python
# coding=UTF-8

import http.server
import threading
import sys
import time

class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    RESET = '\033[0m'

def colorize(text, color):
    if sys.stdout.isatty():
        return f"{color}{text}{Colors.RESET}"
    return text


class TestHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def prepare_response(self):
        if self.path == "/img.png":
            content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            ctype = "image/png"
            status = 200
            self.send_response(status)
        else:
            # HTML content with image for 'check embedded' and padding for Range
            padding = b"<!-- padding -->\n" * 100
            content = b"<html><body><h1>Hello World</h1><img src='img.png'><p>Some text content.</p>" + padding + b"</body></html>"
            ctype = "text/html"
            status = 200
            
            # Request Headers
            range_hdr = self.headers.get("Range")
            ae_hdr = self.headers.get("Accept-Encoding", "")
            inm_hdr = self.headers.get("If-None-Match")
            ims_hdr = self.headers.get("If-Modified-Since")
            
            # Response Headers
            resp_hdrs = {
                "Content-Type": ctype,
                "Cache-Control": "max-age=3600",
                "Accept-Ranges": "bytes",
                "Vary": "Accept-Encoding",
                "ETag": '"test-etag"',
                "Last-Modified": "Mon, 01 Jan 2000 00:00:00 GMT"
            }

            # Conditionals (IMS/INM)
            if inm_hdr == '"test-etag"' or ims_hdr == "Mon, 01 Jan 2000 00:00:00 GMT":
                status = 304
                content = b""

            # Content Negotiation (Gzip)
            elif "gzip" in ae_hdr:
                import gzip
                content = gzip.compress(content)
                resp_hdrs["Content-Encoding"] = "gzip"

            # Range Requests
            elif range_hdr:
                 try:
                    start_str, end_str = range_hdr.replace("bytes=", "").split("-")
                    start = int(start_str)
                    end = int(end_str) if end_str else len(content) - 1
                    full_len = len(content)
                    content = content[start : end + 1]
                    status = 206
                    resp_hdrs["Content-Range"] = f"bytes {start}-{end}/{full_len}"
                 except ValueError:
                    pass # Invalid range, ignore

            self.send_response(status)
            for k, v in resp_hdrs.items():
                self.send_header(k, v)
        
        if status != 304:
             self.send_header("Content-Length", str(len(content)))

        self.send_header("Connection", "close")
        self.end_headers()
        return content

    def do_GET(self):
        print(colorize(f"SERVER: TestHandler GET {self.path}", Colors.GREEN))
        content = self.prepare_response()
        self.wfile.flush()
        self.wfile.write(content)
        self.wfile.flush()
        self.close_connection = True

    def do_HEAD(self):
        self.prepare_response()
        self.wfile.flush()
        self.close_connection = True


class TestServer(threading.Thread):
    def __init__(self):
        super().__init__()
        self.port = 8001  # Different from redbot port
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', self.port), TestHandler)
        self.server.daemon_threads = True
        self.server.allow_reuse_address = True
        self.daemon = True

    def run(self):
        self.server.serve_forever()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

if __name__ == "__main__":
    server = TestServer()
    server.start()
    print(colorize(f"Test server running on port {server.port}", Colors.CYAN))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(colorize("Stopping server...", Colors.RED))
        server.stop()
