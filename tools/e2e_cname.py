#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Checks CNAME uncloaking (engine/patches) in a built Xenon (or Ladybird) that has it.

A small DNS server answers for made-up *.xenontest names with CNAME chains, and the browser uses it (--dns-server). A test
page loads images from aliases; the local web server records the Host of every request that reaches it.

  metrics.site.xenontest       -> collect.tracker.xenontest     blocked: ||tracker.xenontest^ matches where the alias leads
  cdn.site.xenontest           -> edge.cdnprovider.xenontest    loads: no filter matches either name
  assets.site.xenontest        -> origin.site.xenontest         loads: an alias within the site is not uncloaked (uBO's default)
  exempt-alias.site.xenontest  -> pixel.exempt.xenontest        loads: @@||exempt.xenontest^$cname exempts it

With --live, it also loads https://www.microsoft.com/favicon.ico through the system resolver, where it is an alias of
an akamaiedge.net name, with a filter for that domain, to check the path that asks getaddrinfo for canonical names.

Usage: tools/e2e_cname.py [--app PATH] [--live]
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

CNAMES = {
    "metrics.site.xenontest": "collect.tracker.xenontest",
    "cdn.site.xenontest": "edge.cdnprovider.xenontest",
    "assets.site.xenontest": "origin.site.xenontest",
    "exempt-alias.site.xenontest": "pixel.exempt.xenontest",
}
# The test page's own host. It must not be 127.0.0.1: that is a secure context, which upgrades the http:// images it
# loads to https://.
PAGE_HOST = "page.portal.xenontest"
ADDRESSES = {name: "127.0.0.1" for name in [PAGE_HOST, "collect.tracker.xenontest", "edge.cdnprovider.xenontest", "origin.site.xenontest", "pixel.exempt.xenontest"]}

RULES = """
||tracker.xenontest^
||origin.site.xenontest^
||exempt.xenontest^
@@||exempt.xenontest^$cname
"""
EXPECTED_BLOCKED = {"metrics.site.xenontest"}
EXPECTED_LOADED = {"cdn.site.xenontest", "assets.site.xenontest", "exempt-alias.site.xenontest"}


class Recorder(http.server.BaseHTTPRequestHandler):
    hosts: list[str] = []
    report: dict | None = None
    reported = threading.Event()
    page = ""

    def respond(self, body: bytes, content_type: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        host = self.headers.get("Host", "").split(":")[0]
        Recorder.hosts.append(host)
        if self.path == "/test.html":
            self.respond(Recorder.page.encode(), "text/html")
        elif self.path == "/wait-for-report":
            Recorder.reported.wait(timeout=30)
            self.respond(GIF, "image/gif")
        else:
            self.respond(GIF, "image/gif")

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        Recorder.report = json.loads(body)
        Recorder.reported.set()
        self.respond(b"ok", "text/plain")

    def log_message(self, *args):
        pass


GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")


def page_loading(urls: dict[str, str]) -> str:
    return f"""<!doctype html><body><script>
const urls = {json.dumps(urls)};
(async () => {{
    const results = {{}};
    await Promise.all(Object.entries(urls).map(([name, url]) => new Promise(resolve => {{
        const image = new Image();
        image.onload = () => {{ results[name] = "loaded"; resolve(); }};
        image.onerror = () => {{ results[name] = "error"; resolve(); }};
        image.src = url;
    }})));
    await fetch("/report", {{ method: "POST", body: JSON.stringify(results) }});
}})();
</script><img src="/wait-for-report"></body>"""


def run_browser(executable: Path, work: Path, rules: str, url: str, extra_arguments: list[str]) -> None:
    profile = work / "profile"
    shutil.rmtree(profile, ignore_errors=True)
    (profile / "config").mkdir(parents=True)
    (profile / "config" / "Settings.json").write_text(json.dumps({"contentBlockers": {"enabled": True}}))
    (work / "rules.txt").write_text(rules)
    command = [str(executable), "--headless=text", "--profile-path", str(profile),
               "--content-blocker-list", str(work / "rules.txt"), *extra_arguments, url]
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise SystemExit(f"{executable.name} did not exit within 120s")
    if process.returncode != 0:
        raise SystemExit(f"{executable.name} exited with {process.returncode}:\n{process.stderr[-3000:]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", type=Path, default=ROOT / "build" / "xenon" / "Build" / "release" / "bin" / "Xenon.app")
    parser.add_argument("--live", action="store_true", help="also check the system resolver against a real CNAME")
    args = parser.parse_args()
    executable = args.app / "Contents" / "MacOS" / args.app.stem if args.app.suffix == ".app" else args.app

    dns, queries = localdns.start(ADDRESSES, CNAMES)
    web = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Recorder)
    web.daemon_threads = True
    threading.Thread(target=web.serve_forever, daemon=True).start()
    web_port = web.server_address[1]

    failures = []
    work = Path(tempfile.mkdtemp(prefix="xenon-ublock-cname-e2e-"))
    try:
        Recorder.page = page_loading({name: f"http://{name}:{web_port}/pixel.gif" for name in CNAMES})
        run_browser(executable, work, RULES, f"http://{PAGE_HOST}:{web_port}/test.html",
                    ["--dns-server", "127.0.0.1", "--dns-port", str(dns.server_address[1])])
        print("DNS queries:", sorted(set(queries)))
        print("hosts that reached the web server:", sorted(set(Recorder.hosts)))
        print("page report:", Recorder.report)
        report = Recorder.report or {}
        for name in EXPECTED_BLOCKED:
            ok = report.get(name) == "error" and name not in Recorder.hosts
            print(f"{'PASS' if ok else 'FAIL'} {name} (alias of {CNAMES[name]}) is blocked")
            failures += [] if ok else [name]
        for name in EXPECTED_LOADED:
            ok = report.get(name) == "loaded" and name in Recorder.hosts
            print(f"{'PASS' if ok else 'FAIL'} {name} (alias of {CNAMES[name]}) loads")
            failures += [] if ok else [name]

        if args.live:
            for rules, expected in (("", "loaded"), ("||akamaiedge.net^\n", "error")):
                Recorder.report, Recorder.reported = None, threading.Event()
                Recorder.page = page_loading({"www.microsoft.com": "https://www.microsoft.com/favicon.ico"})
                run_browser(executable, work, rules, f"http://127.0.0.1:{web_port}/test.html", [])
                result = (Recorder.report or {}).get("www.microsoft.com")
                label = f"system resolver: www.microsoft.com {'with' if rules else 'without'} ||akamaiedge.net^"
                print(f"{'PASS' if result == expected else 'FAIL'} {label}: {result}")
                failures += [] if result == expected else [label]
    finally:
        dns.shutdown()
        web.shutdown()
        shutil.rmtree(work, ignore_errors=True)

    if failures:
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
