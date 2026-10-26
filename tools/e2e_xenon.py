#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Loads a test page in a built Xenon (or Ladybird) with a preset's lists, and checks what got blocked and hidden.

The browser runs headless (--headless=text) with a throwaway profile (--profile-path) whose settings turn the content
blocker on, and gets the lists the way a frontend can hand them over without touching the profile's list registry
(--content-blocker-list). A local server serves the page and records every request that reaches it: a blocked
request never arrives. The page reports how its decoy ad elements were styled.

Runs:
  control     [::1], blocker off      everything loads and shows
  generic     [::1], blocker on       ad requests blocked, generic hiding rules applied
  specific    127.0.0.1, blocker on   ad requests blocked, a site-specific hiding rule applied, and generic hiding
                                      off, because EasyList has @@://127.0.0.1$generichide (as it does in uBO)

Usage: tools/e2e_xenon.py [--app PATH] [--preset NAME]
"""

import argparse
import http.server
import json
import shutil
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Paths that generic first-party filters in EasyList and EasyPrivacy block, and paths nothing should block.
BLOCKED = {
    "/jquery.popunder.js": "script",  # EasyList: /jquery.popunder.js
    "/js/flyad.js": "script",  # EasyList: /js/flyad.js
    "/images/gen/etherscan-sm.gif": "img",  # EasyList: /images/gen/etherscan-sm.gif
    "/site-tracking-pixel.gif": "img",  # EasyPrivacy: -tracking-pixel.
}
ALLOWED = {"/app.js": "script", "/logo.gif": "img"}
# Decoy elements: two that generic EasyList rules hide (##.ads-banner, ###ad-banner-top), one that the extra
# site-specific rule hides, and one nothing should hide.
ELEMENTS = {"ads-banner": '<div class="ads-banner">', "ad-banner-top": '<div id="ad-banner-top">',
            "xenon-specific": '<div class="xenon-specific">', "article": '<div class="article">'}
GENERIC = {"ads-banner", "ad-banner-top"}
SPECIFIC_RULE = "127.0.0.1##.xenon-specific"

RUNS = [
    # (name, host, blocking, elements expected hidden)
    ("control", "::1", False, set()),
    ("generic", "::1", True, GENERIC),
    ("specific", "127.0.0.1", True, {"xenon-specific"}),
]

GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")


def test_page() -> str:
    elements = "\n".join(f"{tag}{name}</div>" for name, tag in ELEMENTS.items())
    resources = "\n".join(f'<script src="{path}"></script>' if kind == "script" else f'<img src="{path}">'
                          for path, kind in {**BLOCKED, **ALLOWED}.items())
    return f"""<!doctype html>
<html><head><title>xenon-ublock e2e</title></head>
<body>
{elements}
{resources}
<script>
const results = {{}};
for (const name of {json.dumps(list(ELEMENTS))}) {{
    const element = document.querySelector("." + name) || document.getElementById(name);
    results[name] = getComputedStyle(element).display;
}}
// A synchronous request finishes before the load event, so it cannot race the headless browser's exit.
const request = new XMLHttpRequest();
request.open("GET", "/report?" + encodeURIComponent(JSON.stringify(results)), false);
request.send();
document.body.append("results: " + JSON.stringify(results));
</script>
</body></html>
"""


class Recorder(http.server.BaseHTTPRequestHandler):
    requests: list[str] = []
    report: dict | None = None

    def do_GET(self):
        path, _, query = self.path.partition("?")
        Recorder.requests.append(path)
        if path == "/report":
            Recorder.report = json.loads(urllib.parse.unquote(query))
            body, content_type = b"ok", "text/plain"
        elif path == "/test.html":
            body, content_type = test_page().encode(), "text/html"
        elif path.endswith(".js"):
            body, content_type = b"/* ok */", "text/javascript"
        else:
            body, content_type = GIF, "image/gif"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def start_server(host: str) -> tuple[socketserver.TCPServer, str]:
    class Server(socketserver.ThreadingTCPServer):
        address_family = socket.AF_INET6 if ":" in host else socket.AF_INET
        daemon_threads = True

    server = Server((host, 0), Recorder)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    authority = f"[{host}]" if ":" in host else host
    return server, f"http://{authority}:{server.server_address[1]}/test.html"


def run_browser(executable: Path, profile: Path, lists: list[Path], url: str, blocking: bool, engine_arguments: list[str]) -> str:
    (profile / "config").mkdir(parents=True)
    (profile / "config" / "Settings.json").write_text(json.dumps({"contentBlockers": {"enabled": True}}))
    command = [str(executable), "--headless=text", "--profile-path", str(profile), *engine_arguments]
    for path in lists:
        command += ["--content-blocker-list", str(path)]
    if not blocking:
        command.append("--disable-content-blocker")
    command.append(url)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=90)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        raise SystemExit(f"{executable.name} did not exit within 90s:\n{stderr[-2000:]}")
    if process.returncode != 0:
        raise SystemExit(f"{executable.name} exited with {process.returncode}:\n{stderr[-2000:]}")
    return stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", type=Path, default=ROOT.parent / "Xenon" / "Build" / "release" / "bin" / "Xenon.app")
    parser.add_argument("--preset", default="helium")
    parser.add_argument("--dist", type=Path, help="built lists (default: dist, or dist-xenon with --engine xenon)")
    parser.add_argument("--engine", choices=("ladybird", "xenon"), default="ladybird",
                        help="xenon: the app has engine/patches; pass uBO's lists as trusted, and its resources")
    args = parser.parse_args()
    if args.dist is None:
        args.dist = ROOT / ("dist" if args.engine == "ladybird" else "dist-xenon")

    executable = args.app / "Contents" / "MacOS" / args.app.stem if args.app.suffix == ".app" else args.app
    if not executable.exists():
        raise SystemExit(f"{executable} does not exist; pass --app")
    manifest = json.loads((args.dist / "manifest.json").read_text())
    lists = manifest["presets"][args.preset]["lists"]
    engine_arguments = []
    if args.engine == "xenon":
        # As Xenon would pass them: uBO's own lists as trusted, the rest as ordinary lists, and uBO's resources.
        for entry in lists:
            if entry["trusted"]:
                engine_arguments += ["--trusted-content-blocker-list", str(args.dist / entry["file"])]
        engine_arguments += ["--content-blocker-resources", str(args.dist / manifest["resources"]["file"])]
        preset_lists = [args.dist / entry["file"] for entry in lists if not entry["trusted"]]
    else:
        preset_lists = [args.dist / args.preset / "all.txt"]

    failures = []
    work = Path(tempfile.mkdtemp(prefix="xenon-ublock-e2e-"))
    servers = {}
    try:
        extra = work / "site-specific.txt"
        extra.write_text(SPECIFIC_RULE + "\n")
        for name, host, blocking, hidden in RUNS:
            if host not in servers:
                servers[host] = start_server(host)
            url = servers[host][1]
            Recorder.requests, Recorder.report = [], None
            text = run_browser(executable, work / f"profile-{name}", [*preset_lists, extra], url, blocking, engine_arguments)
            arrived = set(Recorder.requests) - {"/test.html", "/report"}
            print(f"{name} ({url}, blocker {'on' if blocking else 'off'}):")
            print(f"  requests that reached the server: {sorted(arrived)}")
            print(f"  element display: {Recorder.report}")
            if Recorder.report is None:
                failures.append(f"{name}: the page never reported back; its text was:\n{text.strip()[:500]}")
                continue
            for path in BLOCKED:
                if blocking == (path in arrived):
                    failures.append(f"{name}: {path} {'loaded' if blocking else 'did not load'}")
            for path in ALLOWED:
                if path not in arrived:
                    failures.append(f"{name}: {path} did not load")
            for element, display in Recorder.report.items():
                if (element in hidden) != (display == "none"):
                    failures.append(f"{name}: {element} is display: {display}")
    finally:
        for server, _ in servers.values():
            server.shutdown()
        shutil.rmtree(work, ignore_errors=True)

    if failures:
        print("FAILED")
        for failure in failures:
            print(f"- {failure}")
        sys.exit(1)
    print(f"OK: {executable.name} blocked and hid what the {args.preset} preset should, and nothing else")


if __name__ == "__main__":
    main()
