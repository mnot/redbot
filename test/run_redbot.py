#!/usr/bin/env python
# coding=UTF-8

import sys
import signal
from configparser import ConfigParser
import tempfile
import shutil
import atexit
import redbot.daemon

save_dir = tempfile.mkdtemp()

def cleanup():
    shutil.rmtree(save_dir, ignore_errors=True)

atexit.register(cleanup)

def run():
    conf = ConfigParser()
    conf.read("config.txt")
    if "redbot" not in conf:
        conf.add_section("redbot")
    
    conf["redbot"]["enable_local_access"] = "true"
    # Disable rate limits for tests
    if "limit_client_tests" in conf["redbot"]:
        del conf["redbot"]["limit_client_tests"]
    if "instant_limit" in conf["redbot"]:
        del conf["redbot"]["instant_limit"]
        
    redconf = conf["redbot"]
    redconf["save_dir"] = save_dir
    redconf["host"] = "127.0.0.1"
    redconf["port"] = "8000"
    
    server = redbot.daemon.RedBotServer(redconf)

    def signal_handler(sig, frame):
        print("Stopping REDbot server...", file=sys.stderr)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)

    print(f"Starting REDbot server on {redconf['host']}:{redconf['port']}...", file=sys.stderr)
    try:
        server.run()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    run()
