#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
winefeed auto-updater
=====================
Pulls live RSS from reputable wine outlets + independent Substacks. For the news
topics (MARKET/CULTURE/SCIENCE) it CLUSTERS the day's coverage into distinct
stories and hands each cluster to takeaways.py, which writes ONE original,
fact-grounded brief per event (our headline + key-takeaway bullets, credited to
the outlets that covered it, but not linked). NEWSLETTERS keep their link + byline.
Writes feed_data.json, then runs build.py to regenerate index.html.

Run:  python3 update.py         (then deploy index.html)
Fully self-contained: only stdlib + curl. No API key, no external packages.
"""
import subprocess, re, html, json, os, sys, datetime
from email.utils import parsedate_to_datetime

HERE = os.path.dirname(os.path.abspath(__file__))
FRESH_DAYS = 30          # pool: ignore anything older than this
NEWS_FRESH_DAYS = 90     # newsletters publish less often, allow a longer window
# How many stories a topic can publish is decided by QUALITY, not a quota: these are the
# candidates handed to the synthesis pass, which drops anything it can't ground properly
# (see takeaways.MIN_BODY/MIN_BULLETS). A rich news day runs long, a thin one runs short.
CAND_PER_TOPIC = 12
MAX_NEWSLETTERS = 10

# The item must read as WINE. Our pool covers all drinks, so this gate does real work --
# and it has to match on WORD boundaries: a plain substring test let a tequila story lead
# the brief because it name-dropped an investment fund called "WineFi".
_WINE_STEMS = ["winer", "winemak", "viticultur", "vinicultur", "oenolog", "enolog", "vinif",
               "sommelier", "vigneron"]
_WINE_WORDS = ["wine", "wines", "vineyard", "vineyards", "grape", "grapes", "vintage",
               "vintages", "cellar", "cellars", "appellation", "appellations", "terroir",
               "champagne", "prosecco", "cava", "rose", "rosé", "riesling", "cabernet",
               "chardonnay", "sauvignon", "pinot", "merlot", "syrah", "shiraz", "grenache",
               "tempranillo", "nebbiolo", "sangiovese", "bordeaux", "burgundy", "barolo",
               "rioja", "napa", "sonoma", "chianti", "mosel", "sherry", "madeira", "chablis",
               "amarone", "douro", "porto", "vino", "vin", "wein", "varietal", "varietals",
               "harvest", "en primeur", "grand cru", "premier cru", "somm"]
WINE_RE = re.compile(r"\b(?:" + "|".join([s + r"\w*" for s in _WINE_STEMS] + _WINE_WORDS) + r")\b", re.I)

# ...and a story dominated by another drink category is not ours, however many times the
# word "wine" happens to appear in it.
_OFF_STEMS = ["whisk", "brewer", "brewing", "distiller"]
_OFF_WORDS = ["tequila", "mezcal", "agave", "bourbon", "scotch", "rum", "gin", "vodka",
              "beer", "beers", "ale", "lager", "cider", "coffee", "cocktail", "cocktails",
              "spirits", "seltzer", "kombucha", "absinthe", "liqueur", "liqueurs", "soju"]
OFF_RE = re.compile(r"\b(?:" + "|".join([s + r"\w*" for s in _OFF_STEMS] + _OFF_WORDS)
                    + r"|sake\b(?!\s+of))\b", re.I)   # "sake" the drink, not "for the sake of"

def _score_item(rx, item):
    """The headline carries the subject, so it counts double."""
    return 2 * len(rx.findall(item.get("title", ""))) + len(rx.findall(item.get("summary", "")))

def is_wine(item):
    """Reads as a wine story: real wine signal, and not dominated by another drink."""
    return _score_item(WINE_RE, item) > 0 and _score_item(WINE_RE, item) >= _score_item(OFF_RE, item)

def is_offtopic(item):
    """Lighter gate for the newsletter writers we already trust: we don't demand wine
    signal, we just veto a post plainly about something else (wineanorak's coffee
    plantation video led the tab)."""
    return _score_item(OFF_RE, item) > _score_item(WINE_RE, item)

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
    ("Grape Collective",      "https://grapecollective.com/rss"),
    ("The Wine Economist",    "https://wineeconomist.com/feed/"),
    ("Dr Vino",               "https://www.drvino.com/feed/"),
]
# Independent wine writers / Substacks -> NEWSLETTERS tab (source, url, author).
# One post per writer per day, freshest first, capped at MAX_NEWSLETTERS -- so a deep bench
# is a feature: it rotates voices and regions and covers for whoever is quiet that week.
# Every feed here was health-tested against this engine's real requirements (valid XML,
# dated items, a genuine summary that isn't just the title echoed, fresh within 90 days).
# Do NOT re-add without a working feed: The Buyer, Wine Spectator, Club Oenologique,
# Meininger's, Harpers, Wine Business, Wine-Searcher, Just Drinks, Terroirist, Wine For
# Normal People, Winemag SA (malformed XML), Hawk Wakawaka / Steve Heimoff / The Wine
# Detective / Naturally Wine (all stale), Andrew Jefford + Levi Dalton (no Substack).
NEWSLETTERS = [
    ("Everyday Drinking",   "https://www.everydaydrinking.com/feed",        "Jason Wilson"),
    ("The Feiring Line",    "https://feiring.substack.com/feed",            "Alice Feiring"),
    ("The Morning Claret",  "https://themorningclaret.com/feed",            "Simon J. Woolf"),
    ("wineanorak",          "https://wineanorak.com/feed/",                 "Jamie Goode"),
    ("Not Drinking Poison", "https://notdrinkingpoison.substack.com/feed",  "Aaron Ayscough"),
    ("Jancis Robinson",     "https://www.jancisrobinson.com/articles/feed", "Jancis Robinson"),
    ("Tim Atkin",           "https://www.timatkin.com/feed/",               "Tim Atkin MW"),
    ("Vinography",          "https://www.vinography.com/index.xml",         "Alder Yarrow"),
    ("SpitBucket",          "https://spitbucket.net/feed/",                 "Amber LeBeau"),
    ("Drinking Culture",    "https://henryjeffreys.substack.com/feed",      "Henry Jeffreys"),
    ("Fermentation",        "https://tomwark.substack.com/feed",            "Tom Wark"),
    ("Drinks Insider",      "https://www.drinksinsider.com/feed",           "Felicity Carter"),
    ("A View from My Table","https://aviewfrommytable.substack.com/feed",   "Andy Neather"),
    ("Down The Rabbit Hole","https://georgenordahl.substack.com/feed",      "George Nordahl"),
    ("Terroir Champagne",   "https://terroirchampagne.substack.com/feed",   "Caroline Henry"),
    ("Eat This, Drink That","https://fionabeckett.substack.com/feed",       "Fiona Beckett"),
    ("The Burnt Cream",     "https://emmabentleyvino.substack.com/feed",    "Emma Bentley"),
    ("Dave McIntyre",       "https://dmwineline.substack.com/feed",         "Dave McIntyre"),
    ("Maker's Table",       "https://www.makerstable.com/feed",             "Meg Maker"),
    ("Wineterroirs",        "https://wineterroirs.substack.com/feed",       "Bertrand Celce"),
    ("Italy Matters",       "https://robertcamuto.substack.com/feed",       "Robert Camuto"),
    ("Be Wine Curious",     "https://newsletter.hudin.com/feed",            "Miquel Hudin"),
    ("Grape Wall of China", "https://www.grapewallofchina.com/feed",        "Jim Boyce"),
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

def strip_boiler(t):
    t = re.sub(r"(?i)^\s*website:\s*\S+\s*", "", t)        # wineanorak "Website: <url> ..."
    t = re.sub(r"^\s*https?://\S+\s*", "", t)              # any other leading bare URL
    # cut common RSS/WordPress footer boilerplate (always trailing)
    t = re.sub(r"(?is)\bthe post\b.*$", "", t)              # "The post X appeared first on Y."
    t = re.sub(r"(?is)\bread more\b.*$", "", t)             # "... Read More ..."
    t = re.sub(r"(?is)\bcontinue reading\b.*$", "", t)
    t = re.sub(r"(?is)\bappeared first on\b.*$", "", t)
    t = re.sub(r"(?is)\bthis (article|post) (first )?appeared\b.*$", "", t)
    t = re.sub(r"(?is)\b(related|read also|see also|read next)\s*:.*$", "", t)
    t = re.sub(r"\[[^\]]*\]\s*$", "", t)                    # trailing [...]
    return t.strip(" .–-\t\n…")

def summarize(desc, title):
    txt = strip_boiler(clean(desc))
    if not txt or len(txt) < 40:
        return ""          # no real description -> item gets filtered out (never echo the title)
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

_ALNUM = re.compile(r"[^a-z0-9]+")
def usable(item):
    """True only if there's a genuine summary that isn't just the headline echoed."""
    s, title = item.get("summary", ""), item.get("title", "")
    if len(s) < 60:
        return False
    low = s.lower()
    if "appeared first on" in low or "read more" in low or low.startswith("the post"):
        return False
    ns, nt = _ALNUM.sub("", low), _ALNUM.sub("", title.lower())
    if not ns or ns == nt:
        return False
    if ns.startswith(nt) and (len(ns) - len(nt)) < 40:   # title + trivial tail
        return False
    return True

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

# On ties, the narrower topics win so CULTURE doesn't swallow science/market stories.
_TOPIC_PRIORITY = ["SCIENCE", "MARKET", "CULTURE"]
def bucket_text(text):
    """Best topic for a blob of text; CULTURE is the catch-all when nothing scores."""
    scores = {t: score(text, KW[t]) for t in TOPICS}
    best = max(_TOPIC_PRIORITY, key=lambda t: (scores[t], -_TOPIC_PRIORITY.index(t)))
    return best if scores[best] > 0 else "CULTURE"

# ---- cluster same-event coverage --------------------------------------------
# Two articles are the same story if their distinctive tokens overlap enough.
# Generic wine words are stripped so overlap means shared NAMES/PLACES/EVENTS.
_STOP = set((
    "the a an and or of to in on for with from at by is are was were be been has have had "
    "this that these those will would can could it its as new more most amid over into than "
    "then out up down off about after before your you our their his her they them we us not "
    "how why what when who which says said report reports year years day days week weeks "
    "wine wines winery wineries vineyard vineyards grape grapes vintage bottle bottles drink "
    "drinks industry market world first best top says "
    # generic headline verbs/nouns that otherwise cause coincidental same-story merges
    "takes take helm joins join launches launch names named appointed reveals reveal "
    "announces announced wins win sells sold offers offer brings bring make makes making "
    "things ways reasons guide know meet sees see gets get set launch back adds add").split())
_TOKEN = re.compile(r"[a-z][a-z0-9'&-]{3,}")
def keytokens(item):
    # TITLE ONLY, on purpose: summaries are broad and cause false merges (a Sam Neill
    # obit whose blurb mentions "Pinot/Otago" would swallow every Pinot article).
    # Headlines are focused, so shared headline tokens are a far better same-story signal.
    toks = _TOKEN.findall(item["title"].lower())
    return set(t for t in toks if t not in _STOP)

def cluster_items(items, min_shared=3):
    """Greedy, seed-anchored clustering, intentionally CONSERVATIVE. An article joins
    an existing story only if it shares >= min_shared distinctive HEADLINE tokens with
    that story's lead article. Token overlap is a weak proxy for "same event", so we
    set the bar high: most stories stay singletons (one clean original brief, one
    credited outlet) and only genuine near-duplicate headlines merge. This avoids
    fusing unrelated stories, which would manufacture false associations in synthesis.
    `items` is expected freshest-first, so the lead of each cluster is its newest."""
    clusters = []   # each: {"seed": set(tokens), "members": [item, ...]}
    for it in items:
        toks = keytokens(it)
        for c in clusters:
            if len(toks & c["seed"]) >= min_shared:
                c["members"].append(it)
                break
        else:
            clusters.append({"seed": toks, "members": [it]})
    return [c["members"] for c in clusters]

def cluster_topic(members):
    return bucket_text(" ".join(m["title"] + " " + m["summary"] for m in members))

def dedupe_sources(members):
    seen, out = set(), []
    for m in members:
        if m["source"] not in seen:
            seen.add(m["source"]); out.append(m["source"])
    return out

def main():
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=FRESH_DAYS)

    print("Fetching pool feeds...")
    pool = []
    for src, url in POOL:
        items = parse(fetch(url), src)
        print(f"  {src}: {len(items)} items")
        pool += items

    # keep fresh + dated + wine-relevant + with a real summary, newest first
    pool = [i for i in pool if i["date"] and i["date"] >= cutoff and is_wine(i) and usable(i)]
    pool.sort(key=lambda i: i["date"], reverse=True)

    # cluster the day's coverage into distinct STORIES, then bucket each to a topic.
    # winefeed no longer maps one article -> one card; it writes ONE original brief
    # per real event, crediting whichever outlets covered it.
    tab_clusters = {t: [] for t in TOPICS}
    for members in cluster_items(pool):
        members.sort(key=lambda i: i["date"], reverse=True)   # freshest member leads
        tab_clusters[cluster_topic(members)].append(members)
    # editorial order within a topic: freshest first, then better-covered stories
    def freshness(m):
        return (m[0]["date"], len(m))
    for t in TOPICS:
        tab_clusters[t].sort(key=freshness, reverse=True)

    # Hand the synthesis pass a deep candidate list and let it publish everything it can
    # actually ground. There is no fixed quota: it drops what it can't report properly,
    # so the day's story count reflects the day's news rather than a magic number.
    chosen = {t: tab_clusters[t][:CAND_PER_TOPIC] for t in TOPICS}
    leftover = [m for t in TOPICS for m in tab_clusters[t][CAND_PER_TOPIC:]]
    leftover.sort(key=freshness, reverse=True)
    # a genuinely thin topic (esp. SCIENCE) should still show fresh news, never blank
    used_urls = {m[0]["url"] for t in TOPICS for m in chosen[t]}
    for t in TOPICS:
        if chosen[t]:
            continue
        # fill an empty tab with the most topically-relevant leftover, then freshness
        pref = sorted(leftover,
                      key=lambda m: (score(m[0]["title"] + " " + m[0]["summary"], KW[t]),
                                     m[0]["date"]),
                      reverse=True)
        for m in pref:
            if m[0]["url"] not in used_urls:
                chosen[t].append(m)
                used_urls.add(m[0]["url"])
                leftover.remove(m)
                break

    def story_from(members):
        # the synthesis pass (takeaways.py) rewrites `head` and fills `takeaways`
        # from the COMBINED bodies of `urls`; the seeds keep the card valid if it can't.
        return {
            "head":      members[0]["title"],
            "date":      members[0]["date"].isoformat(),
            "sources":   dedupe_sources(members),      # tiny credit line, not links
            "summ":      members[0]["summary"],         # fallback body if no synthesis
            "urls":      [m["url"] for m in members][:4],  # internal grounding only
            "takeaways": [],
        }

    tabs = {t: [story_from(m) for m in chosen[t]] for t in TOPICS}

    print("Fetching newsletters...")
    news = []
    for src, url, author in NEWSLETTERS:
        items = parse(fetch(url), src)
        print(f"  {src}: {len(items)} items")
        for it in items:
            it["author"] = author
            news.append(it)
    news_cutoff = today - datetime.timedelta(days=NEWS_FRESH_DAYS)
    # a mis-dated feed shouldn't be able to pin itself to the top of the tab forever
    horizon = today + datetime.timedelta(days=2)
    news = [i for i in news if i["date"] and news_cutoff <= i["date"] <= horizon
            and usable(i) and not is_offtopic(i)]
    news.sort(key=lambda i: i["date"], reverse=True)
    # one post per writer, freshest first — newsletters keep their link + byline
    picked, seen_src = [], set()
    for it in news:
        if it["source"] not in seen_src:
            picked.append({
                "source": it["source"], "url": it["url"], "date": it["date"].isoformat(),
                "head": it["title"], "summ": it["summary"],
                "author": it.get("author", ""), "takeaways": [],
            })
            seen_src.add(it["source"])
        if len(picked) >= MAX_NEWSLETTERS:
            break
    tabs["NEWSLETTERS"] = picked

    # ---- assemble feed_data.json --------------------------------------------
    order = ["MARKET", "CULTURE", "SCIENCE", "NEWSLETTERS"]
    out = {"date": today.isoformat(), "items": {t: tabs.get(t, []) for t in order}}
    thin = []
    for topic in order:
        n = len(out["items"][topic])
        tag = "" if topic == "NEWSLETTERS" else " candidates"
        print(f"{topic}: {n}{tag}")
        if n == 0:
            thin.append(topic)                 # empty is the only real failure now
    ok = not thin

    with open(os.path.join(HERE, "feed_data.json"), "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("Wrote feed_data.json")

    # ---- original key-takeaways (LLM), grounded; excerpt fallback if no key --
    try:
        import takeaways
        takeaways.enrich(os.path.join(HERE, "feed_data.json"))
    except Exception as e:
        print(f"takeaways step skipped: {e}", file=sys.stderr)

    # ---- regenerate the site -------------------------------------------------
    r = subprocess.run([sys.executable, "build.py"], cwd=HERE)
    if r.returncode != 0:
        print("build.py failed", file=sys.stderr)
        sys.exit(1)
    print("Rebuilt index.html")
    if not ok:
        print(f"WARNING: no fresh stories for: {', '.join(thin)}.", file=sys.stderr)

if __name__ == "__main__":
    main()
