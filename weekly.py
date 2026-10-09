# -*- coding: utf-8 -*-
"""Build weekly_data.json: the week's stories, from the daily snapshots in archive/*.json.

Takes the 7 daily editions ending on the given date (default: the latest snapshot),
merges repeats (same headline or any shared link), keeping the version with more outlets, and ranks each tab by how many
outlets reported the story, then by date. email_brief.py renders the weekly email from it.

Run:  python3 weekly.py [YYYY-MM-DD]
"""
import datetime
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TABS = ["MARKET", "CULTURE", "SCIENCE", "NEWSLETTERS"]
DAYS = 7


def keys(row):
    """Every link the story cites, plus its headline: a story repeats if it shares any of them."""
    ks = {u for u in (row.get("urls") or [row.get("url", "")]) if u}
    ks.add(row.get("head", "").strip().lower())
    return ks


def build(end=None):
    snaps = sorted(glob.glob(os.path.join(HERE, "archive", "????-??-??.json")))
    if not snaps:
        raise SystemExit("no archive/*.json snapshots")
    end = end or os.path.basename(snaps[-1])[:10]
    end_d = datetime.date.fromisoformat(end)
    start_d = end_d - datetime.timedelta(days=DAYS - 1)
    items = {t: [] for t in TABS}
    used = 0
    for path in reversed(snaps):  # newest first, so a repeat keeps its latest version
        day = datetime.date.fromisoformat(os.path.basename(path)[:10])
        if not start_d <= day <= end_d:
            continue
        used += 1
        for tab, rows in json.load(open(path)).get("items", {}).items():
            if tab not in items:
                continue
            for row in rows:
                ks = keys(row)
                hit = next((i for i, old in enumerate(items[tab]) if ks & keys(old)), None)
                if hit is None:
                    items[tab].append(row)
                elif len(row.get("sources") or []) > len(items[tab][hit].get("sources") or []):
                    items[tab][hit] = row  # same story, more outlets: keep the better-sourced version
    for tab in TABS:
        items[tab].sort(key=lambda r: (len(r.get("sources") or [1]), r.get("date", "")), reverse=True)
    out = {"start": start_d.isoformat(), "date": end_d.isoformat(), "editions": used, "items": items}
    with open(os.path.join(HERE, "weekly_data.json"), "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"weekly_data.json: {out['start']} to {out['date']}, {used} editions,",
          {t: len(v) for t, v in items.items()})
    return out


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else None)
