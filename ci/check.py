#!/usr/bin/env python3
"""Check, without a full Chromium checkout, that a new release still takes our changes.

    python3 ci/check.py <platform checkout> <work dir>

Fetches only the Chromium files our patches and brand.py touch, at the version
the platform repo pins, from chromium.googlesource.com. Replays upstream's
patches for those files, then ours, with the same patch flags ungoogled uses,
and runs brand.py --check on the result. Exits non-zero on the first thing
that would break the build, so the sync opens an issue and tags nothing.
"""

import base64
import concurrent.futures
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GITILES = "https://chromium.googlesource.com/chromium/src/+/refs/tags/%s/%s?format=%s"

sys.path.insert(0, os.path.join(ROOT, "branding"))
import brand  # noqa: E402


def log(msg):
    print("[check] " + msg, flush=True)


def get(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception as e:  # googlesource throttles bursts now and then
            if attempt == 3:
                raise SystemExit("[check] %s: %s" % (url, e))
            time.sleep(10 * 2 ** attempt)


def fetch(version, path):
    return base64.b64decode(get(GITILES % (version, path, "TEXT")))


def listing(version, folder):
    data = get(GITILES % (version, folder, "JSON")).decode("utf-8")
    return [e["name"] for e in json.loads(data[data.index("{"):])["entries"]]


def series(folder):
    path = os.path.join(folder, "series")
    return [os.path.join(folder, l.strip()) for l in open(path, encoding="utf-8")
            if l.strip() and not l.startswith("#")]


def touched(patch):
    """(path, the part of the patch for that path) for every file in it."""
    out, cur, path = [], [], None
    for line in open(patch, encoding="utf-8", errors="replace").read().splitlines(True):
        if line.startswith("--- "):
            if cur and path:
                out.append((path, "".join(cur)))
            cur, path = [line], None
            continue
        if line.startswith("+++ ") and cur:
            m = re.match(r"\+\+\+ b/(\S+)", line)
            path = m.group(1) if m else None
        if cur:
            cur.append(line)
    if cur and path:
        out.append((path, "".join(cur)))
    return out


def run_patch(src, text, label):
    r = subprocess.run(["patch", "-p1", "--ignore-whitespace", "--forward", "--no-backup-if-mismatch", "-d", src],
                       input=text.encode("utf-8"), capture_output=True)
    if r.returncode != 0:
        sys.exit("[check] %s does not apply:\n%s" % (label, r.stdout.decode(errors="replace")))


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    platform, work = sys.argv[1:]
    version = open(os.path.join(platform, "ungoogled-chromium", "chromium_version.txt")).read().strip()
    src = os.path.join(work, "src")
    shutil.rmtree(src, ignore_errors=True)
    log("Chromium " + version)

    ours = series(os.path.join(ROOT, "patches"))
    files = {p for patch in ours for p, text in touched(patch) if not text.startswith("--- /dev/null")}
    files.add("chrome/app/theme/chromium/BRANDING")
    for grd, parts, xtb_glob in brand.STRINGS:
        files.update([grd] + parts)
        folder, pattern = os.path.split(xtb_glob)
        files.update(folder + "/" + n for n in listing(version, folder) if fnmatch.fnmatch(n, pattern))

    def one(path):
        full = os.path.join(src, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, "wb").write(fetch(version, path))

    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        list(pool.map(one, sorted(files)))
    log("fetched %d files" % len(files))

    upstream = series(os.path.join(platform, "ungoogled-chromium", "patches")) + series(os.path.join(platform, "patches"))
    replayed = 0
    for patch in upstream:
        if os.path.basename(os.path.dirname(patch)) == "grabzy":
            continue
        for path, text in touched(patch):
            if path in files:
                run_patch(src, text, "%s (%s)" % (os.path.relpath(patch, platform), path))
                replayed += 1
    log("upstream: %d hunks on our files replayed" % replayed)
    for patch in ours:
        run_patch(src, open(patch, encoding="utf-8").read(), "our " + os.path.basename(patch))
    log("ours: %d patches apply" % len(ours))

    brand.brand_strings(src, write=False)
    brand.brand_file(src, write=False, mac=False)
    brand.stamp_release(src, write=False)
    log("check passed")


if __name__ == "__main__":
    main()
