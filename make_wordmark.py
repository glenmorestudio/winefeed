# -*- coding: utf-8 -*-
"""Generate the 'winefeed' wordmark in Newsreader 400 as SVG (vector master) + PNG (for email)."""
import os
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from PIL import Image, ImageFont, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT = "winefeed"
INK = "#16181D"

font = TTFont(os.path.join(HERE, "font_newsreader.woff2"))
if "fvar" in font:
    present = {a.axisTag for a in font["fvar"].axes}
    pin = {}
    if "wght" in present: pin["wght"] = 400
    if "opsz" in present: pin["opsz"] = 24
    if pin:
        instancer.instantiateVariableFont(font, pin, inplace=True)

upm = font["head"].unitsPerEm
glyphset = font.getGlyphSet()
cmap = font.getBestCmap()
hmtx = font["hmtx"]

# compose outline path + bounds
spen = SVGPathPen(glyphset)
bpen = BoundsPen(glyphset)
x = 0
for ch in TEXT:
    g = cmap[ord(ch)]
    glyphset[g].draw(TransformPen(spen, (1, 0, 0, 1, x, 0)))
    glyphset[g].draw(TransformPen(bpen, (1, 0, 0, 1, x, 0)))
    x += hmtx[g][0]
xMin, yMin, xMax, yMax = bpen.bounds
W, H = xMax - xMin, yMax - yMin
d = spen.getCommands()

ttf_path = os.path.join(HERE, "_nr400.ttf")
font.flavor = None
font.save(ttf_path)
SIZE = 320  # high-res source
pf = ImageFont.truetype(ttf_path, SIZE)
tmp = Image.new("RGBA", (10, 10))
box = ImageDraw.Draw(tmp).textbbox((0, 0), TEXT, font=pf)
pad = 6

VARIANTS = [("", "#16181D", (22, 24, 29, 255)), ("-light", "#FFFFFF", (255, 255, 255, 255))]
for suf, hexcol, rgba in VARIANTS:
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.1f} {H:.1f}" '
           f'width="{W/upm*100:.1f}" height="{H/upm*100:.1f}" role="img" aria-label="winefeed">'
           f'<path transform="translate({-xMin:.1f},{yMax:.1f}) scale(1,-1)" d="{d}" fill="{hexcol}"/></svg>')
    open(os.path.join(HERE, f"wordmark{suf}.svg"), "w").write(svg)
    w, h = box[2] - box[0] + pad * 2, box[3] - box[1] + pad * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((pad - box[0], pad - box[1]), TEXT, font=pf, fill=rgba)
    img = img.crop(img.getbbox())
    img.save(os.path.join(HERE, f"wordmark{suf}.png"))

os.remove(ttf_path)
print("svg viewBox:", f"{W:.0f}x{H:.0f}", "| png px:", img.size, "| aspect:", round(img.size[0]/img.size[1], 3))
