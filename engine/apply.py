#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Makes a copy of a Ladybird checkout with xenon-ublock's engine patches applied, for a build to use.

The checkout itself is left alone: the copy is a `git clone --shared` of it (it borrows the checkout's objects, so it
costs little), at the commit the patches are for (engine/LADYBIRD_BASE), with the patches applied as commits. A stamp
records what was applied, so running this again before each build only redoes the work when the patches or the base
change. Build outputs are never inside the copy, so resetting it is safe.

Usage:
  engine/apply.py --ladybird PATH --into DIR   make or refresh DIR
  engine/apply.py --ladybird PATH --check      check that the patches apply, without keeping anything
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
PATCHES_DIR = ENGINE_DIR / "patches"
STAMP_NAME = ".xenon-ublock-patches"
COMMITTER = ["-c", "user.name=xenon-ublock", "-c", "user.email=xenon-ublock@localhost", "-c", "commit.gpgsign=false"]


def git(directory: Path, *arguments: str, quiet: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(directory), *COMMITTER, *arguments], check=False, text=True,
                          capture_output=quiet)


def patches() -> list[Path]:
    return sorted(PATCHES_DIR.glob("*.patch"))


def stamp() -> str:
    digest = hashlib.sha256()
    digest.update((ENGINE_DIR / "LADYBIRD_BASE").read_bytes())
    for patch in patches():
        digest.update(patch.name.encode())
        digest.update(patch.read_bytes())
    return digest.hexdigest()


def base_commit() -> str:
    return (ENGINE_DIR / "LADYBIRD_BASE").read_text().strip()


def prepare(ladybird: Path, into: Path) -> None:
    """Makes `into` a clean copy of the base commit with the patches applied as commits."""
    base = base_commit()
    if git(ladybird, "cat-file", "-e", f"{base}^{{commit}}").returncode != 0:
        head = git(ladybird, "rev-parse", "HEAD").stdout.strip()
        raise SystemExit(f"{ladybird} does not have {base}, the Ladybird commit the patches are for (it is at {head}). "
                         "Update the submodule, or rebase the patches (see engine/README.md).")

    if not (into / ".git").exists():
        shutil.rmtree(into, ignore_errors=True)
        into.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(["git", "clone", "--quiet", "--shared", "--no-checkout", str(ladybird), str(into)],
                                text=True, capture_output=True)
        if result.returncode != 0:
            raise SystemExit(f"could not clone {ladybird}: {result.stderr.strip()}")

    if git(into, "cat-file", "-e", f"{base}^{{commit}}").returncode != 0:
        git(into, "fetch", "--quiet", str(ladybird.resolve()), base)
    for command in (["am", "--abort"], ["checkout", "--quiet", "--force", "--detach", base], ["clean", "-fdq"]):
        git(into, *command)

    result = git(into, "am", "--quiet", "--3way", "--keep-cr", "--committer-date-is-author-date", *map(str, patches()))
    if result.returncode != 0:
        failing = git(into, "am", "--show-current-patch=diff").stdout.splitlines()[:1]
        git(into, "am", "--abort")
        raise SystemExit(f"the patches do not apply to {base}:\n{result.stdout}{result.stderr}{failing}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ladybird", type=Path, required=True, help="the Ladybird checkout (Xenon's submodule)")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--into", type=Path, help="the patched copy to make or refresh")
    target.add_argument("--check", action="store_true", help="only check that the patches apply")
    args = parser.parse_args()

    ladybird = args.ladybird.resolve()
    if not (ladybird / "Libraries" / "LibWeb").is_dir():
        raise SystemExit(f"{ladybird} is not a Ladybird checkout")

    if args.check:
        with tempfile.TemporaryDirectory(prefix="xenon-ublock-apply-") as work:
            prepare(ladybird, Path(work) / "ladybird")
        print(f"{len(patches())} patches apply to {base_commit()[:10]}")
        return

    into = args.into.resolve()
    current = stamp()
    stamp_file = into / STAMP_NAME
    if stamp_file.exists() and stamp_file.read_text().strip() == current and git(into, "status", "--porcelain").stdout == f"?? {STAMP_NAME}\n":
        print(f"{into} is up to date with {len(patches())} xenon-ublock patches")
        return

    prepare(ladybird, into)
    stamp_file.write_text(current + "\n")
    print(f"{into}: Ladybird {base_commit()[:10]} with {len(patches())} xenon-ublock patches")


if __name__ == "__main__":
    sys.exit(main())
