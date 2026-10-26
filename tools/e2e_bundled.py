#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Checks that a Xenon with integration/xenon's commits applies uBlock Origin's scriptlets from the lists it bundles.

The browser gets no list options: only what Xenon bundles applies (UI/FilterLists.cpp passes uBO's own lists as
trusted, the others as ordinary lists, and uBO's resources). A local DNS server sends the hostnames of real filters
from those lists to a local web server, whose pages set the property each filter's scriptlet guards:

  huavod.top##+js(trusted-set-constant, ConFig.config.ads, 'json:{"pause":{"state":{}}}')   uBO's list, trusted
  amritlink.xyz##+js(set-constant, isPopupBlockedDetected, false)                           AdGuard's list

Usage: tools/e2e_bundled.py [--app PATH]
"""

import argparse
import http.server
import json
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import localdns

ROOT = Path(__file__).resolve().parent.parent

PAGES = {
    # host: (script that sets what the page would, expression the report reads, expected value)
    "huavod.top": ('window.ConFig = { config: { ads: "page value" } };', "JSON.stringify(window.ConFig.config.ads)",
                   json.dumps({"pause": {"state": {}}}, separators=(",", ":"))),
    "amritlink.xyz": ("window.isPopupBlockedDetected = true;", "String(window.isPopupBlockedDetected)", "false"),
}


class Recorder(http.server.BaseHTTPRequestHandler):
    reports: dict[str, str] = {}
    all_reported = threading.Event()

    def respond(self, body: bytes, content_type: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        host = self.headers.get("Host", "").split(":")[0]
        if self.path == "/wait-for-reports":
            Recorder.all_reported.wait(timeout=30)
            self.respond(b"GIF89a", "image/gif")
            return
        setup, expression, _ = PAGES.get(host, ("", "'unknown host'", ""))
        frames = "".join(f'<iframe src="http://{other}:{self.server.server_address[1]}/"></iframe>'
                         for other in PAGES if other != host) if self.path == "/top" else ""
        page = f"""<!doctype html><script>{setup}
let value; try {{ value = {expression}; }} catch (e) {{ value = "error: " + e; }}
fetch("/report", {{ method: "POST", body: value }});
</script>{frames}{'<img src="/wait-for-reports">' if frames else ''}"""
        self.respond(page.encode(), "text/html")

    def do_POST(self):
        host = self.headers.get("Host", "").split(":")[0]
        Recorder.reports[host] = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode()
        if set(Recorder.reports) >= set(PAGES):
            Recorder.all_reported.set()
        self.respond(b"ok", "text/plain")

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", type=Path, default=ROOT / "build" / "xenon" / "Build" / "release" / "bin" / "Xenon.app")
    args = parser.parse_args()
    executable = args.app / "Contents" / "MacOS" / args.app.stem if args.app.suffix == ".app" else args.app

    dns, _ = localdns.start({host: "127.0.0.1" for host in PAGES})
    web = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Recorder)
    web.daemon_threads = True
    threading.Thread(target=web.serve_forever, daemon=True).start()

    work = Path(tempfile.mkdtemp(prefix="xenon-ublock-bundled-e2e-"))
    try:
        (work / "config").mkdir()
        (work / "config" / "Settings.json").write_text(json.dumps({"contentBlockers": {"enabled": True}}))
        first = next(iter(PAGES))
        command = [str(executable), "--headless=text", "--profile-path", str(work), "--dns-server", "127.0.0.1",
                   "--dns-port", str(dns.server_address[1]), f"http://{first}:{web.server_address[1]}/top"]
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            raise SystemExit(f"{executable.name} did not exit within 120s; reports so far: {Recorder.reports}")
        if process.returncode != 0:
            raise SystemExit(f"{executable.name} exited with {process.returncode}:\n{process.stderr[-3000:]}")
    finally:
        dns.shutdown()
        web.shutdown()
        shutil.rmtree(work, ignore_errors=True)

    failed = False
    for host, (_, _, expected) in PAGES.items():
        got = Recorder.reports.get(host)
        ok = got == expected
        failed |= not ok
        print(f"{'PASS' if ok else 'FAIL'} {host}: {got!r} (expected {expected!r})")
    if failed:
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
