#!/usr/bin/env python3
"""
repurpose.py -- turn the day's feed_data.json into social assets.

Two outputs, both grounded in what the engine already published:
  * X post drafts (text)          -> repurpose_out/x_drafts.json + .txt
  * carousel slides (1080x1350)   -> repurpose_out/<template>/NN.png

Nothing here invents facts. The carousel is a pure re-layout of rows that
already passed the engine's grounding gates; the X drafts are rewritten from
those same bullets by Haiku under a no-new-facts prompt (same contract as
takeaways.py, which is where the grounding rules live).

Rendering is HTML -> headless Chrome -> PNG so the slides inherit the real
design tokens from app.css instead of a hand-copied palette that drifts.
Chrome ships on ubuntu-latest too, so this can move into CI unchanged.

Usage:
  python3 repurpose.py                 # all templates, X drafts included
  python3 repurpose.py --no-x          # slides only (no API calls, no cost)
  python3 repurpose.py --template deck # one template
"""

import argparse, base64, html, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "repurpose_out")

SLIDE_W, SLIDE_H = 1080, 1350   # 4:5 -- the tallest IG allows, so most feed real estate.

CHROME = os.environ.get("CHROME_BIN") or next(
    (p for p in [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome", "/usr/bin/chromium-browser", "/usr/bin/chromium",
    ] if os.path.exists(p)), None)

TABS = ["MARKET", "CULTURE", "SCIENCE", "NEWSLETTERS"]


# ---------------------------------------------------------------- data

def load_feed():
    with open(os.path.join(HERE, "feed_data.json")) as f:
        return json.load(f)


def leads(data, per_tab=1):
    """The day's lead story per tab, in tab order. Empty tabs just drop out.

    The site RANKS wine first and keeps the rest, which is right for a 33-story
    deck you scroll. A carousel is curated: four slides, so one off-topic lead is
    a quarter of a wine brand's post. Here we SELECT the top wine story per tab
    and let the off-topic tail stay on the site where it belongs.
    """
    sys.path.insert(0, HERE)
    import update
    out = []
    for tab in TABS:
        rows = [r for r in (data["items"].get(tab) or []) if r.get("takeaways")]
        if not rows:
            continue
        winey = [r for r in rows if update.is_wine(_as_item(r))]
        out.extend((tab, r) for r in (winey or rows)[:per_tab])
    return out


def _as_item(row):
    """update.is_wine scores a raw RSS item (title/summary). Published rows use
    head/takeaways, so reshape rather than re-implement the scoring."""
    return {"title": row.get("head", ""),
            "summary": " ".join(row.get("takeaways") or []) or row.get("summ", "")}


def pretty_date(iso):
    from datetime import date
    y, m, d = (int(x) for x in iso.split("-"))
    months = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY",
              "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
    return f"{months[m-1]} {d}, {y}"


# The engine's bullets end in a period and are written for a card. On a slide the
# trailing period is noise, and an em-dash parenthetical reads as machine-written.
# En-dashes inside number ranges (2003-2004) are correct typography and stay.
EM_PAREN = re.compile(r"\s*—\s*")

def slide_text(b):
    t = b.strip().rstrip(".")
    t = EM_PAREN.sub(", ", t)
    return t


# ---------------------------------------------------------------- chrome

def shot(html_str, png_path, w=SLIDE_W, h=SLIDE_H):
    if not CHROME:
        sys.exit("no Chrome binary found; set CHROME_BIN")
    tmp = png_path + ".html"
    with open(tmp, "w") as f:
        f.write(html_str)
    subprocess.run([
        CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-sandbox", f"--window-size={w},{h}",
        f"--screenshot={png_path}", "file://" + tmp,
    ], capture_output=True, timeout=90)
    os.remove(tmp)
    if not os.path.exists(png_path):
        sys.exit(f"chrome produced no png for {png_path}")


def fonts_css():
    with open(os.path.join(HERE, "fonts.css")) as f:
        return f.read()


# Tokens lifted from app.css :root. Light theme only -- a social slide has no
# viewer preference to respond to.
TOKENS = """
  --paper:#FBFBFA; --bg:#EDEEF1; --raise:#F1F2F4; --ink:#16181D; --title:#08090C;
  --body:#64686F; --meta:#6B6F78; --faint:#A6A9B1; --line:#E6E7EA; --line-2:#DADCE0;
  --accent:#2743C9;
  --serif:'Geist',system-ui,sans-serif; --mono:'Geist Mono',ui-monospace,monospace;
  --display:'Newsreader',Georgia,serif;
"""

BASE = """<!doctype html><meta charset="utf-8"><style>
%(fonts)s
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
:root{%(tokens)s}
html,body{width:%(w)spx;height:%(h)spx;}
body{font-family:var(--serif);-webkit-font-smoothing:antialiased;
  text-rendering:optimizeLegibility;font-feature-settings:"ss01","cv01";overflow:hidden;}
%(css)s
</style>%(body)s"""


def page(css, body):
    return BASE % {"fonts": fonts_css(), "tokens": TOKENS, "css": css,
                   "body": body, "w": SLIDE_W, "h": SLIDE_H}


def fit(text, big, mid, small, t1=52, t2=92):
    """Headlines vary a lot in length; step the size down instead of overflowing."""
    n = len(text)
    return big if n <= t1 else (mid if n <= t2 else small)


def esc(s):
    return html.escape(s)


def credit_of(tab, row):
    """A newsletter slide is someone else's reporting and must carry their byline,
    exactly as the site does. Our own briefs have no source line by design."""
    a = (row.get("author") or "").strip()
    return f"via {a}" if tab == "NEWSLETTERS" and a else ""


# ---------------------------------------------------------------- template: DECK
# A literal port of the site card: tinted bg, paper panel, accent-dot bullets.
# Maximum brand recognition -- someone who has seen winefeed.co knows this instantly.

DECK_CSS = """
body{background:var(--bg);display:flex;align-items:center;justify-content:center;padding:40px;}
.app{width:100%;height:100%;background:var(--paper);border:1px solid var(--line-2);
  border-radius:44px;box-shadow:0 34px 90px -30px rgba(10,12,20,.30);
  display:flex;flex-direction:column;overflow:hidden;}
.bar{display:flex;align-items:baseline;justify-content:space-between;
  padding:44px 52px 30px;flex:0 0 auto;}
.brand{display:flex;align-items:baseline;gap:16px;}
.wordmark{font-family:var(--display);font-weight:400;font-size:50px;letter-spacing:-0.012em;color:var(--ink);line-height:1;}
.byline{font-family:var(--mono);font-size:16px;letter-spacing:0.11em;text-transform:uppercase;color:var(--meta);}
.dateline{font-family:var(--mono);font-size:17px;letter-spacing:0.13em;text-transform:uppercase;color:var(--meta);}
.tabrow{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:0 34px;flex:0 0 auto;}
.tab{display:flex;align-items:center;justify-content:center;padding:20px 4px;
  border:1px solid var(--line);border-bottom:0;border-radius:16px 16px 0 0;background:var(--raise);
  color:var(--faint);font-family:var(--mono);font-size:14px;letter-spacing:0.03em;text-transform:uppercase;}
.tab.on{background:var(--paper);color:var(--ink);box-shadow:inset 0 4px 0 0 var(--accent);}
.card{flex:1 1 auto;border-top:1px solid var(--line);padding:56px 52px;display:flex;flex-direction:column;min-height:0;}
/* Centre the story block: bullet counts vary, and top-aligning leaves a dead
   slab above the footer on a short slide. */
.body{flex:1 1 auto;display:flex;flex-direction:column;justify-content:center;min-height:0;}
.head{font-weight:400;color:var(--title);letter-spacing:-0.02em;line-height:1.18;}
.cred{margin-top:22px;font-family:var(--mono);font-size:19px;letter-spacing:0.11em;
  text-transform:uppercase;color:var(--accent);}
.tk{list-style:none;margin-top:44px;display:flex;flex-direction:column;gap:28px;}
.tk li{position:relative;padding-left:34px;color:var(--body);font-size:29px;line-height:1.5;}
.tk li::before{content:"";position:absolute;left:0;top:14px;width:11px;height:11px;
  border-radius:50%;background:var(--accent);}
.foot{margin-top:auto;padding-top:40px;display:flex;justify-content:space-between;align-items:center;
  border-top:1px solid var(--line);}
.foot span{font-family:var(--mono);font-size:19px;letter-spacing:0.11em;text-transform:uppercase;color:var(--meta);}
.foot .url{color:var(--accent);}
.cover{flex:1 1 auto;display:flex;flex-direction:column;justify-content:center;padding:0 52px;}
.cover .big{font-family:var(--display);font-weight:400;font-size:104px;line-height:1.02;
  letter-spacing:-0.03em;color:var(--title);}
.cover .sub{margin-top:36px;font-size:34px;line-height:1.45;color:var(--body);max-width:80%;}
.rule{height:1px;background:var(--line);margin:0 52px;}
"""

def deck_shell(inner, tab=None):
    tabs = "".join(
        f'<div class="tab{" on" if t == tab else ""}">{t}</div>'
        for t in TABS)
    return f"""<body><div class="app">
  <div class="bar"><div class="brand"><div class="wordmark">winefeed</div>
    <div class="byline">by Primal Wine</div></div></div>
  <div class="tabrow">{tabs}</div>
  {inner}
</div></body>"""


def deck_cover(data):
    body = deck_shell(f"""<div class="card" style="justify-content:center">
      <div class="cover" style="padding:0">
        <div class="big">The wine<br>world,<br>summarized.</div>
        <div class="sub">{len(sum(data['items'].values(), []))} stories from today, in about two minutes.</div>
      </div>
      <div class="foot"><span>{pretty_date(data['date'])}</span><span class="url">winefeed.co</span></div>
    </div>""")
    return page(DECK_CSS, body)


def deck_story(tab, row, idx, total):
    head = row["head"]
    size = fit(head, 60, 52, 44)
    lis = "".join(f"<li>{esc(slide_text(b))}</li>" for b in row["takeaways"][:3])
    cred = credit_of(tab, row)
    body = deck_shell(f"""<div class="card">
      <div class="body">
        <div class="head" style="font-size:{size}px">{esc(head)}</div>
        {f'<div class="cred">{esc(cred)}</div>' if cred else ''}
        <ul class="tk">{lis}</ul>
      </div>
      <div class="foot"><span>{tab} &middot; {idx:02d} / {total:02d}</span><span class="url">winefeed.co</span></div>
    </div>""", tab=tab)
    return page(DECK_CSS, body)


def deck_cta(data):
    body = deck_shell(f"""<div class="card" style="justify-content:center">
      <div class="cover" style="padding:0">
        <div class="big" style="font-size:88px">Read the<br>rest today.</div>
        <div class="sub">Every story, every morning. Free at winefeed.co</div>
      </div>
      <div class="foot"><span>by Primal Wine</span><span class="url">winefeed.co</span></div>
    </div>""")
    return page(DECK_CSS, body)


# ---------------------------------------------------------------- template: STATEMENT
# Editorial. One fact per slide at display size. Built to stop a thumb, not to
# inform -- the depth lives on the site. Accent used as a full field on the cover.

STMT_CSS = """
body{background:var(--paper);padding:82px;display:flex;flex-direction:column;}
.kicker{font-family:var(--mono);font-size:20px;letter-spacing:0.14em;text-transform:uppercase;color:var(--accent);}
.big{font-family:var(--display);font-weight:400;letter-spacing:-0.032em;line-height:1.03;color:var(--title);}
.body{flex:1 1 auto;display:flex;flex-direction:column;justify-content:center;min-height:0;}
.sub{margin-top:44px;font-size:31px;line-height:1.5;color:var(--body);max-width:88%;}
.foot{margin-top:auto;padding-top:44px;border-top:1px solid var(--line);
  display:flex;justify-content:space-between;align-items:baseline;}
.wm{font-family:var(--display);font-size:36px;color:var(--ink);}
.url{font-family:var(--mono);font-size:20px;letter-spacing:0.11em;text-transform:uppercase;color:var(--accent);}
/* cover: inverted, accent field */
body.inv{background:var(--accent);}
body.inv .big,body.inv .wm{color:#fff;}
body.inv .kicker{color:rgba(255,255,255,.72);}
body.inv .sub{color:rgba(255,255,255,.86);}
body.inv .foot{border-top-color:rgba(255,255,255,.28);}
body.inv .url{color:#fff;}
.stat{font-family:var(--display);font-size:250px;line-height:.9;letter-spacing:-0.04em;color:var(--accent);}
"""

def stmt_cover(data):
    n = len(sum(data["items"].values(), []))
    return page(STMT_CSS, f"""<body class="inv">
      <div class="kicker">{pretty_date(data['date'])}</div>
      <div class="body">
        <div class="big" style="font-size:112px">The wine world,<br>summarized.</div>
        <div class="sub">{n} stories from today. Read them in about two minutes.</div>
      </div>
      <div class="foot"><div class="wm">winefeed</div><div class="url">winefeed.co</div></div>
    </body>""")


def stmt_story(tab, row, idx, total):
    head = row["head"]
    size = fit(head, 82, 68, 56, t1=44, t2=80)
    lead = slide_text(row["takeaways"][0])
    cred = credit_of(tab, row)
    return page(STMT_CSS, f"""<body>
      <div class="kicker">{tab}{f' &middot; {esc(cred)}' if cred else ''}</div>
      <div class="body">
        <div class="big" style="font-size:{size}px">{esc(head)}</div>
        <div class="sub">{esc(lead)}</div>
      </div>
      <div class="foot"><div class="wm">winefeed</div><div class="url">winefeed.co</div></div>
    </body>""")


def stmt_cta(data):
    return page(STMT_CSS, f"""<body class="inv">
      <div class="kicker">Every morning</div>
      <div class="body">
        <div class="big" style="font-size:104px">Read the rest<br>today.</div>
        <div class="sub">Free, and it takes two minutes. winefeed.co</div>
      </div>
      <div class="foot"><div class="wm">winefeed</div><div class="url">by Primal Wine</div></div>
    </body>""")


# ---------------------------------------------------------------- template: BRIEF
# The hybrid: an accent pill for topic, a Geist headline at a readable size, and
# hairline-separated bullets. Less literal than DECK, more informative than STATEMENT.

BRIEF_CSS = """
body{background:var(--paper);padding:76px;display:flex;flex-direction:column;}
.pill{display:inline-flex;align-self:flex-start;font-family:var(--mono);font-size:19px;
  letter-spacing:0.11em;text-transform:uppercase;color:var(--accent);
  border:1.5px solid var(--accent);border-radius:999px;padding:11px 24px;}
.head{margin-top:46px;font-weight:400;letter-spacing:-0.022em;line-height:1.16;color:var(--title);}
.cred{margin-top:24px;font-family:var(--mono);font-size:19px;letter-spacing:0.11em;
  text-transform:uppercase;color:var(--accent);}
.body{flex:1 1 auto;display:flex;flex-direction:column;justify-content:center;min-height:0;}
.tk{list-style:none;margin-top:52px;display:flex;flex-direction:column;}
.tk li{color:var(--body);font-size:30px;line-height:1.5;padding:30px 0;border-top:1px solid var(--line);}
.tk li:last-child{border-bottom:1px solid var(--line);}
.foot{margin-top:auto;padding-top:44px;display:flex;justify-content:space-between;align-items:baseline;}
.wm{font-family:var(--display);font-size:38px;color:var(--ink);}
.byl{font-family:var(--mono);font-size:16px;letter-spacing:0.11em;text-transform:uppercase;color:var(--meta);margin-left:14px;}
.count{font-family:var(--mono);font-size:19px;letter-spacing:0.11em;text-transform:uppercase;color:var(--accent);}
.big{font-family:var(--display);font-weight:400;letter-spacing:-0.03em;line-height:1.04;color:var(--title);margin-top:auto;}
.sub{margin-top:38px;font-size:32px;line-height:1.5;color:var(--body);max-width:84%;}
.date{font-family:var(--mono);font-size:19px;letter-spacing:0.13em;text-transform:uppercase;color:var(--meta);}
"""

def brief_cover(data):
    n = len(sum(data["items"].values(), []))
    return page(BRIEF_CSS, f"""<body>
      <div class="pill">{pretty_date(data['date'])}</div>
      <div class="big" style="font-size:108px">The wine<br>world,<br>summarized.</div>
      <div class="sub">{n} stories from today, in about two minutes.</div>
      <div class="foot"><div style="display:flex;align-items:baseline"><div class="wm">winefeed</div>
        <div class="byl">by Primal Wine</div></div><div class="count">winefeed.co</div></div>
    </body>""")


def brief_story(tab, row, idx, total):
    head = row["head"]
    size = fit(head, 62, 54, 46)
    lis = "".join(f"<li>{esc(slide_text(b))}</li>" for b in row["takeaways"][:3])
    cred = credit_of(tab, row)
    return page(BRIEF_CSS, f"""<body>
      <div class="pill">{tab}</div>
      <div class="body">
        <div class="head" style="font-size:{size}px">{esc(head)}</div>
        {f'<div class="cred">{esc(cred)}</div>' if cred else ''}
        <ul class="tk">{lis}</ul>
      </div>
      <div class="foot"><div style="display:flex;align-items:baseline"><div class="wm">winefeed</div>
        <div class="byl">by Primal Wine</div></div><div class="count">{idx:02d} / {total:02d}</div></div>
    </body>""")


def brief_cta(data):
    return page(BRIEF_CSS, f"""<body>
      <div class="pill">Every morning</div>
      <div class="big" style="font-size:96px">Read the<br>rest today.</div>
      <div class="sub">Free, and it takes two minutes. winefeed.co</div>
      <div class="foot"><div style="display:flex;align-items:baseline"><div class="wm">winefeed</div>
        <div class="byl">by Primal Wine</div></div><div class="count">winefeed.co</div></div>
    </body>""")


TEMPLATES = {
    "deck":      (deck_cover, deck_story, deck_cta),
    "statement": (stmt_cover, stmt_story, stmt_cta),
    "brief":     (brief_cover, brief_story, brief_cta),
}


def build_carousel(data, name):
    cover, story, cta = TEMPLATES[name]
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    rows = leads(data)
    total = len(rows)
    files = []

    p = os.path.join(d, "01-cover.png"); shot(cover(data), p); files.append(p)
    for i, (tab, row) in enumerate(rows, 1):
        p = os.path.join(d, f"{i+1:02d}-{tab.lower()}.png")
        shot(story(tab, row, i, total), p); files.append(p)
    p = os.path.join(d, f"{total+2:02d}-cta.png"); shot(cta(data), p); files.append(p)

    print(f"  {name}: {len(files)} slides -> {d}")
    return files


# ---------------------------------------------------------------- X drafts

X_PROMPT = """You write X (Twitter) posts for winefeed, a daily wine news brief by Primal Wine.

Below is one story we published today: our headline and our key-takeaway bullets.

RULES, all hard:
- Use ONLY facts present in the bullets below. Invent NOTHING. No new numbers, names, dates or claims.
- Under %(budget)d characters. This is a hard ceiling, not a target. Count them.
- Open with the single most surprising concrete fact, not a preamble and not a question.
- Name people and places the way the bullets do. A reader must never meet a bare surname.
- Plain declarative sentences. No hashtags. No emoji. No "thread", no "here's why", no hype.
- NEVER use an em-dash or an en-dash. Use commas, periods or parentheses.
- Do not end with a link; the link is appended separately.

Write %(n)d DIFFERENT drafts of the same story, each a different angle:
1. "fact"      -- lead with the hardest number or the most concrete detail.
2. "tension"   -- lead with what is at stake or what changed.
3. "human"     -- lead with a named person and what they did or said. If the bullets
   name nobody, lead with the named estate or region instead. Do NOT invent a person.
%(credit)s
HEADLINE: %(head)s

BULLETS:
%(bullets)s

Return JSON only: {"drafts": [{"angle": "fact", "text": "..."}, ...]}
"""

X_LIMIT = 280
# X counts every link as 23 chars however long it really is (t.co rewrites it), so
# budgeting against len(url) silently ships drafts that will not post.
URL_COST = 23


def x_cost(text, credit=""):
    return len(text) + (1 + len(credit) if credit else 0) + 1 + URL_COST


def x_drafts(data, per_tab=1):
    sys.path.insert(0, HERE)
    import takeaways
    key = takeaways.get_key()
    if not key:
        print("  ! no ANTHROPIC_API_KEY, skipping X drafts", file=sys.stderr)
        return []

    out = []
    for tab, row in leads(data, per_tab):
        bullets = "\n".join("- " + b for b in row["takeaways"][:5])

        # A newsletter row points at somebody else's piece, so it credits the writer
        # and links them. Our own briefs carry no source line by design (the
        # original-desk model), so they link the site instead.
        author = (row.get("author") or "").strip() if tab == "NEWSLETTERS" else ""
        link = row.get("url") if tab == "NEWSLETTERS" else "https://winefeed.co"
        credit = f"via {author}" if author else ""
        instruction = (f"This is {author}'s reporting. Do NOT work their name into the"
                       " text; a credit line is appended separately.\n") if author else ""
        budget = X_LIMIT - URL_COST - 1 - ((len(credit) + 1) if credit else 0)

        res = takeaways._call(
            key, X_PROMPT % {"head": row["head"], "bullets": bullets, "n": 3,
                             "budget": budget, "credit": instruction},
            max_tokens=900)
        if not res or not res.get("drafts"):
            print(f"  ! no drafts for {tab}", file=sys.stderr)
            continue
        drafts = []
        for d in res["drafts"]:
            t = re.sub(r"\s+", " ", str(d.get("text", ""))).strip()
            t = EM_PAREN.sub(", ", t).replace("—", ", ").replace("–", "-")
            if not t:
                continue
            n = x_cost(t, credit)
            over = n > X_LIMIT
            if over:
                # Loud, never silent. A draft over the ceiling cannot be posted, and
                # a quietly dropped one just looks like the model wrote fewer.
                print(f"    ! {tab}/{d.get('angle')}: {n} chars, over {X_LIMIT}",
                      file=sys.stderr)
            drafts.append({"angle": d.get("angle", ""), "text": t, "credit": credit,
                           "link": link, "chars": n, "over_limit": over})
        out.append({"tab": tab, "head": row["head"], "drafts": drafts})
        ok = sum(1 for d in drafts if not d["over_limit"])
        print(f"  {tab}: {ok}/{len(drafts)} drafts fit {X_LIMIT}")
    return out


def post_text(d):
    """Exactly what gets pasted into X."""
    return "\n\n".join(p for p in [d["text"], d.get("credit"), d["link"]] if p)


def write_x(drafts):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "x_drafts.json"), "w") as f:
        json.dump(drafts, f, indent=2)
    lines = []
    for s in drafts:
        lines.append("=" * 72)
        lines.append(f"{s['tab']}  |  {s['head']}")
        lines.append("=" * 72)
        for d in s["drafts"]:
            flag = "  << OVER LIMIT, do not post" if d["over_limit"] else ""
            lines.append(f"\n--- {d['angle'].upper()}  ({d['chars']}/{X_LIMIT}){flag}")
            lines.append(post_text(d))
        lines.append("")
    with open(os.path.join(OUT, "x_drafts.txt"), "w") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", choices=list(TEMPLATES) + ["all"], default="all")
    ap.add_argument("--no-x", action="store_true")
    ap.add_argument("--no-slides", action="store_true")
    a = ap.parse_args()

    data = load_feed()
    os.makedirs(OUT, exist_ok=True)
    print(f"winefeed repurpose -- {data['date']}")

    if not a.no_slides:
        names = list(TEMPLATES) if a.template == "all" else [a.template]
        for n in names:
            build_carousel(data, n)

    if not a.no_x:
        write_x(x_drafts(data))
        print(f"  x drafts -> {OUT}/x_drafts.txt")


if __name__ == "__main__":
    main()
