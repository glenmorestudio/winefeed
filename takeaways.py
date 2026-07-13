#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
winefeed takeaways
==================
Turns the borrowed RSS excerpt into ORIGINAL, scannable key-takeaway bullets,
strictly grounded in the source article (no invented facts). Reads feed_data.json,
enriches each item with a `takeaways` list, writes it back.

Model: Claude Haiku (cheap). Key from env ANTHROPIC_API_KEY or ~/.primal_wine_club/config.json.
Called by update.py when a key is present; skipped (excerpt fallback) when not.
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = "claude-haiku-4-5-20251001"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"

def get_key():
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k:
        return k
    cfg = os.path.expanduser("~/.primal_wine_club/config.json")
    if os.path.exists(cfg):
        try:
            return json.load(open(cfg)).get("api_key")
        except Exception:
            return None
    return None

TAG = re.compile(r"<[^>]+>")
def fetch_body(url):
    """Readability-ish article body extraction; '' on failure."""
    import html as _html
    try:
        r = subprocess.run(["curl", "-sL", "--max-time", "20", "-A", UA, url],
                           capture_output=True, timeout=30)
        htmlt = r.stdout.decode("utf-8", "replace")
    except Exception:
        return ""
    # drop non-content regions before extracting paragraphs
    for tag in ("script", "style", "nav", "header", "footer", "aside", "form", "figure", "noscript"):
        htmlt = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", " ", htmlt, flags=re.S | re.I)
    # prefer the main article region if the page marks one
    region = htmlt
    for pat in (r"<article\b[^>]*>(.*?)</article>", r"<main\b[^>]*>(.*?)</main>",
                r'<div[^>]*class="[^"]*(?:article|post|entry|content)[^"]*"[^>]*>(.*?)</div>'):
        m = re.search(pat, htmlt, re.S | re.I)
        if m and len(m.group(1)) > 400:
            region = m.group(1)
            break
    paras = re.findall(r"<p[^>]*>(.*?)</p>", region, re.S | re.I)
    kept = []
    for p in paras:
        t = re.sub(r"\s+", " ", _html.unescape(TAG.sub(" ", p))).strip()
        if len(t) >= 40 and "cookie" not in t.lower() and "subscribe" not in t.lower():
            kept.append(t)
    return " ".join(kept)[:8000]

PROMPT = """You are the editor of Winefeed, a wine-news brief read by wine lovers and trade.
From the source article below, write 4-5 KEY TAKEAWAY bullets: the most important facts a reader should know so they can skip the full article.

Hard rules:
- Use ONLY facts explicitly stated in the source. Never invent or infer numbers, names, dates, or claims.
- Aim for 4-5 bullets when the source supports it. If the source is thin, return fewer (even 1). If there are zero real facts, return {"takeaways": []}.
- NEVER write ABOUT the article, source, paywall, subscribers, metadata, or missing content. Output wine facts or nothing.
- Each bullet: one sentence, under 20 words, plain and factual. No marketing, no "the article says", no fluff.
- Neutral, information-dense. Lead with the concrete fact (who/what/number). No two bullets should repeat the same fact.

Return STRICT JSON only: {"takeaways": ["...", "...", "..."]}

TITLE: %(title)s
SOURCE: %(source)s
ARTICLE:
%(body)s
"""

def call_haiku(key, title, source, body):
    payload = json.dumps({
        "model": MODEL,
        "max_tokens": 550,
        "messages": [{"role": "user", "content": PROMPT % {"title": title, "source": source, "body": body}}],
    })
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "40", "https://api.anthropic.com/v1/messages",
             "-H", "x-api-key: " + key,
             "-H", "anthropic-version: 2023-06-01",
             "-H", "content-type: application/json",
             "-d", payload],
            capture_output=True, timeout=60)
        resp = json.loads(r.stdout.decode("utf-8", "replace"))
        text = resp["content"][0]["text"]
    except Exception as e:
        print(f"    ! haiku call failed: {e}", file=sys.stderr)
        return []
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except Exception:
        return []
    outs = []
    for t in data.get("takeaways", [])[:5]:
        t = re.sub(r"\s+", " ", str(t)).strip(" .–-").strip()
        if 8 <= len(t) <= 180 and not is_meta(t):
            outs.append(t + ".")
    return outs

# reject bullets that talk about the article/source instead of the wine facts
_META = ["paywall", "subscriber", "not provided", "cannot be extracted", "editorial standard",
         "metadata", "source material", "full article", "full text", "the article", "this article",
         "the source", "the piece", "the post", "without the full", "no substantive", "the excerpt",
         "insufficient", "unable to"]
def is_meta(b):
    low = b.lower()
    return any(p in low for p in _META)

def enrich(path=None):
    path = path or os.path.join(HERE, "feed_data.json")
    key = get_key()
    if not key:
        print("No Anthropic key found; skipping takeaways (excerpts kept).")
        return False
    d = json.load(open(path))
    total = 0
    for tab, rows in d["items"].items():
        print(f"{tab}:")
        for row in rows:
            src, url, date, head, summ = row[0], row[1], row[2], row[3], row[4]
            author = row[5] if len(row) > 5 else ""
            body = fetch_body(url)
            if len(body) < 200:
                body = summ           # fall back to the excerpt we already have
            tk = call_haiku(key, head, src, body)
            # normalize row to [src,url,date,head,summ,author,takeaways]
            row[:] = [src, url, date, head, summ, author, tk]
            total += 1
            print(f"  {src}: {head[:44]} -> {len(tk)} bullets")
    json.dump(d, open(path, "w"), indent=2, ensure_ascii=False)
    print(f"Enriched {total} items with takeaways.")
    return True

if __name__ == "__main__":
    enrich()
