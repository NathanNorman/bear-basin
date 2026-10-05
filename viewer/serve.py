#!/usr/bin/env python3
"""Serve the local viewer without caching generated model files."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

VIEWER_DIRECTORY = Path(__file__).resolve().parent


class NoCache(SimpleHTTPRequestHandler):
    """Always serve current files and declare browser module MIME types."""

    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".glb": "model/gltf-binary",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()


def create_server(port=8472, host="127.0.0.1"):
    """Return a server rooted at this file, independently of the current directory."""
    handler = partial(NoCache, directory=str(VIEWER_DIRECTORY))
    return ThreadingHTTPServer((host, port), handler)


def port_number(value):
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", nargs="?", type=port_number, default=8472)
    args = parser.parse_args(argv)
    try:
        with create_server(args.port) as server:
            print(f"Bear Basin viewer: http://127.0.0.1:{args.port}", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    except OSError as error:
        parser.exit(1, f"Could not start viewer server: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
