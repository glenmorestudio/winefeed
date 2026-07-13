# -*- coding: utf-8 -*-
import html, datetime, re, os, json

_HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = open(os.path.join(_HERE, 'fonts.css')).read().strip()

# ---- real, sourced news data (from research agent; all real URLs) ----
DATA = {
    "MARKET": {
        "blurb": "Trade, prices, tariffs, and the business of wine.",
        "items": [
            ("The Drinks Business", "https://www.thedrinksbusiness.com/2026/07/h1-sees-disciplined-buyers-selective-demand-and-broadly-stable-prices-for-fine-wine/", "2026-07",
             "H1 2026: disciplined buyers, selective demand, broadly stable fine-wine prices",
             "WineCap's Q2 report describes a first half marked by cautious buyers, selective demand, and broadly stable secondary-market prices. Nine of the ten best-performing wines of the quarter were back-vintage Bordeaux, led by Chateau Climens 2012 (up about 66%)."),
            ("The Drinks Business", "https://www.thedrinksbusiness.com/2026/07/sothebys-to-hold-auction-dedicated-to-chateau-haut-brion/", "2026-07",
             "Sotheby's plans an ex-cellar auction dedicated to Chateau Haut-Brion",
             "Sotheby's, with Domaine Clarence Dillon, will hold an ex-cellar Haut-Brion auction in Paris on 1 October: 676 lots estimated at 2.5 to 3.5 million euros. Marking 90 years of Dillon ownership, it includes a barrel of the 2025 vintage, billed as the first barrel offered at a First Growth auction."),
            ("Meininger's", "https://www.winemag.it/en/european-wine-new-risk-of-us-tariffs-uswta-mobilizes-american-sellers/", "2026-07",
             "European wine faces fresh US tariff risk as importers mobilize",
             "European wine faces renewed tariff exposure tied to a USTR Section 301 review of trade practices across roughly 60 economies. The US Wine Trade Alliance rallied American importers to file comments before the 6 July deadline, warning of damage to both the US and EU wine sectors."),
            ("The Drinks Business", "https://www.thedrinksbusiness.com/2026/07/former-diageo-veteran-joins-terlato-wine-group/", "2026-07",
             "A former Diageo veteran joins Terlato Wine Group",
             "Terlato Wine Group has appointed a former Diageo executive to a senior role as the family-owned US importer strengthens its leadership team. The hire reflects continued executive movement across the drinks trade in 2026."),
            ("The Drinks Business", "https://www.thedrinksbusiness.com/2026/07/westgarth-wines-expands-fine-wine-business-into-europe-with-new-hire/", "2026-07",
             "Westgarth Wines expands its fine-wine business into Europe",
             "UK merchant Westgarth Wines is expanding onto the continent, backed by a new senior hire. The move signals continued appetite for cross-border growth in the fine-wine trade despite a cautious market."),
        ],
    },
    "CULTURE": {
        "blurb": "People, restaurants, and how the world drinks.",
        "items": [
            ("Wine Spectator", "https://www.winespectator.com/articles/wine-spectator-restaurant-awards-reveal-2026", "2026-06",
             "2026 Wine Spectator Restaurant Awards name over 4,000 winners",
             "Wine Spectator's 2026 Restaurant Awards recognized more than 4,000 wine programs worldwide. Two venues earned a first top-tier Grand Award: Berria Wine Bar in Madrid and Caruso's at Rosewood Miramar Beach in Montecito, the latter listing about 3,600 selections."),
            ("The Drinks Business", "https://www.thedrinksbusiness.com/2026/07/michelin-unveils-first-ever-burgundy-wine-rankings/", "2026-07",
             "Michelin unveils its first-ever wine rankings, starting in Burgundy",
             "The Michelin Guide published its first wine rating system, revealing the 2026 Grape Selection in Dijon. Nine Burgundy estates received the top three-grape distinction, with 94 producers recognized across the region."),
            ("Wine Industry Advisor", "https://wineindustryadvisor.com/2026/07/09/cotes-du-rhone-launches-refresh-your-wine/", "2026-07-09",
             "Cotes du Rhone launches a 'Refresh Your Wine' chilled-wine campaign",
             "The Cotes du Rhone AOC launched 'Refresh Your Wine,' a campaign for chilled wines aimed at drinkers aged 21 to 40. It positions the appellation's reds, whites, and roses for casual, contemporary, warm-weather occasions."),
            ("The Drinks Business", "https://www.thedrinksbusiness.com/2026/07/antinori-takes-helm-of-primum-familiae-vini/", "2026-07",
             "Alessia Antinori takes the helm of Primum Familiae Vini",
             "Primum Familiae Vini, the association of family-owned wineries, named Alessia Antinori president for the 2026 to 2027 term. She represents the 26th generation of the Antinori family and succeeds Prince Robert of Luxembourg."),
            ("The Drinks Business", "https://www.thedrinksbusiness.com/2026/06/muse-by-tom-aikens-launches-summer-wine-nights/", "2026-06",
             "Tom Aikens' Muse launches a summer of Tuesday wine nights",
             "Tom Aikens' 23-cover Belgravia restaurant Muse is running a weekly summer 'Tuesday Wine Nights' series, pairing his food with wines from around the world, led by head sommelier Elisa Marchini. The regular run begins 14 July with the Languedoc, after a launch dinner seating four female winemakers at the counter."),
        ],
    },
    "SCIENCE": {
        "blurb": "Climate, viticulture, sustainability, and health.",
        "items": [
            ("Frontiers in Climate", "https://www.frontiersin.org/news/2026/07/08/frontiers-climate-wine-growing-regions-california-under-climate-change-and-wildfires", "2026-07-08",
             "Warming and wildfire risk could redraw California's wine map",
             "A Frontiers in Climate study modeled 379 California sites and projected steep declines in grape suitability for Napa and Sonoma under high-emission scenarios, compounded by wildfire risk. Cooler coastal and northern areas such as Mendocino and Monterey are projected to gain suitability."),
            ("Canada's National Observer", "https://www.nationalobserver.com/2026/07/09/news/climate-adaptation-strategies-wine-market", "2026-07-09",
             "People will pay more for climate-proof wine, study finds",
             "New research weighed three strategies for winemakers on a warming planet: go, stay, or change. It found consumers are willing to pay more for climate-adapted wines, suggesting a market incentive for producers to adapt."),
            ("Wine Enthusiast", "https://www.wineenthusiast.com/culture/industry-news/new-alcohol-health-study-june-2026/", "2026-06",
             "Study finds no link between moderate drinking and cancer mortality",
             "A Journal of General Internal Medicine study using the REGARDS cohort found no association between moderate alcohol consumption and cancer mortality, with light drinkers showing lower cancer-death rates and heavy drinkers higher. The findings complicate blanket messaging that any amount raises cancer risk."),
            ("Harvard Gazette", "https://news.harvard.edu/gazette/story/2026/06/a-clearer-picture-of-drinking-and-disease/", "2026-06",
             "A clearer picture of drinking: 62 diseases fully attributable to alcohol",
             "A review in Addiction, covered by the Harvard Gazette, found 62 diseases are entirely attributable to alcohol, most tied to heavy drinking. The authors also reported that some alcohol-related damage can be slowed or reversed by cutting down or quitting."),
            ("Vino Joy News", "https://vino-joy.com/2026/07/10/frances-heatwave-cuts-wine-harvest-as-growers-brace-for-smaller-vintage/", "2026-07-10",
             "France's heatwave cuts the harvest as growers brace for a smaller vintage",
             "France's record June heatwave, which hit 44C and set a national record on 24 June, is stressing vines from Champagne to Bordeaux and advancing the 2026 harvest. Some growers reported heavy losses, including one Loire producer said to have lost about 40% of the crop to sunburn."),
        ],
    },
    "NEWSLETTERS": {
        "blurb": "Dispatches from independent wine writers and their Substacks.",
        "items": [
            ("wineanorak", "https://wineanorak.com/2026/07/09/champagne-perrier-jouet-have-implemented-regenerative-viticulture-in-half-of-their-vineyard-area-and-they-are-already-seeing-differences-in-the-base-wines/", "2026-07-09",
             "Perrier-Jouet is farming half its vineyards regeneratively, and it's changing the base wines",
             "Goode visits Perrier-Jouet's regenerative plots in Ambonnay, where a program running since 2021 now covers 33 of the house's 65 hectares. He reports measurable gains in soil structure, cover-crop nitrogen, and grape quality, plus more freshness and finesse in the base wines.",
             "Jamie Goode"),
            ("The Morning Claret", "https://themorningclaret.com/p/mountains-and-magliocco-casa-comerci", "2026-07-08",
             "Mountains and Magliocco",
             "Woolf reports from Calabria, exploring the region's mountainous terroir and the local Magliocco grape through producer Casa Comerci. The dispatch examines how altitude and place shape the character of southern Italian natural wine.",
             "Simon J. Woolf"),
            ("Everyday Drinking", "https://www.everydaydrinking.com/p/the-sysco-ification-of-wine", "2026-07-01",
             "The Sysco-ification of wine",
             "Wilson pushes back on wine culture's reflexive 'just drink what you like' ethos, arguing it has flattened taste and encouraged homogenized, industrially-styled bottles. He makes a case for critical re-engagement and for paying attention to who and what is behind the wine in your glass.",
             "Jason Wilson"),
            ("The Feiring Line", "https://feiring.substack.com/p/the-man-who-brought-you-bar-brutal", "2026-07-01",
             "The man who brought you Bar Brutal",
             "A profile of Stefano Colombo, whom Feiring frames as a game-changer of Barcelona's natural wine scene and the figure behind the influential Bar Brutal. The piece traces his role in shaping the city's drinking culture and the bar's wide-reaching aesthetic.",
             "Alice Feiring"),
            ("Not Drinking Poison", "https://notdrinkingpoison.substack.com/p/bruno-schueller-cant-we-try-to-work", "2026-05-27",
             "Bruno Schueller: can't we try to work less well?",
             "An interview with the Alsatian vigneron Bruno Schueller, known for imaginative, long-fermentation and oxidative natural wines. Schueller lays out his philosophy of working the vineyards less intensively while keeping the estate economically viable.",
             "Aaron Ayscough"),
        ],
    },
}

MONTHS = ["", "JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
MONTHS_FULL = ["", "JANUARY","FEBRUARY","MARCH","APRIL","MAY","JUNE","JULY","AUGUST","SEPTEMBER","OCTOBER","NOVEMBER","DECEMBER"]
WEEKDAYS = ["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"]

def fmt_date(s):
    parts = s.split("-")
    if len(parts) == 3:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        return f"{d} {MONTHS[m]} {y}"
    if len(parts) == 2:
        y, m = int(parts[0]), int(parts[1])
        return f"{MONTHS_FULL[m]} {y}"
    return s

def esc(t):
    return html.escape(t.replace("—", ", ").replace("–", "-"), quote=True)

# Optional live-data override written by update.py (feed_data.json in this dir).
# Keeps the static snapshot as the fallback when no feed data is present.
_OVERRIDE_DATE = None
_ov = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'feed_data.json')
if os.path.exists(_ov):
    _o = json.load(open(_ov))
    for _tab, _items in _o.get('items', {}).items():
        if _tab in DATA and _items:
            DATA[_tab]['items'] = [tuple(x) for x in _items]
    _OVERRIDE_DATE = _o.get('date')

# Today's dateline (computed, not fabricated)
today = datetime.date(2026, 7, 12)
if _OVERRIDE_DATE:
    _y, _m, _d = map(int, _OVERRIDE_DATE.split('-'))
    today = datetime.date(_y, _m, _d)
DATELINE = f"{WEEKDAYS[today.weekday()]} {today.day} {MONTHS_FULL[today.month]} {today.year}"

TAB_ORDER = ["MARKET", "CULTURE", "SCIENCE", "NEWSLETTERS"]

def build_tabs():
    out = []
    for i, name in enumerate(TAB_ORDER):
        sel = "true" if i == 0 else "false"
        act = " is-active" if i == 0 else ""
        out.append(
            f'<button class="tab{act}" role="tab" id="tab-{name.lower()}" '
            f'aria-selected="{sel}" aria-controls="panel-{name.lower()}" '
            f'data-panel="{name.lower()}" tabindex="{0 if i==0 else -1}">{name}</button>'
        )
    return "\n        ".join(out)

def build_panels():
    out = []
    for pi, name in enumerate(TAB_ORDER):
        d = DATA[name]
        hidden = "" if pi == 0 else " hidden"
        cards = []
        for idx, item in enumerate(d["items"], 1):
            src, url, date, head, summ = item[:5]
            author = item[5] if len(item) > 5 else None
            byline = f'<span class="dot">&middot;</span><span class="by">{esc(author)}</span>' if author else ''
            cards.append(f'''<article class="card" style="--i:{idx-1}">
            <div class="meta">
              <span class="idx">{idx:02d}</span>
              <span class="src">{esc(src)}</span>
              {byline}
              <span class="dot">&middot;</span>
              <time class="date">{esc(fmt_date(date))}</time>
            </div>''')
            cards[-1] += f'''
            <h3 class="head"><a href="{esc(url)}" target="_blank" rel="noopener">{esc(head)}</a></h3>
            <p class="summary">{esc(summ)}</p>
            <a class="read" href="{esc(url)}" target="_blank" rel="noopener">Read the full story <span class="read-arrow" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg></span></a>
          </article>'''
        panel = f'''<section class="panel{'' if pi==0 else ' '}" role="tabpanel" id="panel-{name.lower()}" aria-labelledby="tab-{name.lower()}"{hidden}>
          <p class="panel-blurb">{esc(d["blurb"])}</p>
          {"".join(cards)}
        </section>'''
        out.append(panel)
    return "\n        ".join(out)

STYLE = '''
<style>
''' + FONTS + '''
*,*::before,*::after{box-sizing:border-box;}
:root{
  --paper:#FBFBFA; --raise:#F1F2F4; --ink:#16181D; --body:#3A3D44; --meta:#6B6F78;
  --faint:#A6A9B1; --line:#E6E7EA; --line-2:#DADCE0; --accent:#2743C9; --accent-hover:#1B33A6;
  --radius:0px;
  --ease-out:cubic-bezier(0.23,1,0.32,1);
  --serif: 'Geist', system-ui, sans-serif;
  --mono: 'Geist Mono', ui-monospace, monospace;
  --display: 'Newsreader', Georgia, serif;
}
@media (prefers-color-scheme: dark){
  :root{
    --paper:#0F1113; --raise:#171A1E; --ink:#E8EAEE; --body:#C2C6CE; --meta:#8B9099;
    --faint:#565B63; --line:#22262B; --line-2:#2D3239; --accent:#8AA6FF; --accent-hover:#A6BCFF;
  }
}
:root[data-theme="light"]{
  --paper:#FBFBFA; --raise:#F1F2F4; --ink:#16181D; --body:#3A3D44; --meta:#6B6F78;
  --faint:#A6A9B1; --line:#E6E7EA; --line-2:#DADCE0; --accent:#2743C9; --accent-hover:#1B33A6;
}
:root[data-theme="dark"]{
  --paper:#0F1113; --raise:#171A1E; --ink:#E8EAEE; --body:#C2C6CE; --meta:#8B9099;
  --faint:#565B63; --line:#22262B; --line-2:#2D3239; --accent:#8AA6FF; --accent-hover:#A6BCFF;
}
html{-webkit-text-size-adjust:100%;}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:var(--serif); font-size:16px; line-height:1.6;
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
  font-feature-settings:"ss01","cv01";
}
/* ---------- framed column ---------- */
.frame{
  max-width:642px; margin:0 auto; min-height:100dvh;
  border-left:1px solid var(--line); border-right:1px solid var(--line);
}
.pad{padding-left:38px; padding-right:38px;}

/* ---------- header ---------- */
.masthead{padding-top:50px;}
.mast-top{display:flex; align-items:center; justify-content:space-between; gap:16px;}
.wordmark{
  font-family:var(--display); font-weight:500; font-size:34px; letter-spacing:-0.012em;
  color:var(--ink); margin:0; line-height:1;
}
.wordmark .dropchar{color:var(--ink);}
.theme-toggle{
  display:inline-flex; align-items:center; justify-content:center; flex:0 0 auto;
  width:30px; height:30px; padding:0; color:var(--meta);
  background:none; border:0; cursor:pointer;
  transition:transform 260ms var(--ease-out), color 160ms ease;
}
.theme-toggle svg{width:19px; height:19px; display:block;}
.theme-toggle:hover{color:var(--ink);}
.theme-toggle:active{transform:scale(0.9);}
.theme-toggle:focus-visible{outline:2px solid var(--accent); outline-offset:3px; border-radius:999px;}
.tagline{
  margin:20px 0 0; max-width:none; color:var(--body); font-size:15.5px; line-height:1.55;
  text-wrap:balance;
}
.dateline{
  margin:22px 0 22px; font-family:var(--mono); font-size:11px; letter-spacing:0.13em;
  text-transform:uppercase; color:var(--meta); display:flex; align-items:center; gap:12px;
}
.dateline::after{content:""; flex:1; height:1px; background:var(--line);}

/* ---------- concave folder tabs ---------- */
/* active tab's outline flares into the feed panel with a Chrome-style concave curve
   on each side; each connector paints the transparent notch, the grey arc, and the
   paper fill in one radial-gradient. gap == connector radius so flares sit in the gaps. */
.tabs-outer{
  position:sticky; top:0; z-index:20; background:var(--paper);
  border-bottom:1px solid var(--line);
}
.tablist{
  position:relative; z-index:2; display:grid; grid-template-columns:repeat(4,1fr);
  gap:10px; padding-top:18px;
}
.tab{
  position:relative; display:flex; align-items:center; justify-content:center;
  padding:12px 10px 13px; cursor:pointer; text-align:center; margin-bottom:-1px;
  border:1px solid var(--line); border-bottom:0; border-radius:10px 10px 0 0;
  background:var(--raise); color:var(--meta);
  font-family:var(--mono); font-size:11.5px; font-weight:400; letter-spacing:0.07em; text-transform:uppercase;
  white-space:nowrap; transition:background 180ms ease, color 180ms ease;
}
.tab:hover:not(.is-active){background:var(--line); color:var(--ink);}
.tab.is-active{
  background:var(--paper); color:var(--ink); z-index:1;
  box-shadow:inset 0 2px 0 0 var(--accent);
}
.tab:active{color:var(--ink);}
.tab:focus-visible{outline:2px solid var(--accent); outline-offset:-4px; border-radius:6px;}
/* bordered concave connectors */
.tab.is-active::before,.tab.is-active::after{content:""; position:absolute; bottom:-1px; width:10px; height:11px; z-index:1;}
.tab.is-active::before{left:-10px; background:radial-gradient(circle at 0 0,#0000 9px,var(--line) 9px 10px,var(--paper) 10px);}
.tab.is-active::after{right:-10px; background:radial-gradient(circle at 100% 0,#0000 9px,var(--line) 9px 10px,var(--paper) 10px);}

/* ---------- panels / cards ---------- */
.panel[hidden]{display:none;}
.panel-blurb{
  font-family:var(--serif); font-size:15px; font-weight:400; letter-spacing:0; text-transform:none;
  color:var(--meta); margin:0; padding:20px 0 18px; line-height:1.5;
  border-bottom:1px solid var(--line); text-wrap:pretty;
}
.card{
  padding:30px 0 4px; border-top:1px solid var(--line);
  animation:rise 440ms var(--ease-out) both; animation-delay:calc(var(--i) * 55ms);
}
.card:first-of-type{border-top:0; padding-top:26px;}
@keyframes rise{from{opacity:0; transform:translateY(8px);} to{opacity:1; transform:translateY(0);}}
.meta{
  display:flex; align-items:center; flex-wrap:wrap; gap:9px; font-family:var(--mono); font-size:10.5px;
  letter-spacing:0.09em; text-transform:uppercase; color:var(--meta); margin-bottom:12px;
}
.idx{color:var(--accent);}
.src{color:var(--ink);}
.by{color:var(--meta);}
.dot{color:var(--faint);}
.date{color:var(--meta); font-variant-numeric:tabular-nums;}
.head{margin:0 0 10px; font-size:19px; line-height:1.36; font-weight:400; letter-spacing:-0.006em; text-wrap:balance;}
.head a{color:var(--ink); text-decoration:none; background-image:linear-gradient(var(--accent),var(--accent)); background-size:0% 1.5px; background-repeat:no-repeat; background-position:0 100%; transition:background-size 260ms var(--ease-out), color 180ms ease;}
.head a:hover{color:var(--accent); background-size:100% 1.5px;}
.summary{margin:0 0 16px; color:var(--body); font-size:15.75px; line-height:1.62; text-wrap:pretty;}
.read{
  display:inline-flex; align-items:center; gap:7px; font-family:var(--mono); font-size:10.5px;
  letter-spacing:0.09em; text-transform:uppercase; color:var(--meta); text-decoration:none;
  transition:color 180ms ease;
}
.read-arrow{display:inline-flex; transition:transform 200ms var(--ease-out);}
.read-arrow svg{width:14px; height:14px; display:block;}
.read:hover{color:var(--accent);}
.read:hover .read-arrow{transform:translateX(4px);}
a:focus-visible{outline:2px solid var(--accent); outline-offset:3px; border-radius:2px;}

/* ---------- footer ---------- */
.foot{margin-top:42px; padding-bottom:54px; color:var(--meta);}
.foot-box{border:1px solid var(--line); border-radius:14px; padding:22px 24px;}
.foot p{margin:0 0 10px; font-size:13.5px; line-height:1.6; max-width:52ch;}
.foot .fine{font-family:var(--mono); font-size:10.5px; letter-spacing:0.07em; text-transform:uppercase; color:var(--faint);}
.foot a{color:var(--meta); text-decoration:none; border-bottom:1px solid var(--line-2); transition:color 160ms ease, border-color 160ms ease;}
.foot a:hover{color:var(--accent); border-color:var(--accent);}

@media (max-width:520px){
  .pad{padding-left:22px; padding-right:22px;}
  .frame{border-left:0; border-right:0;}
  .masthead{padding-top:38px;} .wordmark{font-size:29px;} .head{font-size:18px;}
  .tablist{gap:6px;}
  .tab{font-size:9.5px; letter-spacing:0.02em; padding:10px 3px 11px; border-radius:8px 8px 0 0;}
  .tab.is-active::before,.tab.is-active::after{display:none;}
}
@media (prefers-reduced-motion: reduce){
  *{animation-duration:0.001ms !important; transition-duration:0.001ms !important;}
  .card{animation:none;}
}
</style>'''

BODY = f'''<div class="frame">
      <header class="masthead pad">
        <div class="mast-top">
          <h1 class="wordmark">wine<span class="dropchar">feed</span></h1>
          <button class="theme-toggle" id="themeToggle" type="button" aria-label="Toggle light or dark theme" title="Toggle theme">
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.25" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M12 2.75 A9.25 9.25 0 0 1 12 21.25 Z" fill="currentColor"/></svg>
          </button>
        </div>
        <p class="tagline">A daily digest of the wine world, summarized in plain language. Five stories per topic. Every link goes to the outlet that reported it.</p>
        <p class="dateline">{DATELINE}</p>
      </header>

      <nav class="tabs-outer" aria-label="Topics">
        <div class="tablist pad" role="tablist">
          {build_tabs()}
        </div>
      </nav>

      <main>
        <div id="panels" class="pad">
          {build_panels()}
        </div>

        <footer class="foot pad">
          <div class="foot-box">
            <p>Winefeed summarizes reporting from independent wine journalists and trade publications. We do not republish full articles. Read a summary, then click through and support the writers doing the work.</p>
            <p class="fine">Made by Guido Cattabianchi &middot; <a href="mailto:guido.catta@gmail.com">guido.catta@gmail.com</a></p>
          </div>
        </footer>
      </main>
    </div>

    <script>
    (function(){{
      var root = document.documentElement;
      // theme
      var toggle = document.getElementById('themeToggle');
      function current(){{
        var set = root.getAttribute('data-theme');
        if(set) return set;
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }}
      try{{ var saved = localStorage.getItem('winefeed-theme'); if(saved) root.setAttribute('data-theme', saved); }}catch(e){{}}
      toggle.addEventListener('click', function(){{
        var next = current() === 'dark' ? 'light' : 'dark';
        root.setAttribute('data-theme', next);
        try{{ localStorage.setItem('winefeed-theme', next); }}catch(e){{}}
      }});

      // tabs
      var tabs = Array.prototype.slice.call(document.querySelectorAll('.tab'));
      var panels = {{}};
      tabs.forEach(function(t){{ panels[t.dataset.panel] = document.getElementById('panel-' + t.dataset.panel); }});

      function activate(tab, focus){{
        tabs.forEach(function(t){{
          var on = t === tab;
          t.classList.toggle('is-active', on);
          t.setAttribute('aria-selected', on ? 'true' : 'false');
          t.tabIndex = on ? 0 : -1;
          panels[t.dataset.panel].hidden = !on;
        }});
        // retrigger stagger animation
        var p = panels[tab.dataset.panel];
        p.querySelectorAll('.card').forEach(function(c){{
          c.style.animation = 'none'; void c.offsetWidth; c.style.animation = '';
        }});
        if(focus) tab.focus();
      }}
      tabs.forEach(function(tab){{
        tab.addEventListener('click', function(){{ activate(tab, false); }});
        tab.addEventListener('keydown', function(e){{
          var i = tabs.indexOf(tab);
          if(e.key === 'ArrowRight' || e.key === 'ArrowDown'){{ e.preventDefault(); activate(tabs[(i+1)%tabs.length], true); }}
          else if(e.key === 'ArrowLeft' || e.key === 'ArrowUp'){{ e.preventDefault(); activate(tabs[(i-1+tabs.length)%tabs.length], true); }}
          else if(e.key === 'Home'){{ e.preventDefault(); activate(tabs[0], true); }}
          else if(e.key === 'End'){{ e.preventDefault(); activate(tabs[tabs.length-1], true); }}
        }});
      }});
    }})();
    </script>'''

# ---- Artifact version (content only; host wraps in doctype/head/body) ----
artifact = f'<title>Winefeed — a daily wine-news digest</title>\n{STYLE}\n{BODY}\n'
open(os.path.join(_HERE, 'winefeed_artifact.html'),'w').write(artifact)

# ---- Standalone version for GoDaddy ----
standalone = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Winefeed — a daily wine-news digest</title>
<meta name="description" content="A daily digest of the wine world, summarized. Five stories each across Market, Regions, Culture, and Science. Every link goes to the original source.">
<meta name="author" content="Guido Cattabianchi">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22%3E%3Ctext y=%22.9em%22 font-size=%2290%22%3E%F0%9F%8D%B7%3C/text%3E%3C/svg%3E">
{STYLE}
</head>
<body>
{BODY}
</body>
</html>
'''
open(os.path.join(_HERE, 'index.html'),'w').write(standalone)

print("Dateline:", DATELINE)
print("artifact bytes:", len(artifact))
print("standalone bytes:", len(standalone))
