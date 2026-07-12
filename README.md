# winefeed

A daily digest of the wine world, summarized. Four topic tabs (Market, Culture,
Science, Newsletters), five stories each, every link going to the original outlet.
Live at **winefeed.co**.

## How it works

- **`build.py`** — renders the site. Reads `feed_data.json` if present (live data),
  otherwise falls back to the built-in snapshot. Emits:
  - `index.html` — the standalone site (fonts embedded, zero external calls).
  - `winefeed_artifact.html` — preview variant.
- **`update.py`** — the engine. Pulls RSS from reputable wine outlets + independent
  Substacks, buckets items into the four topics, summarizes each from the outlet's
  own excerpt (never invented), keeps the 5 freshest per topic, writes
  `feed_data.json`, and runs `build.py`. Stdlib + `curl` only — no API key.
- **`.github/workflows/update.yml`** — runs `update.py` twice a day (06:30 & 18:30
  UTC), commits the refreshed `index.html`. GitHub Pages serves it.

## Run locally

```bash
python3 update.py      # fetch live news + rebuild
# or, static snapshot only:
python3 build.py
```

## Deploy (free, drops the GoDaddy hosting bill)

1. Push this folder to a GitHub repo.
2. **Settings -> Pages** -> Source: *Deploy from a branch*, `main` / `/ (root)`.
3. Custom domain: `winefeed.co` (the `CNAME` file is already here). Point the
   domain's DNS (at GoDaddy) at GitHub Pages per their custom-domain docs.
4. Cancel the GoDaddy **hosting** product (keep the domain registration).

The scheduled workflow then refreshes the site twice a day automatically.

## Tuning

- Feeds: `POOL` and `NEWSLETTERS` lists in `update.py`.
- Topic keywords: `KW` in `update.py`. Filler filter: `SKIP`.
- Design/tokens/copy: `build.py`.
