#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
winefeed preview builder
========================
Turns a REAL generated page into one an Artifact can render, for design review.

Why this exists: previews must never be hand-mocked. An earlier archive preview was
hand-written with its row links stubbed to "#", so clicking a day did nothing and the
archive looked broken when production was fine. This transforms the ACTUAL built HTML
instead, so what you click is what ships:
  - inlines fonts.css / app.css / app.js (an Artifact's CSP can't fetch /app.css)
  - rewrites archive day links to the live site, so they really open
  - strips the doctype/head/body wrapper (the Artifact host supplies it)

Run after build.py:  python3 mk_preview.py
Writes winefeed-archive-preview.html (gitignored); publish that with the Artifact tool.
The deck needs no transform: build.py already emits winefeed_artifact.html.
"""
import re, os

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = "https://winefeed.co/archive/"

def build(src, out, title):
    h = open(os.path.join(HERE, src)).read()
    fonts = open(os.path.join(HERE, "fonts.css")).read().strip()
    css = open(os.path.join(HERE, "app.css")).read()
    js = open(os.path.join(HERE, "app.js")).read()

    # body only: the Artifact host supplies doctype/head/body
    m = re.search(r"<body>(.*)</body>", h, re.S)
    body = m.group(1) if m else h
    # external assets -> inline
    body = re.sub(r'<script src="[^"]*app\.js"[^>]*></script>', "", body)
    # archive day links -> the live pages, so they actually open
    body = re.sub(r'href="(\d{4}-\d{2}-\d{2}\.html)"',
                  lambda m: f'href="{LIVE}{m.group(1)}" target="_blank"', body)
    body = re.sub(r'href="\.\./"', 'href="https://winefeed.co/" target="_blank"', body)

    art = (f"<title>{title}</title>\n<style>\n{fonts}\n{css}\n</style>\n"
           f"{body}\n<script>\n{js}\n</script>\n")
    open(os.path.join(HERE, out), "w").write(art)
    print(f"{out}: {len(art)} bytes | day links -> live site")

if __name__ == "__main__":
    build("archive/index.html", "winefeed-archive-preview.html", "winefeed archive")
