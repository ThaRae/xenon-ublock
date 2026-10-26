#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Checks the engine features from engine/patches in a built Xenon (or Ladybird) that has them.

Runs the browser headless with a throwaway profile, uBO's resources (--content-blocker-resources), and two small lists
of test filters: one passed as trusted (--trusted-content-blocker-list), one not. A local server serves a test page
and records every request that reaches it. The page runs its checks, reports them, and only then lets its load event
fire (an image the server holds until the report arrives), so the headless browser cannot exit before the checks end.

Usage: tools/e2e_engine.py [--app PATH] [--resources PATH]
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
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

UNTRUSTED_RULES = """
127.0.0.1##+js(set-constant, xenonTest.ads, false)
127.0.0.1##+js(trusted-set-constant, xenonTest.untrustedTrusted, 7)
127.0.0.1##.promo:has-text(Sponsored)
127.0.0.1##.overlay:remove()
127.0.0.1##.clicky:remove-attr(onclick)
||127.0.0.1^*/ads/ima3.js$script,redirect=google-ima.js
||127.0.0.1^*/ads/blocked.js$script
||127.0.0.1^$removeparam=utm_source
||127.0.0.1^*/popup-ad.html$popup
||127.0.0.1^*/late-popup-ad.html$popup
||127.0.0.1^*/method-test$xhr,method=post
"""
TRUSTED_RULES = """
127.0.0.1##+js(trusted-set-constant, xenonTest.trusted, 42)
"""

PAGE = """<!doctype html>
<html><head><title>xenon-ublock engine e2e</title>
<script>
// Scriptlets run before this: set-constant makes xenonTest.ads false whatever the page assigns.
window.xenonTest = { ads: true, trusted: 0, untrustedTrusted: 0 };
const results = { scriptlets: { ads: window.xenonTest.ads, trusted: window.xenonTest.trusted, untrustedTrusted: window.xenonTest.untrustedTrusted } };
results.surrogate = "pending";
results.blockedScript = "pending";
</script>
<script src="/ads/ima3.js" onload="results.surrogate = (window.google && window.google.ima) ? 'surrogate' : 'loaded-without-ima'" onerror="results.surrogate = 'error'"></script>
<script src="/ads/blocked.js" onload="results.blockedScript = 'loaded'" onerror="results.blockedScript = 'error'"></script>
</head>
<body>
<div class="promo" id="sponsored">Sponsored content</div>
<div class="promo" id="organic">An ordinary story</div>
<div class="overlay" id="overlay">Overlay</div>
<a class="clicky" id="clicky" href="#" onclick="return false">link</a>
<iframe id="frame" src="/frame.html?utm_source=e2e&page=1"></iframe>
<script>
(async () => {
    await new Promise(resolve => document.getElementById("frame").addEventListener("load", resolve, { once: true }));
    results.frameURL = document.getElementById("frame").contentWindow.location.href;

    const popup = window.open("/popup-ad.html");
    results.popupBlocked = popup === null;
    const allowedPopup = window.open("/popup-ok.html");
    results.allowedPopupOpened = allowedPopup !== null;
    if (allowedPopup) allowedPopup.close();
    const late = window.open("");
    if (late) late.location = "/late-popup-ad.html";

    const echo = await fetch("/echo?utm_source=e2e&id=1").then(r => r.text()).catch(e => "error: " + e);
    results.fetchURLSeenByServer = echo;
    results.postBlocked = await fetch("/method-test", { method: "POST", body: "x" }).then(() => false, () => true);
    results.getAllowed = await fetch("/method-test").then(() => true, () => false);

    await new Promise(resolve => setTimeout(resolve, 500));
    const display = id => { const e = document.getElementById(id); return e ? getComputedStyle(e).display : "removed"; };
    results.procedural = { sponsored: display("sponsored"), organic: display("organic"), overlay: display("overlay"), clickyOnclick: document.getElementById("clicky").hasAttribute("onclick") };

    await fetch("/report", { method: "POST", body: JSON.stringify(results) });
})();
</script>
<img src="/wait-for-report">
</body></html>
"""


class Recorder(http.server.BaseHTTPRequestHandler):
    requests: list[str] = []
    report: dict | None = None
    reported = threading.Event()

    def respond(self, body: bytes, content_type: str):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        Recorder.requests.append(self.path)
        path, _, _ = self.path.partition("?")
        if path == "/test.html":
            self.respond(PAGE.encode(), "text/html")
        elif path == "/echo":
            self.respond(self.path.encode(), "text/plain")
        elif path == "/wait-for-report":
            Recorder.reported.wait(timeout=20)
            self.respond(bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b"), "image/gif")
        elif path.endswith(".js"):
            self.respond(b"window.realScriptRan = true;", "text/javascript")
        else:
            self.respond(b"<!doctype html><p>page", "text/html")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        Recorder.requests.append("POST " + self.path)
        if self.path == "/report":
            Recorder.report = json.loads(body)
            Recorder.reported.set()
        self.respond(b"ok", "text/plain")

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app", type=Path, default=ROOT / "build" / "xenon" / "Build" / "release" / "bin" / "Xenon.app")
    parser.add_argument("--resources", type=Path, default=ROOT / "dist" / "resources" / "ublock-resources.json")
    args = parser.parse_args()

    executable = args.app / "Contents" / "MacOS" / args.app.stem if args.app.suffix == ".app" else args.app
    for path in (executable, args.resources):
        if not path.exists():
            raise SystemExit(f"{path} does not exist")

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Recorder)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/test.html"

    work = Path(tempfile.mkdtemp(prefix="xenon-ublock-engine-e2e-"))
    try:
        (work / "untrusted.txt").write_text(UNTRUSTED_RULES)
        (work / "trusted.txt").write_text(TRUSTED_RULES)
        profile = work / "profile"
        (profile / "config").mkdir(parents=True)
        (profile / "config" / "Settings.json").write_text(json.dumps({"contentBlockers": {"enabled": True}}))
        # --allow-popups turns off Ladybird's own popup blocker, which stops every popup the page opens without a user
        # gesture, so the popup checks see only the content blocker.
        command = [str(executable), "--headless=text", "--allow-popups", "--profile-path", str(profile),
                   "--content-blocker-list", str(work / "untrusted.txt"),
                   "--trusted-content-blocker-list", str(work / "trusted.txt"),
                   "--content-blocker-resources", str(args.resources), url]
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired as error:
            print((error.stderr or b"")[-3000:].decode(errors="replace"), file=sys.stderr)
            raise SystemExit(f"{executable.name} did not exit within 120s; requests so far: {Recorder.requests}")
        if process.returncode != 0:
            raise SystemExit(f"{executable.name} exited with {process.returncode}:\n{process.stderr[-3000:]}")
    finally:
        server.shutdown()
        shutil.rmtree(work, ignore_errors=True)

    report = Recorder.report
    seen = Recorder.requests
    print("requests that reached the server:", seen)
    print("report:", json.dumps(report, indent=2))
    if report is None:
        raise SystemExit("FAILED: the page never reported back")

    checks = {
        "scriptlet set-constant applied": report["scriptlets"]["ads"] is False,
        "trusted scriptlet applied from the trusted list": report["scriptlets"]["trusted"] == 42,
        "trusted scriptlet ignored in an untrusted list": report["scriptlets"]["untrustedTrusted"] == 0,
        "procedural :has-text() hid the sponsored post": report["procedural"]["sponsored"] == "none",
        "procedural :has-text() left the other post": report["procedural"]["organic"] != "none",
        ":remove() removed the overlay": report["procedural"]["overlay"] == "removed",
        ":remove-attr() removed onclick": report["procedural"]["clickyOnclick"] is False,
        "$redirect answered with the google-ima.js surrogate": report["surrogate"] == "surrogate",
        "$redirect request never reached the server": not any(r.startswith("/ads/ima3.js") for r in seen),
        "plain block still fails the script": report["blockedScript"] == "error",
        "$removeparam cleaned the frame's navigation URL": "utm_source" not in report["frameURL"] and "page=1" in report["frameURL"],
        "$removeparam cleaned the request the server saw": "/frame.html?page=1" in seen and not any("utm_source" in r for r in seen),
        "$removeparam cleaned fetch()": report["fetchURLSeenByServer"] == "/echo?id=1",
        "$popup blocked window.open()": report["popupBlocked"] is True and "/popup-ad.html" not in seen,
        "an ordinary popup still opens": report["allowedPopupOpened"] is True,
        "$popup blocked a popup navigated after opening": "/late-popup-ad.html" not in seen,
        "$method=post blocked the POST": report["postBlocked"] is True and "POST /method-test" not in seen,
        "$method=post left the GET": report["getAllowed"] is True,
    }
    failed = [name for name, ok in checks.items() if not ok]
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    if failed:
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
