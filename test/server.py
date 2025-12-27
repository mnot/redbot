#!/usr/bin/env python
# coding=UTF-8

import http.server
import threading
import sys
import time
import gzip
import signal
import socket

class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    RESET = '\033[0m'

REQUEST_COUNT = 0
ACTIVE_CONNECTIONS = 0
MAX_ACTIVE_CONNECTIONS = 0
COUNTER_LOCK = threading.Lock()
LOG_BUFFER = []

def colorize(text, color):
    if sys.stdout.isatty():
        return f"{color}{text}{Colors.RESET}"
    return text


class TestHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def setup(self):
        super().setup()
        global ACTIVE_CONNECTIONS, MAX_ACTIVE_CONNECTIONS
        with COUNTER_LOCK:
            ACTIVE_CONNECTIONS += 1
            if ACTIVE_CONNECTIONS > MAX_ACTIVE_CONNECTIONS:
                MAX_ACTIVE_CONNECTIONS = ACTIVE_CONNECTIONS

    def finish(self):
        super().finish()
        global ACTIVE_CONNECTIONS
        with COUNTER_LOCK:
            ACTIVE_CONNECTIONS -= 1

    def prepare_response(self):
        resp_hdrs = {
            "Cache-Control": "max-age=3600",
            "Connection": "close"
        }
        if self.path == "/img.png":
            content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            resp_hdrs["Content-Type"] = "image/png"
            status = 200
        else:
            padding = b"<!-- padding -->\n" * 100
            content = b"<html><body><h1>Hello World</h1><img src='img.png'><p>Some text content.</p>" + padding + b"</body></html>"
            status = 200

            range_hdr = self.headers.get("Range")
            ae_hdr = self.headers.get("Accept-Encoding", "")
            inm_hdr = self.headers.get("If-None-Match")
            ims_hdr = self.headers.get("If-Modified-Since")

            resp_hdrs.update({
                "Content-Type": "text/html",
                "Accept-Ranges": "bytes",
                "Vary": "Accept-Encoding",
                "ETag": '"test-etag"',
                "Last-Modified": "Mon, 01 Jan 2000 00:00:00 GMT"
            })

            if inm_hdr == '"test-etag"' or ims_hdr == "Mon, 01 Jan 2000 00:00:00 GMT":
                status = 304
                content = b""
            elif "gzip" in ae_hdr:
                content = gzip.compress(content)
                resp_hdrs["Content-Encoding"] = "gzip"
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
                    pass

        self.send_response(status)
        if status != 304:
            resp_hdrs["Content-Length"] = str(len(content))
        for k, v in resp_hdrs.items():
            self.send_header(k, v)
        self.end_headers()
        return content

    def log_message(self, format, *args):
        # Disable standard logging to reduce noise/contention
        pass

    def do_GET(self):
        global REQUEST_COUNT
        try:
            with COUNTER_LOCK:
                REQUEST_COUNT += 1
            content = self.prepare_response()
            self.wfile.write(content)
        except Exception as e:
            with COUNTER_LOCK:
                LOG_BUFFER.append(colorize(f"SERVER ERROR: {e}", Colors.RED))
        finally:
            self.close_connection = True

    def do_HEAD(self):
        global REQUEST_COUNT
        try:
            with COUNTER_LOCK:
                REQUEST_COUNT += 1
            self.prepare_response()
        except Exception as e:
            with COUNTER_LOCK:
                LOG_BUFFER.append(colorize(f"SERVER ERROR: {e}", Colors.RED))
        finally:
            self.close_connection = True

class QuietThreadingHTTPServer(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        # Suppress expected socket errors during tests
        try:
             _, exc, _ = sys.exc_info()
             if isinstance(exc, (ConnectionResetError, BrokenPipeError)):
                 return
        except Exception:
             pass
        super().handle_error(request, client_address)

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        super().server_bind()


class TestServer(threading.Thread):
    def __init__(self):
        super().__init__()
        self.port = 8001  # Different from redbot port
        http.server.ThreadingHTTPServer.request_queue_size = 100
        self.server = QuietThreadingHTTPServer(('127.0.0.1', self.port), TestHandler)
        self.server.daemon_threads = True
        self.server.allow_reuse_address = True
        self.daemon = True

    def run(self):
        self.server.serve_forever()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        for line in LOG_BUFFER:
            print(line)
        print(colorize(f"SERVER STATS: Requests: {REQUEST_COUNT}, Max Active Connections: {MAX_ACTIVE_CONNECTIONS}, Leaked Connections: {ACTIVE_CONNECTIONS}", Colors.CYAN))

if __name__ == "__main__":
    server = TestServer()
    server.start()
    print(colorize(f"Test server running on port {server.port}", Colors.CYAN))
    def signal_handler(sig, frame):
        print(colorize("\nStopping server (signal)...", Colors.RED))
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(colorize("\nStopping server...", Colors.RED))
        server.stop()
