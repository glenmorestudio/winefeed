# -*- coding: utf-8 -*-
"""
winefeed build
==============
Renders every page of the site from feed_data.json + the archive snapshots.

Outputs:
  index.html               today's deck, standalone (fonts/CSS/JS inlined -> one request)
  winefeed_artifact.html   same deck, Artifact-preview variant (host wraps head/body)
  archive/YYYY-MM-DD.json  a snapshot of each published day (today's is written here)
  archive/index.html       the back catalogue, newest first
  archive/YYYY-MM-DD.html  one past edition, same deck

Archive pages link the shared /fonts.css, /app.css and /app.js rather than inlining
them: those files are already deployed at the repo root, so every past day reuses one
cached copy instead of carrying its own 190KB of base64 fonts. index.html stays
self-contained, where the single-request first paint is worth the bytes.

Linked vs unlinked is decided PER ROW by whether it has a `url`, not by which tab it is
in. Newsletters always link (the point is pointing at the writer). Our own news briefs
never do (original summaries of public facts, no outlet's scoop). Editions from before
2026-07-13 predate the original-desk model: their news rows are the outlets' own
excerpts and DO carry a url, so the archive keeps their credit and link intact rather
than passing someone else's excerpt off as our writing.

Run: python3 build.py   (update.py calls this after every refresh)
"""
import html, datetime, os, json, glob

_HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_DIR = os.path.join(_HERE, "archive")
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
WEEKDAYS_SHORT = ["MON","TUE","WED","THU","FRI","SAT","SUN"]

def fmt_date(s):
    parts = str(s).split("-")
    if len(parts) == 3:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2]); return f"{d} {MONTHS[m]} {y}"
    if len(parts) == 2:
        y, m = int(parts[0]), int(parts[1]); return f"{MONTHS_FULL[m]} {y}"
    return str(s)

def esc(t):
    return html.escape(str(t).replace("—", ", ").replace("–", "-"), quote=True)

def parse_day(s):
    y, m, d = map(int, str(s).split("-"))
    return datetime.date(y, m, d)

def dateline_of(day):
    return f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS_FULL[day.month]} {day.year}"

def dateline_html(day):
    """Spelled out where there's room, abbreviated on a phone — never dropped, since on
    an archive page the date is the only thing telling you which edition you're reading."""
    return (f'<span class="dateline"><span class="dl-full">{esc(dateline_of(day))}</span>'
            f'<span class="dl-short">{day.day} {MONTHS[day.month]}</span></span>')

ARROW_R = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>'
ARROW_L = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></svg>'
TOGGLE = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.25" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M12 2.75 A9.25 9.25 0 0 1 12 21.25 Z" fill="currentColor"/></svg>'
MAIL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>'
# lucide "history": the past editions live behind this
HISTORY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>'

# ---------- pieces ----------
def tabs_html(items):
    """The first tab that actually has stories starts active. A topic can legitimately
    come up empty (nothing groundable that day), and an empty tab must not look clickable."""
    first = next((i for i, n in enumerate(TAB_ORDER) if items.get(n)), 0)
    out = []
    for i, name in enumerate(TAB_ORDER):
        empty = not items.get(name)
        cls = "tab" + (" is-active" if i == first and not empty else "") + (" is-empty" if empty else "")
        sel = "true" if (i == first and not empty) else "false"
        dis = ' disabled aria-disabled="true"' if empty else ''
        out.append(f'<button class="{cls}" role="tab" aria-selected="{sel}" data-tab="{i}"{dis}>{name}</button>')
    return "\n          ".join(out)

def body_html(row):
    tk = row.get("takeaways") or []
    if tk:
        return '<ul class="takeaways">' + "".join(f'<li>{esc(b)}</li>' for b in tk) + '</ul>'
    return f'<p class="summary">{esc(row.get("summ", ""))}</p>'

def slides_html(items):
    slides = []
    for ti, name in enumerate(TAB_ORDER):
        rows = items.get(name, [])
        count = len(rows)   # variable per tab: the engine publishes what it can ground
        for wi, row in enumerate(rows, 1):
            date, head, url = row.get("date", ""), row.get("head", ""), row.get("url", "")
            if url:
                # someone else's piece: credit the outlet/writer and link out
                src, author = row.get("source", ""), row.get("author", "")
                byline = f'<span class="dot">&middot;</span><span class="by">{esc(author)}</span>' if author else ''
                srctag = f'<span class="src">{esc(src)}</span>' if src else ''
                meta = f'<span class="idx">{wi:02d}</span>{srctag}{byline}<span class="dot">&middot;</span><time class="date">{esc(fmt_date(date))}</time>'
                head_html = f'<h3 class="head"><a href="{esc(url)}" target="_blank" rel="noopener">{esc(head)}</a></h3>'
                tail = f'<a class="read" href="{esc(url)}" target="_blank" rel="noopener">Read the full story <span class="read-arrow" aria-hidden="true">{ARROW_R}</span></a>'
            else:
                # our own brief: original research/summary of public facts, not any
                # outlet's scoop -> unlinked headline, no credit line, no read-more
                meta = f'<span class="idx">{wi:02d}</span><time class="date">{esc(fmt_date(date))}</time>'
                head_html = f'<h3 class="head">{esc(head)}</h3>'
                tail = ''
            slides.append(f'''<article class="slide" data-tab="{ti}" role="group" aria-roledescription="slide" aria-label="{name} {wi} of {count}">
              <div class="slide-inner">
                <div class="meta">{meta}</div>
                {head_html}
                {body_html(row)}
                {tail}
              </div>
            </article>''')
    return "\n            ".join(slides)

def brand_html(home_href=None):
    mark = '<h1 class="wordmark">wine<span class="dropchar">feed</span></h1>'
    if home_href:
        mark = f'<a class="wordmark-link" href="{esc(home_href)}" aria-label="winefeed home">{mark}</a>'
    return f'<div class="brand">{mark}<span class="byline">by Primal Wine</span></div>'

def header_html(*, right, home_href=None):
    return f'''<header class="bar">
        {brand_html(home_href)}
        <div class="bar-right">{right}</div>
      </header>'''

def subscribe_html():
    return f'''<form class="subscribe" id="subForm" novalidate>
          <div class="sub-field">
            <input type="email" id="subEmail" placeholder="Sign up for our daily brief" autocomplete="email" aria-label="Sign up for our daily brief">
            <button class="sub-btn" type="submit" aria-label="Subscribe">{MAIL}</button>
          </div>
          <span class="sub-msg" id="subMsg"></span>
        </form>'''

def deck_html(items, *, right, home_href=None):
    return f'''<div class="app" data-kpub="{esc(KPUB)}" data-klist="{esc(KLIST)}">
      {header_html(right=right, home_href=home_href)}

      <nav class="tabs-outer" aria-label="Topics">
        <div class="tablist" role="tablist">
          {tabs_html(items)}
        </div>
      </nav>

      <main class="deck" id="deck">
        <div class="track" id="track">
            {slides_html(items)}
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
        {subscribe_html()}
      </footer>
    </div>'''

def page(body, *, title, desc, root="", inline=True):
    """root: path prefix back to the site root ('' at root, '../' one level down)."""
    if inline:
        head_assets = "<style>\n" + FONTS + "\n" + CSS + "\n</style>"
        tail_assets = "<script>\n" + JS + "\n</script>"
    else:
        head_assets = (f'<link rel="stylesheet" href="{root}fonts.css">\n'
                       f'<link rel="stylesheet" href="{root}app.css">')
        tail_assets = f'<script src="{root}app.js" defer></script>'
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="author" content="Guido Cattabianchi">
<link rel="icon" type="image/svg+xml" href="{root}favicon.svg">
{head_assets}
</head>
<body>
{body}
{tail_assets}
</body>
</html>
'''

# ---------- archive ----------
def snapshot(data):
    """Keep today's edition. Re-running the same day just refreshes it."""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    date = data.get("date")
    if not date:
        return
    with open(os.path.join(ARCHIVE_DIR, f"{date}.json"), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def archived_days():
    """[(date_str, data)] newest first."""
    out = []
    for p in sorted(glob.glob(os.path.join(ARCHIVE_DIR, "*.json")), reverse=True):
        try:
            data = json.load(open(p))
        except Exception:
            continue
        if data.get("date") and data.get("items"):
            out.append((data["date"], data))
    return out

def lead_of(data):
    for tab in TAB_ORDER:
        rows = data["items"].get(tab) or []
        if rows:
            return rows[0].get("head", "")
    return ""

def render_archive_day(date, data):
    day = parse_day(date)
    right = (f'<a class="arc-tag" href="index.html">Archive</a>'
             + dateline_html(day)
             + f'<button class="theme-toggle" id="themeToggle" type="button" aria-label="Toggle light or dark theme">{TOGGLE}</button>')
    body = deck_html(data["items"], right=right, home_href="../")
    n = sum(len(v) for v in data["items"].values())
    html_out = page(body, root="../", inline=False,
                    title=f"winefeed — {dateline_of(day).title()}",
                    desc=f"The winefeed edition for {dateline_of(day).title()}: {n} original wine briefs across Market, Culture, Science and independent Newsletters.")
    open(os.path.join(ARCHIVE_DIR, f"{date}.html"), "w").write(html_out)

def render_archive_index(days):
    rows, cur_month = [], None
    for date, data in days:
        day = parse_day(date)
        month = (day.year, day.month)
        if month != cur_month:
            cur_month = month
            rows.append(f'<div class="arc-month">{MONTHS_FULL[day.month]} {day.year}</div>')
        n = sum(len(v) for v in data["items"].values())
        lead = lead_of(data)
        rows.append(f'''<a class="arc-row" href="{esc(date)}.html">
            <span class="arc-date">{WEEKDAYS_SHORT[day.weekday()]} {day.day:02d}</span>
            <span class="arc-lead">{esc(lead)}</span>
            <span class="arc-n">{n}</span>
          </a>''')
    oldest = parse_day(days[-1][0]) if days else datetime.date.today()
    right = f'<button class="theme-toggle" id="themeToggle" type="button" aria-label="Toggle light or dark theme">{TOGGLE}</button>'
    body = f'''<div class="app" data-kpub="{esc(KPUB)}" data-klist="{esc(KLIST)}">
      {header_html(right=right, home_href="../")}
      <main class="sheet">
        <div class="sheet-inner">
          <h2 class="sheet-title">Archive</h2>
          <p class="sheet-note">Every edition of winefeed since {fmt_date(oldest.isoformat()).title()}. {len(days)} in all.</p>
          {"".join(rows)}
        </div>
      </main>
      <footer class="controls">
        {subscribe_html()}
      </footer>
    </div>'''
    html_out = page(body, root="../", inline=False,
                    title="winefeed — archive",
                    desc="Every past edition of winefeed, the daily wine-news brief by Primal Wine.")
    open(os.path.join(ARCHIVE_DIR, "index.html"), "w").write(html_out)

# ---------- main ----------
def main():
    data = json.load(open(os.path.join(_HERE, 'feed_data.json')))
    items = data.get("items", {})
    today = parse_day(data["date"]) if data.get("date") else datetime.date(2026, 7, 12)

    snapshot(data)

    right = (dateline_html(today)
             + f'<a class="icon-link" href="archive/" aria-label="Read past editions" title="Past editions">{HISTORY}</a>'
             f'<button class="theme-toggle" id="themeToggle" type="button" aria-label="Toggle light or dark theme">{TOGGLE}</button>')
    body = deck_html(items, right=right)

    open(os.path.join(_HERE, 'index.html'), 'w').write(page(
        body, title="winefeed — a daily wine-news digest",
        desc="The wine world, summarized. Original, fact-based daily briefs across Market, Culture, Science, and independent Newsletters."))

    # Artifact preview variant: the host supplies doctype/head/body
    artifact = ("<title>winefeed — a daily wine-news digest</title>\n"
                "<style>\n" + FONTS + "\n" + CSS + "\n</style>\n"
                + body + "\n<script>\n" + JS + "\n</script>\n")
    open(os.path.join(_HERE, 'winefeed_artifact.html'), 'w').write(artifact)

    days = archived_days()
    for date, d in days:
        render_archive_day(date, d)
    if days:
        render_archive_index(days)

    print("Dateline:", dateline_of(today))
    print("slides:", sum(len(items.get(t, [])) for t in TAB_ORDER),
          {t: len(items.get(t, [])) for t in TAB_ORDER})
    print(f"archive: {len(days)} day(s)")

if __name__ == "__main__":
    main()
