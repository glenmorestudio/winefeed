#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
winefeed takeaways
==================
Turns the day's clustered coverage into ORIGINAL, scannable briefs, strictly
grounded in the source articles (no invented facts). Reads feed_data.json, enriches
each story in place, writes it back.

- News topics (MARKET/CULTURE/SCIENCE): each row is a CLUSTER of URLs covering the
  same event. We fetch every member's body (falling back to archive.ph for
  paywalled/thin pages, to lift one or two extra facts), combine them, and have
  Claude write OUR OWN headline + 4-5 key-takeaway bullets. Facts are public; the
  phrasing is ours, which is what keeps it copyright-safe. No outbound link.
- NEWSLETTERS: single article, per-piece bullets, headline + link kept (we credit
  and point to the independent writer).

Model: Claude Haiku (cheap). Key from env ANTHROPIC_API_KEY or ~/.primal_wine_club/config.json.
Called by update.py; if no key, cards fall back to the freshest excerpt.
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
def _extract(htmlt):
    """Readability-ish: pull the article paragraphs out of a raw HTML page."""
    import html as _html
    if not htmlt:
        return ""
    for tag in ("script", "style", "nav", "header", "footer", "aside", "form", "figure", "noscript"):
        htmlt = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", " ", htmlt, flags=re.S | re.I)
    region = htmlt
    for pat in (r"<article\b[^>]*>(.*?)</article>", r"<main\b[^>]*>(.*?)</main>",
                r'<div[^>]*class="[^"]*(?:article|post|entry|content)[^"]*"[^>]*>(.*?)</div>'):
        m = re.search(pat, htmlt, re.S | re.I)
        if m and len(m.group(1)) > 400:
            region = m.group(1)
            break
    kept = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", region, re.S | re.I):
        t = re.sub(r"\s+", " ", _html.unescape(TAG.sub(" ", p))).strip()
        if len(t) >= 40 and "cookie" not in t.lower() and "subscribe" not in t.lower():
            kept.append(t)
    return " ".join(kept)[:8000]

def _curl(url, t=20):
    try:
        r = subprocess.run(["curl", "-sL", "--max-time", str(t), "-A", UA, url],
                           capture_output=True, timeout=t + 10)
        return r.stdout.decode("utf-8", "replace")
    except Exception:
        return ""

def fetch_body(url, allow_archive=True):
    """Article body; if the live page is thin/paywalled, try archive.ph for a
    couple more grounded facts. Best-effort — archive can rate-limit CI, so the
    brief must stand on whatever it returns."""
    body = _extract(_curl(url))
    if len(body) < 400 and allow_archive:
        arc = _extract(_curl("https://archive.ph/newest/" + url, t=25))
        if len(arc) > len(body):
            body = arc
    return body

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

# ---- synthesis: our own headline + bullets from the COMBINED coverage ---------
SYNTH_PROMPT = """You are the editor of Winefeed, an independent wine-news desk. One or more outlets have covered the same story; their reporting is combined below.
Write Winefeed's OWN brief on this story.

Return STRICT JSON only: {"headline": "...", "takeaways": ["...", "..."]}

headline: an original, specific headline IN YOUR OWN WORDS. Under 12 words, concrete (who/what), no clickbait, no outlet names, no "Winefeed".
takeaways: 4-5 KEY TAKEAWAY bullets a reader can skim to know the story.

Hard rules:
- Use ONLY facts explicitly stated in the source material. Never invent or infer numbers, names, dates, quotes, or claims.
- Write facts in your OWN words. Do NOT copy sentences from the sources.
- If several outlets agree on a fact, state it once. If they conflict, keep the specific/attributed version.
- Each bullet: one sentence, under 20 words, plain and factual. Lead with the concrete fact. No two bullets repeat the same fact.
- NEVER write ABOUT the articles, outlets, paywalls, or missing content. Output wine facts or nothing.
- If there are no real facts, return {"headline": "", "takeaways": []}.

STORY (working title): %(title)s
SOURCE MATERIAL:
%(body)s
"""

def _call(key, prompt, max_tokens=650):
    payload = json.dumps({
        "model": MODEL, "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    })
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "50", "https://api.anthropic.com/v1/messages",
             "-H", "x-api-key: " + key,
             "-H", "anthropic-version: 2023-06-01",
             "-H", "content-type: application/json",
             "-d", payload],
            capture_output=True, timeout=70)
        text = json.loads(r.stdout.decode("utf-8", "replace"))["content"][0]["text"]
    except Exception as e:
        print(f"    ! haiku call failed: {e}", file=sys.stderr)
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

def _clean_bullets(raw):
    outs = []
    for t in (raw or [])[:5]:
        t = re.sub(r"\s+", " ", str(t)).strip(" .–-").strip()
        if 8 <= len(t) <= 180 and not is_meta(t):
            outs.append(t + ".")
    return outs

def synthesize(key, title, body):
    """Return (headline, takeaways). headline '' if the model wrote nothing usable."""
    data = _call(key, SYNTH_PROMPT % {"title": title, "body": body})
    if not data:
        return "", []
    head = re.sub(r"\s+", " ", str(data.get("headline", ""))).strip().strip('"').strip()
    if is_meta(head) or len(head) < 8:
        head = ""
    return head, _clean_bullets(data.get("takeaways", []))

def combined_body(urls, seed=""):
    """Fetch + concatenate every cluster member's body (archive.ph fallback)."""
    parts, seen = [], set()
    for u in urls:
        b = fetch_body(u)
        if len(b) >= 200:
            parts.append(b)
            seen.add(u)
    combo = "\n\n---\n\n".join(parts)
    if len(combo) < 200 and seed:      # everything paywalled/JS -> lean on the excerpt
        combo = seed
    return combo[:12000]

# post-synthesis same-tab near-duplicate guard. Two outlets can cover one event with
# different headlines that conservative clustering won't merge; their BULLETS give it
# away. We compare the content bag (headline + bullets) and drop a later story only when
# it both shares many tokens AND is largely contained in a kept one (calibrated: true
# twins land ~0.31 containment / 19 shared, distinct-but-related stories stay <0.30).
_DSTOP = set(("the a an and or of to in on for with from at by as is are was were be new "
              "amid over into than then out up its it also more most this that these those "
              "wine wines winery grape grapes vintage bottle producers producer region regions").split())
_DTOKEN = re.compile(r"[a-z][a-z0-9'-]{3,}")
NEARDUP_OVERLAP = 12
NEARDUP_CONTAIN = 0.30
def _content_bag(row):
    text = (row.get("head", "") + " " + " ".join(row.get("takeaways", []))).lower()
    return set(t for t in _DTOKEN.findall(text) if t not in _DSTOP)
def _is_near_dup(bag, kept_bags):
    for kb in kept_bags:
        ov = len(bag & kb)
        if ov >= NEARDUP_OVERLAP and ov / max(1, min(len(bag), len(kb))) >= NEARDUP_CONTAIN:
            return True
    return False

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
        if tab == "NEWSLETTERS":
            # single independent piece: per-article bullets, keep their headline + link
            for row in rows:
                body = fetch_body(row.get("url", ""))
                if len(body) < 200:
                    body = row.get("summ", "")
                row["takeaways"] = call_haiku(key, row.get("head", ""), row.get("source", ""), body)
                total += 1
                print(f"  {row.get('source','')}: {row.get('head','')[:44]} -> {len(row['takeaways'])} bullets")
            continue
        # news topic: synthesize ONE original brief per cluster of URLs, keeping the
        # first KEEP_PER good ones (spares cover dropped promos/dupes without backfill)
        KEEP_PER = 5
        kept, kept_bags = [], []
        for row in rows:
            if len(kept) >= KEEP_PER:
                break
            body = combined_body(row.get("urls", []), row.get("summ", ""))
            head, tk = synthesize(key, row.get("head", ""), body)
            if head:
                row["head"] = head          # our headline replaces the seeded one
            row["takeaways"] = tk
            total += 1
            n_src = len(row.get("sources", []))
            if not tk:
                # no real facts -> no original brief; drop rather than show a junk excerpt
                print(f"  [{n_src} src] {row.get('head','')[:44]} -> 0 bullets (dropped)")
                continue
            bag = _content_bag(row)
            if _is_near_dup(bag, kept_bags):
                print(f"  [{n_src} src] {row.get('head','')[:44]} -> near-dup (dropped)")
                continue
            kept.append(row); kept_bags.append(bag)
            print(f"  [{n_src} src] {row.get('head','')[:44]} -> {len(tk)} bullets")
        d["items"][tab] = kept
    json.dump(d, open(path, "w"), indent=2, ensure_ascii=False)
    print(f"Enriched {total} stories.")
    return True

if __name__ == "__main__":
    enrich()
