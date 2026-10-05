#!/Users/nathan.norman/.pyenv/versions/3.12.11/bin/python3
"""Static server for the viewer that disables browser caching, so every refresh shows the latest export."""
import functools, http.server, os, sys

class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8472
handler = functools.partial(NoCache, directory=os.path.dirname(os.path.abspath(__file__)))
http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()
