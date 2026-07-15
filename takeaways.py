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
- Each bullet: one sentence, 25 words or fewer, plain and factual. No marketing, no "the article says", no fluff.
- Neutral, information-dense. Lead with the concrete fact (who/what/number). No two bullets should repeat the same fact.
- NAME the people, producers, estates and regions involved. Never write that the author "explores", "examines" or "reflects on" a subject: say what they actually found or claimed. No bullet may merely restate the headline.

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
    return _clean_bullets(data.get("takeaways", []), title)

# reject bullets that talk about the article/source instead of the wine facts
_META = ["paywall", "subscriber", "not provided", "cannot be extracted", "editorial standard",
         "metadata", "source material", "full article", "full text", "the article", "this article",
         "the source", "the piece", "the post", "without the full", "no substantive", "the excerpt",
         "insufficient", "unable to"]
def is_meta(b):
    low = b.lower()
    return any(p in low for p in _META)

# News cards carry no outbound link, so a brief is the whole story a reader ever gets.
# A bullet saying someone "explores"/"focuses on" a subject, with no fact attached, is
# ABOUTNESS: it describes an article instead of reporting it, and leaves the reader with
# nothing (this is what produced "MacNeil examines prestige and pricing tensions", a card
# nobody could understand). Only reject when there's no concrete anchor, so real reporting
# like "Neill rejected the label, arguing it diminished the work" survives.
_ABOUT = re.compile(r"\b(?:explores?|examines?|discusses?|delves?|considers?|reflects? on|"
                    r"focuses? on|centers? on|centres? on|looks? at|highlights?|touches? on|"
                    r"is about|weighs? in|muses?)\b", re.I)
_ANCHOR = re.compile(r"\d|[$£€%]|\bper cent\b|\bpercent\b", re.I)
def is_vague(b):
    return bool(_ABOUT.search(b)) and not _ANCHOR.search(b)

# a bullet whose every distinctive word already appears in the headline adds nothing
_ECHO_CONTAIN = 0.75
def is_echo(b, head):
    if not head:
        return False
    hb = set(t for t in _DTOKEN.findall(head.lower()) if t not in _DSTOP)
    bb = set(t for t in _DTOKEN.findall(b.lower()) if t not in _DSTOP)
    if not bb or not hb:
        return False
    return len(bb & hb) / len(bb) >= _ECHO_CONTAIN

# ---- synthesis: our own headline + bullets from the COMBINED coverage ---------
SYNTH_PROMPT = """You are the editor of Winefeed, an independent wine-news desk. One or more outlets have covered the same story; their reporting is combined below.
Write Winefeed's OWN brief on this story.

Return STRICT JSON only: {"headline": "...", "takeaways": ["...", "..."]}

headline: an original, specific headline IN YOUR OWN WORDS. Under 12 words, concrete (who/what), no clickbait, no outlet names, no "Winefeed".
takeaways: 4-5 KEY TAKEAWAY bullets a reader can skim to know the story.

THE BRIEF MUST STAND ALONE. The reader cannot click through to any article — your bullets are the entire story they will ever see. Someone who knows nothing about this must finish the bullets understanding what happened, who it happened to, and why it matters. Assume no prior context.

LENGTH IS A HARD LIMIT: each bullet MUST be one sentence of 25 words or fewer. This is not in tension with being specific — it is the skill. Cut the throat-clearing, not the facts. A bullet that runs long is rejected outright and its facts are lost, so tighten it rather than let it run.

BULLET 1 IS THE SETUP. Before any detail, say what this actually is: the occasion, the event, the survey, the announcement, and who is involved. A reader must never meet a name, a list or a number before they know what they are reading about. If the story is "fifteen sommeliers name Bordeaux worth the price", bullet 1 says who the sommeliers are and what they were asked; the picks come after.

IDENTIFY EVERY PERSON AND GROUP ON FIRST MENTION: give the role and the place. "Julie Dalton, master sommelier at Stella's Wine Bar in Houston" — never a bare surname, never "a sommelier", never "experts". If the source doesn't say who someone is, describe them only as far as it does.

Study these, they are the whole job:
  GOOD (14 words, names + number): "Sussex vineyard founded by Peter Hall in 1974 listed at £4 million guide price."
  GOOD (setup bullet, 15 words): "Fifteen US restaurant sommeliers were asked which three-figure Bordeaux bottles justify their price."
  BAD, too vague (says nothing): "The piece explores the estate's long history and its place in English wine."
  BAD, no context (a pick with no frame — we never learn who chose it, or why the list exists): "Château Palmer offers emotional complexity with violet and graphite notes that justify premium pricing."
  BAD, too long (34 words, same facts as the first GOOD but bloated): "Breaky Bottom Vineyard near Lewes in Sussex, which was founded by Peter Hall back in 1974, has now been listed for sale for the first time at a guide price of £4 million."

Hard rules:
- NAME the people, producers, estates, companies and regions, and give the numbers and dates. A brief without names is a failed brief. Fit them inside 25 words.
- Never write that someone "explores", "examines", "discusses", "highlights" or "reflects on" a subject. That describes an article instead of reporting it. Say what they actually found, claimed, or did. If the source only muses and states no findings, return {"headline": "", "takeaways": []}.
- Use ONLY facts explicitly stated in the source material. Never invent or infer numbers, names, dates, quotes, or claims.
- Write facts in your OWN words. Do NOT copy sentences from the sources.
- If several outlets agree on a fact, state it once. If they conflict, keep the specific/attributed version.
- Lead each bullet with the concrete fact. No two bullets repeat the same fact. No bullet may merely restate the headline.
- NEVER write ABOUT the articles, outlets, paywalls, or missing content. Output wine facts or nothing.
- NEVER use an em-dash or an en-dash as punctuation. Use a comma, a full stop, or brackets. A dash between two numbers in a range (2003-2004) is fine and is the only dash allowed.
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

# A backstop against a model dumping a paragraph, NOT a style rule -- length discipline
# belongs in the prompt (which asks for 25 words), because dropping a bullet here loses
# the fact entirely. Twice now a tighter cap silently ate the setup bullet and left a
# brief opening mid-story with no context, which is the exact failure it should prevent.
MAX_BULLET = 260

# The em-dash parenthetical is the clearest tell that a machine wrote the line, and
# these bullets are republished to the site, the daily email and social. The prompt
# now forbids them; this is the backstop for when it does it anyway.
#
# An en-dash BETWEEN DIGITS is a correct number range (2003-2004) and must survive --
# a blanket strip would mangle every vintage span and drought year we publish. Only a
# dash used as PUNCTUATION becomes a comma.
_EN_RANGE = re.compile(r"(?<=\d)\s*[–—]\s*(?=\d)")
_DASH_PUNCT = re.compile(r"\s*[—–]\s*")
_DUP_PUNCT = re.compile(r",\s*([,.;:])")

def _dedash(t):
    t = _EN_RANGE.sub("\x00", t)            # park the legitimate ranges
    t = _DASH_PUNCT.sub(", ", t)            # everything else reads as a comma
    t = _DUP_PUNCT.sub(r"\1", t)            # ", ." -> "."
    return t.replace("\x00", "–")      # restore the ranges as en-dashes

def _clean_bullets(raw, head=""):
    outs = []
    for t in (raw or [])[:5]:
        t = re.sub(r"\s+", " ", str(t)).strip(" .–-").strip()
        t = _dedash(t)
        if len(t) < 8:
            continue
        if len(t) > MAX_BULLET:
            # Loud on purpose. A silent length drop once cost us most of a day's bullets:
            # a prompt tweak pushed the model to 30-word bullets and they all vanished here.
            print(f"    ! bullet over {MAX_BULLET} chars ({len(t)}), dropped: {t[:60]}...", file=sys.stderr)
            continue
        if is_meta(t) or is_vague(t) or is_echo(t, head):
            continue
        outs.append(t + ".")
    return outs

def synthesize(key, title, body):
    """Return (headline, takeaways). headline '' if the model wrote nothing usable."""
    data = _call(key, SYNTH_PROMPT % {"title": title, "body": body})
    if not data:
        return "", []
    head = re.sub(r"\s+", " ", str(data.get("headline", ""))).strip().strip('"').strip()
    head = _dedash(head)
    if is_meta(head) or len(head) < 8:
        head = ""
    return head, _clean_bullets(data.get("takeaways", []), head or title)

# A brief is only as good as the reporting under it. Below this much real article text
# the model has nothing to summarize and pads by rephrasing the headline, so we would
# rather run one story fewer than run one nobody can understand.
MIN_BODY = 1000
MIN_BULLETS = 3

def combined_body(urls):
    """Fetch + concatenate every cluster member's body (archive.ph fallback).

    Deliberately NO excerpt fallback: an RSS blurb is 2 sentences, and asking for 4-5
    takeaways off it yields content-free aboutness. Callers drop the story instead."""
    parts = []
    for u in urls:
        b = fetch_body(u)
        if len(b) >= 200:
            parts.append(b)
    return "\n\n---\n\n".join(parts)[:12000]

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
        # news topic: synthesize ONE original brief per cluster of URLs. Every candidate
        # update.py hands us gets a shot; how many survive is decided by the quality gates
        # below, not by a fixed quota -- a rich news day publishes more, a thin one fewer.
        kept, kept_bags = [], []
        for row in rows:
            n_src = len(row.get("sources", []))
            body = combined_body(row.get("urls", []))
            if len(body) < MIN_BODY:
                # nothing real to summarize (paywalled/JS/press-release stub). Writing a
                # brief off the RSS blurb is how vague, nameless cards get made.
                print(f"  [{n_src} src] {row.get('head','')[:44]} -> no article body (dropped)")
                continue
            head, tk = synthesize(key, row.get("head", ""), body)
            if head:
                row["head"] = head          # our headline replaces the seeded one
            row["takeaways"] = tk
            total += 1
            if len(tk) < MIN_BULLETS:
                # too few real facts survived -> no brief worth publishing
                print(f"  [{n_src} src] {row.get('head','')[:44]} -> {len(tk)} bullets (dropped)")
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
