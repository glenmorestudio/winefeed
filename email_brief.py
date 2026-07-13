# -*- coding: utf-8 -*-
"""
winefeed daily brief -> email (Klaviyo), mirroring the winefeed.co website style.
feed_data.json -> header (winefeed by Primal Wine, left-aligned) -> the brief
(4 topics x 5 stories, key takeaways, hairline-separated) -> Wine of the Day
(featured-product format, no pill) -> Shop All / Join Club band -> footer.
Palette + type match the site (paper/ink/blue accent, Geist + Newsreader).
"""
import html, datetime, os, json, re, base64

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(HERE, "feed_data.json")))
ITEMS = DATA.get("items", {})
TAB_ORDER = ["MARKET", "CULTURE", "SCIENCE", "NEWSLETTERS"]
BULLETS_IN_EMAIL = 3

MONTHS_FULL = ["", "JANUARY","FEBRUARY","MARCH","APRIL","MAY","JUNE","JULY","AUGUST","SEPTEMBER","OCTOBER","NOVEMBER","DECEMBER"]
MONTHS = ["", "JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
WEEKDAYS = ["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"]
_d = DATA.get("date")
today = datetime.date(*map(int, _d.split("-"))) if _d else datetime.date.today()
DATELINE = f"{WEEKDAYS[today.weekday()]} {today.day} {MONTHS_FULL[today.month]} {today.year}"

def e(t): return html.escape(str(t).replace("—", ", ").replace("–", "-"), quote=True)
def fmt(s):
    p = str(s).split("-")
    if len(p) == 3: return f"{int(p[2])} {MONTHS[int(p[1])]} {p[0]}"
    if len(p) == 2: return f"{MONTHS_FULL[int(p[1])]} {p[0]}"
    return str(s)

# ---- winefeed.co palette + type ----
INK, TITLE, BODY, META = "#16181D", "#08090C", "#64686F", "#6B6F78"
LINE, PAGE, CARD, RAISE = "#E6E7EA", "#EDEEF1", "#FBFBFA", "#F1F2F4"
ACCENT, DARK = "#2743C9", "#16181D"
SERIF = "'Newsreader', Georgia, serif"
SANS  = "'Geist', -apple-system, 'Segoe UI', Roboto, Arial, sans-serif"
MONO  = "'Geist Mono', ui-monospace, Menlo, monospace"

# wordmark (LIGHT, for the accent header): hosted PNG for real sends, inline data-URI for the preview
WM_URL = "https://winefeed.co/wordmark-light.png"
_wm_png = os.path.join(HERE, "wordmark-light.png")
WM_DATA = ("data:image/png;base64," + base64.b64encode(open(_wm_png, "rb").read()).decode()) if os.path.exists(_wm_png) else WM_URL
WM_W, WM_H = 100, 19

def story(row, wi, is_newsletter, first):
    date = row.get("date", "")
    head = row.get("head", "")
    tks = (row.get("takeaways") or [])[:BULLETS_IN_EMAIL]
    if tks:
        lis = "".join(
            f'<tr><td valign="top" style="padding:0 9px 7px 0;"><span style="color:{ACCENT};">&bull;</span></td>'
            f'<td valign="top" style="padding:0 0 7px 0; font-family:{SANS}; font-size:14px; line-height:1.5; color:{BODY};">{e(b)}</td></tr>'
            for b in tks)
        body = f'<table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:8px 0 0;">{lis}</table>'
    else:
        body = f'<p style="margin:8px 0 0; font-family:{SANS}; font-size:14px; line-height:1.55; color:{BODY};">{e(row.get("summ",""))}</p>'
    sep = "" if first else f"border-top:1px solid {LINE};"
    pad = "16px 0 18px" if first else "18px 0 18px"
    if is_newsletter:
        # independent piece: source + byline in meta, linked headline
        author = row.get("author", "")
        by = f' &middot; <span style="color:{META};">{e(author)}</span>' if author else ""
        meta = (f'<span style="color:{ACCENT};">{wi:02d}</span> &middot; '
                f'<span style="color:{INK};">{e(row.get("source",""))}</span>{by} &middot; {e(fmt(date))}')
        head_html = (f'<a href="{e(row.get("url",""))}" style="text-decoration:none; color:{TITLE}; '
                     f'font-family:{SANS}; font-size:16.5px; font-weight:500; line-height:1.34;">{e(head)}</a>')
        credit = ""
    else:
        # our own brief: original summary of public facts, no credit, no outbound link
        meta = f'<span style="color:{ACCENT};">{wi:02d}</span> &middot; {e(fmt(date))}'
        head_html = (f'<span style="color:{TITLE}; font-family:{SANS}; font-size:16.5px; '
                     f'font-weight:500; line-height:1.34;">{e(head)}</span>')
        credit = ""
    return f'''
    <tr><td style="padding:{pad}; {sep}">
      <p style="margin:0 0 6px; font-family:{MONO}; font-size:10px; letter-spacing:0.06em; text-transform:uppercase; color:{META};">
        {meta}
      </p>
      {head_html}
      {body}
      {credit}
    </td></tr>'''

def topic_block(name, ti):
    rows = ITEMS.get(name, [])
    is_newsletter = name == "NEWSLETTERS"
    stories = "".join(story(r, i, is_newsletter, first=(i == 1)) for i, r in enumerate(rows, 1))
    sep = "" if ti == 0 else f"border-top:1px solid {LINE};"
    return f'''
    <tr><td style="padding:{'20px' if ti == 0 else '28px'} 0 4px; {sep}">
      <span style="display:inline-block; font-family:{MONO}; font-size:11px; letter-spacing:0.1em; text-transform:uppercase; color:{ACCENT}; background:transparent; border:1px solid {ACCENT}; border-radius:999px; padding:5px 14px;">{name}</span>
    </td></tr>
    {stories}'''

BRIEF = "".join(topic_block(n, i) for i, n in enumerate(TAB_ORDER))

# ---- Wine of the Day (featured-product format, NO pill) ----
WOTD = f'''
    <tr><td style="padding:30px 0 0; border-top:1px solid {LINE};">
      <table cellpadding="0" cellspacing="0" border="0" width="100%">
        <tr>
          <td width="140" valign="top" style="padding:0 20px 0 0;">
            <div style="width:140px; height:180px; background:{RAISE}; border:1px solid {LINE}; border-radius:16px; text-align:center; line-height:180px; font-family:{MONO}; font-size:10px; letter-spacing:0.1em; color:{META};">BOTTLE</div>
          </td>
          <td valign="top">
            <p style="margin:0 0 6px; font-family:{MONO}; font-size:10px; letter-spacing:0.06em; text-transform:uppercase; color:{META};"><span style="color:{ACCENT};">Wine of the Day</span> &middot; Red &middot; Etna, Sicily &middot; $32</p>
            <p style="margin:0 0 8px; font-family:{SERIF}; font-size:19px; font-weight:500; color:{TITLE}; line-height:1.25;">Wine of the Day title</p>
            <p style="margin:0 0 16px; font-family:{SANS}; font-size:13.5px; line-height:1.6; color:{BODY}; min-height:65px;">One flowing, three-line note on why this bottle is worth reaching for tonight. Producer, place, and the single thing that makes it sing.</p>
            <a href="https://primalwine.com/products/PRODUCT-HANDLE" style="display:inline-block; font-family:{MONO}; font-size:11px; letter-spacing:0.06em; text-transform:uppercase; color:{INK}; text-decoration:none; border:1px solid {INK}; border-radius:999px; padding:9px 22px;">Shop this bottle</a>
          </td>
        </tr>
      </table>
    </td></tr>'''

CTA = f'''
    <tr><td style="padding:32px 0 6px;">
      <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:{ACCENT}; border-radius:16px;">
        <tr><td align="center" style="padding:30px 30px;">
          <p style="margin:0 0 6px; font-family:{MONO}; font-size:10px; text-transform:uppercase; letter-spacing:0.09em; color:rgba(255,255,255,0.6);">winefeed by primal wine</p>
          <p style="margin:6px 0 20px; font-family:{SANS}; font-size:20px; font-weight:500; color:#ffffff; line-height:1.3;">Keep exploring.</p>
          <table cellpadding="0" cellspacing="0" border="0" style="margin:0 auto;"><tr>
            <td class="cta-btn-col" valign="top" style="padding:0 6px 0 0;">
              <a href="https://primalwine.com/collections/all" class="cta-btn" style="display:inline-block; background:#ffffff; color:{ACCENT}; border:1px solid #ffffff; text-decoration:none; text-align:center; font-family:{MONO}; font-size:11px; padding:11px 24px; border-radius:999px; text-transform:uppercase; letter-spacing:0.06em;">Shop All Wine</a>
            </td>
            <td class="cta-btn-col-right" valign="top" style="padding:0 0 0 6px;">
              <a href="https://primalwine.com/products/primal-wine-club-natural-wine-club" class="cta-btn" style="display:inline-block; background:transparent; color:#ffffff; border:1px solid rgba(255,255,255,0.5); text-decoration:none; text-align:center; font-family:{MONO}; font-size:11px; padding:11px 24px; border-radius:999px; text-transform:uppercase; letter-spacing:0.06em;">Join Our Club</a>
            </td>
          </tr></table>
        </td></tr>
      </table>
    </td></tr>'''

FONTS_IMPORT = "@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&family=Newsreader:wght@400;500&display=swap');"

def page(footer, wm):
    return f'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
{FONTS_IMPORT}
body{{margin:0; background:{PAGE};}}
@media (max-width:600px){{
  .card-inner{{padding:2px 22px 30px !important;}}
  .hdr-inner{{padding:22px 22px !important;}}
  .cta-btn-col, .cta-btn-col-right{{display:block !important; width:100% !important; padding:0 0 12px 0 !important;}}
  .cta-btn-col-right{{padding:0 !important;}}
  .cta-btn{{display:block !important; width:100% !important; box-sizing:border-box !important;}}
}}
</style></head>
<body>
<div style="display:none; max-height:0; overflow:hidden; opacity:0;">The wine world in five-minute reads. Today's brief from winefeed by Primal Wine.</div>
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:{PAGE};"><tr><td align="center" style="padding:28px 14px;">
  <table cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:600px; background:{CARD}; border:1px solid {LINE}; border-radius:20px;">

    <tr><td class="hdr-inner" style="background:{ACCENT}; border-radius:19px 19px 0 0; padding:26px 34px 26px;">
      <table cellpadding="0" cellspacing="0" border="0" width="100%"><tr>
        <td valign="baseline" style="white-space:nowrap;">
          <img src="{wm}" width="{WM_W}" height="{WM_H}" alt="winefeed" style="display:inline-block; vertical-align:baseline; border:0;">
          <span style="font-family:{MONO}; font-size:9.5px; letter-spacing:0.11em; text-transform:uppercase; color:rgba(255,255,255,0.72); padding-left:10px;">by Primal Wine</span>
        </td>
        <td valign="baseline" align="right" style="font-family:{MONO}; font-size:9.5px; letter-spacing:0.12em; text-transform:uppercase; color:rgba(255,255,255,0.72); white-space:nowrap;">{DATELINE}</td>
      </tr></table>
      <p style="margin:17px 0 0; font-family:{SANS}; font-size:14.5px; line-height:1.55; color:rgba(255,255,255,0.92);">The wine world, summarized. Five stories per topic, the key facts pulled out, every link to the outlet that reported it. Read this and you are caught up.</p>
    </td></tr>

    <tr><td class="card-inner" style="padding:2px 38px 30px;">
      <table cellpadding="0" cellspacing="0" border="0" width="100%">
        {BRIEF}
        {WOTD}
        {CTA}
      </table>
    </td></tr>
  </table>
  {footer}
</td></tr></table>
</body></html>'''

FOOTER_KLAVIYO = f'''<table cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:600px;"><tr><td align="center" style="padding:22px 24px 8px;">
  <p style="margin:0 0 6px; font-family:{MONO}; font-size:10px; letter-spacing:0.06em; text-transform:uppercase; color:{META};">winefeed by Primal Wine</p>
  <p style="margin:0; font-family:{SANS}; font-size:11px; line-height:1.6; color:{META};">You are receiving this because you subscribed at winefeed.co.<br>{{{{ organization.address }}}} &middot; <a href="{{% unsubscribe %}}" style="color:{META};">Unsubscribe</a></p>
</td></tr></table>'''

FOOTER_PREVIEW = f'''<table cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:600px;"><tr><td align="center" style="padding:22px 24px 8px;">
  <p style="margin:0 0 6px; font-family:{MONO}; font-size:10px; letter-spacing:0.06em; text-transform:uppercase; color:{META};">winefeed by Primal Wine</p>
  <p style="margin:0; font-family:{SANS}; font-size:11px; line-height:1.6; color:{META};">You are receiving this because you subscribed at winefeed.co.<br>Primal Wine, Los Angeles CA &middot; <span style="color:{META};">Unsubscribe</span></p>
</td></tr></table>'''

open(os.path.expanduser("~/primal_claude/klaviyo/winefeed-daily-brief.html"), "w").write(page(FOOTER_KLAVIYO, WM_URL))
open(os.path.join(HERE, "winefeed-email-preview.html"), "w").write(page(FOOTER_PREVIEW, WM_DATA))

# content-only for the Artifact preview (strip doctype/html/head/body)
full = page(FOOTER_PREVIEW, WM_DATA)
style = re.search(r"<style>.*?</style>", full, re.S).group(0)
inner = re.search(r"<body>(.*)</body>", full, re.S).group(1)
open(os.path.join(HERE, "winefeed-email-artifact.html"), "w").write(
    "<title>winefeed daily brief — email</title>\n" + style + "\n" + inner)

print("wrote klaviyo template + preview + artifact")
print("date:", DATELINE, "| stories:", sum(len(ITEMS.get(t, [])) for t in TAB_ORDER))
