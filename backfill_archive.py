#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
winefeed archive backfill (one-time)
====================================
The archive keeps one JSON snapshot per published day. Days before the archive
existed are still recoverable: the bot has committed feed_data.json on every
refresh since launch, so git history IS the back catalogue. This walks it and
writes archive/YYYY-MM-DD.json for each day we ever published.

Run once:  python3 backfill_archive.py
After that, build.py snapshots each new day automatically.

Schema note: feed_data.json changed shape on 2026-07-13 (commit efc5100), when
winefeed stopped aggregating and started writing its own briefs. Rows before that
are LISTS [source, url, date, head, summ, author, takeaways] and their news
summaries are the OUTLETS' excerpts, published with a credit and a link. We keep
the source and link on those rows rather than restyling someone else's excerpt as
our original brief: the archive shows what winefeed actually published that day.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, "archive")

def normalize(data):
    """Old list rows -> current dict rows. Newer data passes through untouched."""
    out = {"date": data.get("date"), "items": {}}
    for tab, rows in data.get("items", {}).items():
        fixed = []
        for row in rows:
            if isinstance(row, dict):
                fixed.append(row)
                continue
            # [source, url, date, head, summ, author, takeaways]
            row = list(row) + [""] * (7 - len(row))
            src, url, date, head, summ, author, tk = row[:7]
            fixed.append({
                "head": head, "date": date, "summ": summ,
                "source": src, "url": url, "author": author or "",
                "sources": [src] if src else [],
                "urls": [url] if url else [],
                "takeaways": tk or [],
            })
        out["items"][tab] = fixed
    return out

def git_days():
    """{date: normalized data} from every committed feed_data.json, newest commit wins."""
    commits = subprocess.run(["git", "log", "--format=%H", "--", "feed_data.json"],
                             cwd=HERE, capture_output=True, text=True).stdout.split()
    found = {}
    for c in commits:      # git log is newest-first, so the first hit for a date is final
        r = subprocess.run(["git", "show", f"{c}:feed_data.json"],
                           cwd=HERE, capture_output=True, text=True)
        if r.returncode:
            continue
        try:
            data = json.loads(r.stdout)
        except Exception:
            continue
        date = data.get("date")
        if date and date not in found and data.get("items"):
            found[date] = normalize(data)
    return found

def main():
    os.makedirs(ARCHIVE, exist_ok=True)
    days = git_days()
    if not days:
        print("No feed_data.json history found.", file=sys.stderr)
        return 1
    for date in sorted(days):
        path = os.path.join(ARCHIVE, f"{date}.json")
        if os.path.exists(path):
            print(f"  {date}: exists, left alone")
            continue
        with open(path, "w") as f:
            json.dump(days[date], f, indent=2, ensure_ascii=False)
        n = sum(len(v) for v in days[date]["items"].values())
        print(f"  {date}: wrote {n} stories")
    print(f"Backfilled {len(days)} day(s) into archive/")
    return 0

if __name__ == "__main__":
    sys.exit(main())
