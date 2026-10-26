#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Checks built lists against Ladybird's real content blocker.

Builds libweb_content_blocker_rust from a Ladybird checkout (unmodified, into build/), links harness/engine_check.c
against it, and then:

  1. runs tests/engine-quirks.txt, which pins down the engine behaviors build.py works around;
  2. loads every list of every built preset on its own, and each preset's all.txt, timing the engine build;
  3. runs tests/vectors.txt against each preset;
  4. samples filters from each list and checks that the engine applies them in the full preset (a few can be
     overridden by another list's exception, so this passes at 95% or better).

Usage: tools/verify.py [--ladybird DIR] [--dist DIR] [--samples N]
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRATE = Path("Libraries/LibWeb/ContentBlocker/Rust")
SAMPLE_PASS_RATE = 0.95


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def ladybird_adblock_version(ladybird: Path) -> str:
    """The adblock version Ladybird's Cargo.lock resolves for the content blocker."""
    lock = tomllib.loads((ladybird / "Cargo.lock").read_text())
    versions = {package["version"] for package in lock["package"] if package["name"] == "adblock"}
    if len(versions) != 1:
        raise SystemExit(f"expected one adblock version in {ladybird / 'Cargo.lock'}, found {sorted(versions)}")
    manifest = tomllib.loads((ladybird / CRATE / "Cargo.toml").read_text())
    dependency = manifest["dependencies"]["adblock"]
    if isinstance(dependency, dict) and (dependency.get("features") or dependency.get("default-features") is False):
        raise SystemExit(f"Ladybird now builds adblock with non-default features ({dependency}); update probe/")
    return versions.pop()


def probe_adblock_version() -> str:
    manifest = tomllib.loads((ROOT / "probe" / "Cargo.toml").read_text())
    return manifest["dependencies"]["adblock"].lstrip("=")


def build_harness(ladybird: Path) -> Path:
    target = ROOT / "build" / "ladybird-target"
    command = ["cargo", "build", "--release", "--locked", "--quiet", "--manifest-path", str(ladybird / CRATE / "Cargo.toml"),
               "--target-dir", str(target)]
    # --locked keeps Ladybird's Cargo.lock as it is; the build only writes under build/.
    if subprocess.run(command + ["--offline"]).returncode != 0:
        run(command)
    library = target / "release" / "liblibweb_content_blocker_rust.a"
    binary = ROOT / "build" / "engine_check"
    compiler = os.environ.get("CC", "cc")
    system_libraries = ["-framework", "CoreFoundation", "-framework", "Security", "-liconv", "-Wl,-dead_strip"] \
        if sys.platform == "darwin" else ["-lpthread", "-ldl", "-lm", "-Wl,--gc-sections"]
    run([compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-o", str(binary), str(ROOT / "harness" / "engine_check.c"),
         str(library)] + system_libraries)
    return binary


def engine_check(binary: Path, *arguments) -> tuple[int, str]:
    result = subprocess.run([str(binary), *map(str, arguments)], capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise SystemExit(f"engine_check crashed ({result.returncode}): {result.stderr.strip()}")
    return result.returncode, result.stdout + result.stderr


def sample_vectors(list_path: Path, count: int, rng: random.Random) -> list[str]:
    """Builds vectors from filters simple enough to know a request or page they must affect."""
    network, specific, generic = [], [], []
    for line in list_path.read_text(encoding="utf-8").splitlines():
        if match := re.fullmatch(r"\|\|([a-z0-9.-]+\.[a-z]{2,})\^", line):
            network.append(f"block https://{match.group(1)}/xenon-verify.js https://xenon-verify.example/ script")
        elif match := re.fullmatch(r"([a-z0-9-]+(?:\.[a-z0-9-]+)+)##([.#])([A-Za-z_][\w-]*)", line):
            host, kind, name = match.groups()
            specific.append(f"hide https://{host}/ - - {kind}{name}")
        elif match := re.fullmatch(r"##([.#])([A-Za-z_][\w-]*)", line):
            kind, name = match.groups()
            classes, ids = (name, "-") if kind == "." else ("-", name)
            generic.append(f"hide https://xenon-verify.example/ {classes} {ids} {kind}{name}")
    vectors = []
    for pool in (network, specific, generic):
        vectors += rng.sample(pool, min(count, len(pool)))
    return vectors


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ladybird", type=Path,
                        default=Path(os.environ.get("LADYBIRD_SOURCE_DIR", ROOT.parent / "Xenon" / "ladybird")))
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--samples", type=int, default=100, help="filters to sample per kind and list (default 100)")
    args = parser.parse_args()

    ladybird = args.ladybird.resolve()
    if not (ladybird / CRATE / "Cargo.toml").exists():
        raise SystemExit(f"{ladybird} is not a Ladybird checkout (no {CRATE}); pass --ladybird")

    failures = []
    engine_version = ladybird_adblock_version(ladybird)
    print(f"Ladybird at {ladybird} builds adblock {engine_version}; the probe uses {probe_adblock_version()}")
    if engine_version != probe_adblock_version():
        failures.append(f"adblock version mismatch: update probe/Cargo.toml to ={engine_version} and rebuild the lists")

    binary = build_harness(ladybird)

    status, output = engine_check(binary, "--vectors", ROOT / "tests" / "engine-quirks.txt")
    print(f"Engine quirks: {output.strip().splitlines()[-1]}")
    if status:
        failures.append("engine quirks changed:\n" + "\n".join(l for l in output.splitlines() if l.startswith("FAIL")))

    manifest = json.loads((args.dist / "manifest.json").read_text())
    rng = random.Random(0)
    for preset, info in manifest["presets"].items():
        print(f"\n{info['title']} ({preset})")
        sample_lines = []
        for entry in info["lists"]:
            path = args.dist / entry["file"]
            status, output = engine_check(binary, "--rules", path)
            load = next((l for l in output.splitlines() if l.startswith(("LOAD", "FAIL"))), output.strip())
            print(f"  {entry['id']}: {load}")
            if status:
                failures.append(f"{preset}/{entry['id']} does not load: {load}")
            sample_lines += sample_vectors(path, args.samples, rng)

        combined = args.dist / info["combined_file"]
        status, output = engine_check(binary, "--rules", combined, "--repeat", "3", "--vectors", ROOT / "tests" / "vectors.txt")
        lines = output.splitlines()
        print(f"  all.txt: {lines[0]}")
        print(f"  tests/vectors.txt: {lines[-1]}")
        if status:
            failures.append(f"{preset}: tests/vectors.txt failed:\n" + "\n".join(l for l in lines if l.startswith("FAIL")))

        samples_path = ROOT / "build" / f"samples-{preset}.txt"
        samples_path.write_text("\n".join(sample_lines) + "\n")
        _, output = engine_check(binary, "--rules", combined, "--vectors", samples_path)
        passed = output.count("\nPASS ") + output.startswith("PASS ")
        failed = [l for l in output.splitlines() if l.startswith("FAIL")]
        rate = passed / max(passed + len(failed), 1)
        print(f"  sampled filters applied by the engine: {passed} of {passed + len(failed)} ({rate:.1%}); "
              "the rest are usually turned off by an exception in another list")
        for line in failed[:5]:
            print(f"    not applied: {line.removeprefix('FAIL ')}")
        if rate < SAMPLE_PASS_RATE:
            failures.append(f"{preset}: only {rate:.1%} of sampled filters took effect")

    print()
    if failures:
        print("FAILED")
        for failure in failures:
            print(f"- {failure}")
        sys.exit(1)
    print("OK: every list loads in Ladybird's content blocker and behaves as expected")


if __name__ == "__main__":
    main()
