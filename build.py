# -*- coding: utf-8 -*-
import html, datetime, os, json

_HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = open(os.path.join(_HERE, 'fonts.css')).read().strip()
CSS   = open(os.path.join(_HERE, 'app.css')).read()
JS    = open(os.path.join(_HERE, 'app.js')).read()

# Klaviyo public ids (non-secret) for the signup form, if configured
KPUB, KLIST = "", ""
try:
    _k = json.load(open(os.path.join(_HERE, 'klaviyo.json')))
    KPUB, KLIST = _k.get('public', ''), _k.get('list', '')
except Exception:
    pass

TAB_ORDER = ["MARKET", "CULTURE", "SCIENCE", "NEWSLETTERS"]

MONTHS = ["", "JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
MONTHS_FULL = ["", "JANUARY","FEBRUARY","MARCH","APRIL","MAY","JUNE","JULY","AUGUST","SEPTEMBER","OCTOBER","NOVEMBER","DECEMBER"]
WEEKDAYS = ["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"]

def fmt_date(s):
    parts = str(s).split("-")
    if len(parts) == 3:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2]); return f"{d} {MONTHS[m]} {y}"
    if len(parts) == 2:
        y, m = int(parts[0]), int(parts[1]); return f"{MONTHS_FULL[m]} {y}"
    return str(s)

def esc(t):
    return html.escape(str(t).replace("—", ", ").replace("–", "-"), quote=True)

# ---- live data (required) ----
DATA = json.load(open(os.path.join(_HERE, 'feed_data.json')))
ITEMS = DATA.get("items", {})
_d = DATA.get("date")
if _d:
    _y, _m, _dd = map(int, _d.split("-")); today = datetime.date(_y, _m, _dd)
else:
    today = datetime.date(2026, 7, 12)
DATELINE = f"{WEEKDAYS[today.weekday()]} {today.day} {MONTHS_FULL[today.month]} {today.year}"

ARROW_R = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>'
ARROW_L = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></svg>'
TOGGLE = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.25" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M12 2.75 A9.25 9.25 0 0 1 12 21.25 Z" fill="currentColor"/></svg>'
MAIL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>'

def build_tabs():
    out = []
    for i, name in enumerate(TAB_ORDER):
        act = " is-active" if i == 0 else ""
        sel = "true" if i == 0 else "false"
        out.append(f'<button class="tab{act}" role="tab" aria-selected="{sel}" data-tab="{i}">{name}</button>')
    return "\n          ".join(out)

def body_html(row):
    tk = row.get("takeaways") or []
    if tk:
        return '<ul class="takeaways">' + "".join(f'<li>{esc(b)}</li>' for b in tk) + '</ul>'
    return f'<p class="summary">{esc(row.get("summ", ""))}</p>'

def build_slides():
    slides = []
    for ti, name in enumerate(TAB_ORDER):
        rows = ITEMS.get(name, [])
        if name != "NEWSLETTERS":
            rows = rows[:5]     # safety net: news tabs render at most 5 (enrich caps too)
        count = len(rows)
        for wi, row in enumerate(rows, 1):
            date = row.get("date", "")
            head = row.get("head", "")
            if name == "NEWSLETTERS":
                # independent piece: keep source + byline in meta, linked head, read-more
                src = row.get("source", "")
                author = row.get("author", "")
                url = row.get("url", "")
                byline = f'<span class="dot">&middot;</span><span class="by">{esc(author)}</span>' if author else ''
                meta = f'<span class="idx">{wi:02d}</span><span class="src">{esc(src)}</span>{byline}<span class="dot">&middot;</span><time class="date">{esc(fmt_date(date))}</time>'
                head_html = f'<h3 class="head"><a href="{esc(url)}" target="_blank" rel="noopener">{esc(head)}</a></h3>'
                tail = f'<a class="read" href="{esc(url)}" target="_blank" rel="noopener">Read the full story <span class="read-arrow" aria-hidden="true">{ARROW_R}</span></a>'
            else:
                # our own brief: unlinked headline, tiny non-linked credit line, no read-more
                meta = f'<span class="idx">{wi:02d}</span><time class="date">{esc(fmt_date(date))}</time>'
                head_html = f'<h3 class="head">{esc(head)}</h3>'
                srcs = row.get("sources") or []
                tail = f'<p class="credit">Reported by {esc(", ".join(srcs))}</p>' if srcs else ''
            slides.append(f'''<article class="slide" data-tab="{ti}" role="group" aria-roledescription="slide" aria-label="{name} {wi} of {count}">
              <div class="slide-inner">
                <div class="meta">{meta}</div>
                {head_html}
                {body_html(row)}
                {tail}
              </div>
            </article>''')
    return "\n            ".join(slides)

STYLE = "<style>\n" + FONTS + "\n" + CSS + "\n</style>"

markup = f'''<div class="app" data-kpub="{esc(KPUB)}" data-klist="{esc(KLIST)}">
      <header class="bar">
        <div class="brand">
          <h1 class="wordmark">wine<span class="dropchar">feed</span></h1>
          <span class="byline">by Primal Wine</span>
        </div>
        <div class="bar-right">
          <span class="dateline">{DATELINE}</span>
          <button class="theme-toggle" id="themeToggle" type="button" aria-label="Toggle light or dark theme">{TOGGLE}</button>
        </div>
      </header>

      <nav class="tabs-outer" aria-label="Topics">
        <div class="tablist" role="tablist">
          {build_tabs()}
        </div>
      </nav>

      <main class="deck" id="deck">
        <div class="track" id="track">
            {build_slides()}
        </div>
      </main>

      <footer class="controls">
        <div class="nav-row">
          <button class="nav-btn" id="prevBtn" type="button" aria-label="Previous story">{ARROW_L}</button>
          <div class="progress">
            <div class="dots" aria-hidden="true"></div>
            <span class="counter" id="tabname"></span>
            <span class="counter" id="counter"></span>
          </div>
          <button class="nav-btn" id="nextBtn" type="button" aria-label="Next story">{ARROW_R}</button>
        </div>
        <form class="subscribe" id="subForm" novalidate>
          <div class="sub-field">
            <input type="email" id="subEmail" placeholder="Sign up for our daily brief" autocomplete="email" aria-label="Sign up for our daily brief">
            <button class="sub-btn" type="submit" aria-label="Subscribe">{MAIL}</button>
          </div>
          <span class="sub-msg" id="subMsg"></span>
        </form>
      </footer>
    </div>'''

BODY = markup + "\n<script>\n" + JS + "\n</script>"

# ---- Artifact version (host wraps in doctype/head/body) ----
artifact = f'<title>winefeed — a daily wine-news digest</title>\n{STYLE}\n{BODY}\n'
open(os.path.join(_HERE, 'winefeed_artifact.html'), 'w').write(artifact)

# ---- Standalone version for GitHub Pages ----
standalone = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>winefeed — a daily wine-news digest</title>
<meta name="description" content="The wine world, summarized. Original, fact-based daily briefs across Market, Culture, Science, and independent Newsletters.">
<meta name="author" content="Guido Cattabianchi">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22%3E%3Ctext y=%22.9em%22 font-size=%2290%22%3E%F0%9F%8D%B7%3C/text%3E%3C/svg%3E">
{STYLE}
</head>
<body>
{BODY}
</body>
</html>
'''
open(os.path.join(_HERE, 'index.html'), 'w').write(standalone)

print("Dateline:", DATELINE)
print("slides:", sum(len(ITEMS.get(t, [])) for t in TAB_ORDER))
print("artifact bytes:", len(artifact), "| standalone bytes:", len(standalone))
