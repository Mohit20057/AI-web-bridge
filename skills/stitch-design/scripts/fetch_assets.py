#!/usr/bin/env python3
"""
Download a Stitch screen's HTML and screenshot into design/stitch/.
Usage:
  python fetch_assets.py --name home --html "<url>" --image "<url>" [--out design/stitch]
Standard library only — no dependencies needed.
"""
import argparse
import os
import sys
import urllib.error
import urllib.request

EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def download(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), r.headers.get_content_type()


def main():
    ap = argparse.ArgumentParser(description="Fetch Stitch assets")
    ap.add_argument("--name", required=True, help="page name, e.g. home, pricing")
    ap.add_argument("--html", help="URL to download screen HTML")
    ap.add_argument("--image", help="URL to download screen screenshot")
    ap.add_argument("--out", default="design/stitch", help="Output directory")
    a = ap.parse_args()

    if not (a.html or a.image):
        sys.exit("ERROR: give --html and/or --image")

    os.makedirs(a.out, exist_ok=True)
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in a.name.lower())
    failed = False

    for kind, url in (("html", a.html), ("image", a.image)):
        if not url:
            continue
        try:
            data, ctype = download(url)
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"ERROR downloading {kind}: {e}", file=sys.stderr)
            failed = True
            continue

        ext = ".html" if kind == "html" else EXT.get(ctype, ".png")
        path = os.path.join(a.out, slug + ext)
        with open(path, "wb") as f:
            f.write(data)
        print(f"Saved {path} ({len(data)} bytes)")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
