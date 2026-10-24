#!/usr/bin/env python3
import argparse
import http.server
import os
import shutil
import subprocess
import urllib.parse
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))


def make_handler(files):
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            target = files.get(path)
            if not target:
                self.send_error(404)
                return
            local, ctype = target
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(os.path.getsize(local)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with open(local, "rb") as f:
                try:
                    shutil.copyfileobj(f, self.wfile, 1 << 20)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def log_message(self, *args):
            pass

    return Handler


def open_browser(url):
    if shutil.which("rundll32.exe"):
        subprocess.run(["rundll32.exe", "url.dll,FileProtocolHandler", url], check=False)
    else:
        webbrowser.open(url)


def main():
    ap = argparse.ArgumentParser(description="show nbody trajectories in the browser")
    ap.add_argument("csv", help="nbody output (t,x1,y1,...)")
    ap.add_argument("input", nargs="?", help="nbody input file; point size then follows mass")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true", help="only print the URL")
    args = ap.parse_args()
    for path in filter(None, [args.csv, args.input]):
        if not os.path.isfile(path):
            ap.error(f"{path}: file not found")

    files = {"/": (os.path.join(HERE, "viewer.html"), "text/html; charset=utf-8"),
             "/data.csv": (os.path.abspath(args.csv), "text/csv; charset=utf-8")}
    query = {"file": "data.csv", "name": os.path.basename(args.csv)}
    if args.input:
        files["/masses.txt"] = (os.path.abspath(args.input), "text/plain; charset=utf-8")
        query["masses"] = "masses.txt"

    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(files))
    url = f"http://localhost:{args.port}/?{urllib.parse.urlencode(query)}"
    print(f"viewer: {url}\nCtrl+C to stop", flush=True)
    if not args.no_open:
        open_browser(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
