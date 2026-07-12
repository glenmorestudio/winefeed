#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
winefeed auto-updater
=====================
Pulls live RSS from reputable wine outlets + independent Substacks, buckets items
into the four winefeed topics, writes a 2-3 sentence summary taken from each
outlet's OWN excerpt (never invented), keeps the 5 freshest per topic, writes
feed_data.json, then runs build.py to regenerate index.html.

Run:  python3 update.py         (then deploy index.html)
Fully self-contained: only stdlib + curl. No API key, no external packages.
"""
import subprocess, re, html, json, os, sys, datetime
from email.utils import parsedate_to_datetime

HERE = os.path.dirname(os.path.abspath(__file__))
FRESH_DAYS = 30          # pool: ignore anything older than this
NEWS_FRESH_DAYS = 90     # newsletters publish less often, allow a longer window
PER_TOPIC = 5

# item must read as WINE (pool feeds like VinePair/PUNCH also cover spirits/beer)
WINE_TERMS = ["wine", "winer", "vineyard", "vigneron", "winemak", "grape", "vintage",
              "sommelier", "cellar", "appellation", "terroir", "champagne", "prosecco",
              "cava", "rose", "rosé", "riesling", "cabernet", "chardonnay", "sauvignon",
              "pinot", "merlot", "syrah", "shiraz", "grenache", "tempranillo", "nebbiolo",
              "sangiovese", "bordeaux", "burgundy", "barolo", "rioja", "napa", "sonoma",
              "chianti", "mosel", "port ", "sherry", "madeira", "chablis", "amarone",
              "grand cru", "en primeur", "vino", "vin ", "wein"]
def is_wine(item):
    t = (item["title"] + " " + item["summary"]).lower()
    return any(w in t for w in WINE_TERMS)

# ---- feeds -------------------------------------------------------------------
# General reputable pool -> keyword-bucketed into MARKET / CULTURE / SCIENCE.
POOL = [
    ("The Drinks Business",   "https://www.thedrinksbusiness.com/feed/"),
    ("Wine Enthusiast",       "https://www.wineenthusiast.com/feed/"),
    ("Wine Industry Advisor", "https://wineindustryadvisor.com/feed/"),
    ("Vino Joy News",         "https://vino-joy.com/feed/"),
    ("SevenFifty Daily",      "https://daily.sevenfifty.com/feed/"),
    ("Decanter",              "https://www.decanter.com/feed/"),
    ("The Buyer",             "https://www.the-buyer.net/feed/"),
    ("VinePair",              "https://vinepair.com/feed/"),
    ("PUNCH",                 "https://punchdrink.com/feed/"),
    ("Wine Spectator",        "https://www.winespectator.com/rss/news"),
    ("Club Oenologique",      "https://cluboenologique.com/feed/"),
]
# Independent wine writers / Substacks -> NEWSLETTERS tab (source, url, author).
NEWSLETTERS = [
    ("Everyday Drinking",   "https://www.everydaydrinking.com/feed",        "Jason Wilson"),
    ("The Feiring Line",    "https://feiring.substack.com/feed",            "Alice Feiring"),
    ("The Morning Claret",  "https://themorningclaret.com/feed",            "Simon J. Woolf"),
    ("wineanorak",          "https://wineanorak.com/feed/",                 "Jamie Goode"),
    ("Not Drinking Poison", "https://notdrinkingpoison.substack.com/feed",  "Aaron Ayscough"),
    ("Jancis Robinson",     "https://www.jancisrobinson.com/articles/feed", "Jancis Robinson"),
]

# ---- keyword buckets for the pool -------------------------------------------
KW = {
    "SCIENCE": ["climate", "warming", "heatwave", "drought", "wildfire", "research",
                "study", "scientist", "sustainab", "organic", "regenerative", "carbon",
                "emission", "disease", "mildew", "yeast", "soil", "health", "cancer",
                "alcohol consumption", "biodivers", "viticultur", "rootstock"],
    "MARKET":  ["tariff", "price", "sales", "market", "export", "import", "trade",
                "acquisition", "merger", "auction", "invest", "revenue", "profit",
                "dtc", "retail", "distributor", "economy", "consumption", "volume",
                "shipment", "duty", "e-commerce", "financial", "earnings", "en primeur"],
    "CULTURE": ["restaurant", "sommelier", "bar", "chef", "wine list", "award",
                "trend", "cocktail", "festival", "pairing", "appointed", "named",
                "hospitality", "menu", "tasting", "somm", "personality", "influencer",
                "natural wine", "bottle shop", "gen z"],
}
TOPICS = ["MARKET", "CULTURE", "SCIENCE"]
BLURBS = {
    "MARKET":      "Trade, prices, tariffs, and the business of wine.",
    "CULTURE":     "People, restaurants, and how the world drinks.",
    "SCIENCE":     "Climate, viticulture, sustainability, and health.",
    "NEWSLETTERS": "Dispatches from independent wine writers and their Substacks.",
}

# ---- fetch / parse -----------------------------------------------------------
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"

def fetch(url):
    try:
        r = subprocess.run(["curl", "-sL", "--max-time", "25", "-A", UA, url],
                           capture_output=True, timeout=40)
        return r.stdout.decode("utf-8", "replace")
    except Exception as e:
        print(f"  ! fetch failed {url}: {e}", file=sys.stderr)
        return ""

TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")
CDATA = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.S)

def clean(t):
    if not t:
        return ""
    m = CDATA.search(t)
    if m:
        t = m.group(1)
    t = TAG.sub(" ", t)
    t = html.unescape(t)
    t = t.replace("—", ", ").replace("–", "-")
    return WS.sub(" ", t).strip()

def summarize(desc, title):
    txt = clean(desc)
    if not txt or len(txt) < 40:
        return clean(title)
    # first 2-3 sentences, capped
    out, n = "", 0
    for sent in re.split(r"(?<=[.!?])\s+", txt):
        if not sent:
            continue
        out = (out + " " + sent).strip()
        n += 1
        if len(out) > 300 or n >= 3:
            break
    if len(out) > 340:
        out = out[:330].rsplit(" ", 1)[0] + "..."
    return out

def parse_date(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return parsedate_to_datetime(s).date()
    except Exception:
        pass
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        return None

# drop low-editorial filler (promos, roundups, podcasts, sponsored)
SKIP = ["afternoon brief", "call for entries", " masters 202", "podcast", "webinar",
        "sponsored", "advertorial", "shop the", "\U0001F4FA", "\U0001F3A7", "giveaway",
        "subscribe", "newsletter round", "week in review", "deals of the"]
def is_filler(title):
    t = title.lower()
    return any(s in t for s in SKIP)

def field(block, *tags):
    for tag in tags:
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", block, re.S | re.I)
        if m:
            return m.group(1)
    return ""

def atom_link(block):
    m = re.search(r'<link[^>]*href="([^"]+)"[^>]*/?>', block, re.I)
    return m.group(1) if m else ""

def parse(xmlt, source):
    items = []
    blocks = re.findall(r"<item\b.*?</item>", xmlt, re.S | re.I)
    atom = False
    if not blocks:
        blocks = re.findall(r"<entry\b.*?</entry>", xmlt, re.S | re.I)
        atom = True
    for b in blocks:
        title = clean(field(b, "title"))
        link = clean(field(b, "link")) if not atom else atom_link(b)
        desc = field(b, "description", "summary", "content:encoded", "content")
        date = parse_date(field(b, "pubDate", "published", "updated", "dc:date"))
        if not title or not link or is_filler(title):
            continue
        items.append({"source": source, "url": link, "title": title,
                      "summary": summarize(desc, title), "date": date})
    return items

# ---- categorize --------------------------------------------------------------
def score(text, words):
    t = text.lower()
    return sum(t.count(w) for w in words)

def bucket(item):
    text = item["title"] + " " + item["summary"]
    best, bs = None, 0
    for topic in TOPICS:
        s = score(text, KW[topic])
        if s > bs:
            best, bs = topic, s
    return best  # may be None

def main():
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=FRESH_DAYS)

    print("Fetching pool feeds...")
    pool = []
    for src, url in POOL:
        items = parse(fetch(url), src)
        print(f"  {src}: {len(items)} items")
        pool += items

    # keep fresh + dated + wine-relevant, newest first
    pool = [i for i in pool if i["date"] and i["date"] >= cutoff and is_wine(i)]
    pool.sort(key=lambda i: i["date"], reverse=True)

    used = set()                 # urls used anywhere (no article twice)
    tabs = {t: [] for t in TOPICS}
    used_src = {t: set() for t in TOPICS}   # sources used per tab (one each)

    def take(topic, it):
        tabs[topic].append(it)
        used.add(it["url"])
        used_src[topic].add(it["source"])

    # primary: keyword bucket, one source per tab
    for it in pool:
        b = bucket(it)
        if b and len(tabs[b]) < PER_TOPIC and it["url"] not in used and it["source"] not in used_src[b]:
            take(b, it)
    # backfill short topics from freshest remaining items, still one source per tab
    for topic in TOPICS:
        if len(tabs[topic]) < PER_TOPIC:
            for it in pool:
                if it["url"] not in used and it["source"] not in used_src[topic]:
                    take(topic, it)
                    if len(tabs[topic]) >= PER_TOPIC:
                        break

    print("Fetching newsletters...")
    news = []
    for src, url, author in NEWSLETTERS:
        items = parse(fetch(url), src)
        print(f"  {src}: {len(items)} items")
        for it in items:
            it["author"] = author
            news.append(it)
    news_cutoff = today - datetime.timedelta(days=NEWS_FRESH_DAYS)
    news = [i for i in news if i["date"] and i["date"] >= news_cutoff]
    news.sort(key=lambda i: i["date"], reverse=True)
    # one post per writer, freshest first
    picked, seen_src = [], set()
    for it in news:
        if it["source"] not in seen_src:
            picked.append(it)
            seen_src.add(it["source"])
        if len(picked) >= PER_TOPIC:
            break
    tabs["NEWSLETTERS"] = picked

    # ---- assemble feed_data.json --------------------------------------------
    out = {"date": today.isoformat(), "items": {}}
    order = ["MARKET", "CULTURE", "SCIENCE", "NEWSLETTERS"]
    ok = True
    for topic in order:
        rows = []
        for it in tabs.get(topic, []):
            row = [it["source"], it["url"], it["date"].isoformat(),
                   it["title"], it["summary"]]
            if topic == "NEWSLETTERS":
                row.append(it.get("author", ""))
            rows.append(row)
        out["items"][topic] = rows
        print(f"{topic}: {len(rows)}/{PER_TOPIC}")
        if len(rows) < PER_TOPIC:
            ok = False

    with open(os.path.join(HERE, "feed_data.json"), "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("Wrote feed_data.json")

    # ---- regenerate the site -------------------------------------------------
    r = subprocess.run([sys.executable, "build.py"], cwd=HERE)
    if r.returncode != 0:
        print("build.py failed", file=sys.stderr)
        sys.exit(1)
    print("Rebuilt index.html")
    if not ok:
        print("WARNING: at least one topic had fewer than 5 fresh stories.", file=sys.stderr)

if __name__ == "__main__":
    main()
