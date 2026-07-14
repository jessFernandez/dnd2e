"""Generate the app icon (assets/dnd2e.ico) — tracked generator, safe to re-run.

Draws the icon in the app's own palette (dark navy medallion, gold accent) with
thin gold corner brackets echoing the splash frame, supersampled for clean edges,
then packs the standard Windows sizes into a multi-resolution .ico. Run from the
repo root:

    python scripts/build_icon.py                 # build the chosen design
    python scripts/build_icon.py --design book    # override which motif
    python scripts/build_icon.py --previews DIR   # dump all candidates to DIR

Pillow is the only dependency (already in requirements via the scraper deps).
"""
import argparse
import math
import os

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ICO = os.path.join(REPO, "assets", "dnd2e.ico")
OUT_PNG = os.path.join(REPO, "assets", "dnd2e.png")  # for the in-app window icon

# Which motif ships. Change this (or pass --design) once a look is chosen.
CHOSEN = "ampersand"

# ── Palette (matches app.py / splash_html.py) ─────────────────────────────────
BG_TOP = (28, 31, 48)        # navy, top of medallion gradient (#1c1f30)
BG_BOT = (14, 15, 22)        # near-black navy, bottom (#0e0f16)
GOLD = (201, 168, 76)        # the app's signature accent (#c9a84c)
GOLD_LIGHT = (232, 205, 130)  # lit gold
GOLD_DARK = (150, 118, 44)   # shaded gold
BRONZE = (74, 60, 16)        # deep bronze (corner-bracket / spine shadow, #4a3c10)
PARCH_LIGHT = (232, 220, 174)  # lit parchment (book pages)
PARCH_DARK = (206, 186, 132)   # shaded parchment
INK = (40, 33, 12)           # dark accents on gold

S = 1024          # supersampled master size


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def vertical_gradient(size, top, bot):
    grad = Image.new("RGB", (1, size), 0)
    for y in range(size):
        grad.putpixel((0, y), lerp(top, bot, y / (size - 1)))
    return grad.resize((size, size))


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1],
                                        radius=radius, fill=255)
    return m


def load_font(px, bold=True):
    names = (("georgiab.ttf", "timesbd.ttf", "arialbd.ttf") if bold
             else ("georgia.ttf", "times.ttf", "arial.ttf"))
    for name in names:
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


def medallion(size):
    """Navy rounded-square base with thin gold corner brackets."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    radius = int(size * 0.22)
    grad = vertical_gradient(size, BG_TOP, BG_BOT).convert("RGBA")
    img.paste(grad, (0, 0), rounded_mask(size, radius))

    d = ImageDraw.Draw(img)
    # Faint gold hairline border.
    d.rounded_rectangle([int(size * 0.045)] * 1 + [int(size * 0.045),
                        size - 1 - int(size * 0.045), size - 1 - int(size * 0.045)],
                        radius=int(radius * 0.8), outline=(*GOLD, 60),
                        width=max(1, int(size * 0.006)))

    # Corner brackets (L-shapes), echoing the splash frame.
    w = max(2, int(size * 0.022))          # stroke width
    ln = int(size * 0.15)                  # arm length
    off = int(size * 0.11)                 # inset from edge
    lo, hi = off, size - 1 - off
    for (cx, cy, dx, dy) in [(lo, lo, 1, 1), (hi, lo, -1, 1),
                             (lo, hi, 1, -1), (hi, hi, -1, -1)]:
        d.line([(cx, cy), (cx + dx * ln, cy)], fill=GOLD, width=w)
        d.line([(cx, cy), (cx, cy + dy * ln)], fill=GOLD, width=w)
    return img


def _gold_text(d, xy, text, font, size):
    """Draw text with a soft dark drop shadow and a gold gradient fill fake
    (top-lit) by layering a lighter glyph slightly above a darker one."""
    x, y = xy
    off = max(1, int(size * 0.012))
    d.text((x + off, y + off), text, font=font, fill=(*INK, 180), anchor="mm")
    d.text((x, y + off), text, font=font, fill=GOLD_DARK, anchor="mm")
    d.text((x, y), text, font=font, fill=GOLD, anchor="mm")
    d.text((x, y - off), text, font=font, fill=GOLD_LIGHT, anchor="mm")
    d.text((x, y), text, font=font, fill=GOLD, anchor="mm")


# ── Motifs ────────────────────────────────────────────────────────────────────

def draw_monogram(img, size):
    d = ImageDraw.Draw(img)
    font = load_font(int(size * 0.46))
    _gold_text(d, (size / 2, size * 0.50), "2e", font, size)


def draw_ampersand(img, size):
    d = ImageDraw.Draw(img)
    font = load_font(int(size * 0.60))
    _gold_text(d, (size / 2, size * 0.49), "&", font, size)


def draw_book(img, size):
    d = ImageDraw.Draw(img)
    cx, cy = size / 2, size / 2 + size * 0.01
    bw, bh = size * 0.60, size * 0.44

    def L(fx, fy):
        return (cx + fx * bw, cy + fy * bh)

    spine_top = L(0, -0.42)
    spine_bot = L(0, 0.48)
    # Left / right page quads (fold high in the middle, draping to the sides).
    left = [spine_top, L(-0.50, -0.14), L(-0.50, 0.36), spine_bot]
    right = [spine_top, L(0.50, -0.14), L(0.50, 0.36), spine_bot]

    d.polygon(left, fill=PARCH_DARK)
    d.polygon(right, fill=PARCH_LIGHT)

    edge = max(2, int(size * 0.012))
    d.line(left + [left[0]], fill=GOLD_DARK, width=edge, joint="curve")
    d.line(right + [right[0]], fill=GOLD, width=edge, joint="curve")
    # Spine.
    d.line([spine_top, spine_bot], fill=BRONZE, width=max(3, int(size * 0.02)))

    # A few text lines on each page.
    lw = max(1, int(size * 0.008))
    for i, t in enumerate((0.05, 0.30, 0.55)):
        yl = -0.02 + t
        d.line([L(-0.40, yl - 0.06), L(-0.08, yl - 0.02)], fill=GOLD_DARK, width=lw)
        d.line([L(0.08, yl - 0.02), L(0.40, yl - 0.06)], fill=(*GOLD_DARK, 200), width=lw)

    # Small gold bookmark ribbon.
    rb = [L(0.14, 0.30), L(0.22, 0.30), L(0.22, 0.62), L(0.18, 0.55), L(0.14, 0.62)]
    d.polygon(rb, fill=GOLD_LIGHT)


DESIGNS = {
    "monogram": draw_monogram,
    "book": draw_book,
    "ampersand": draw_ampersand,
}


def render(design, size=S):
    img = medallion(size)
    DESIGNS[design](img, size)
    return img


def _save_ico(master, path):
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [master.resize((s, s), Image.LANCZOS) for s in sizes]
    frames[0].save(path, format="ICO", sizes=[(s, s) for s in sizes])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", choices=list(DESIGNS), default=CHOSEN)
    ap.add_argument("--previews", metavar="DIR",
                    help="render every candidate to DIR and exit")
    args = ap.parse_args()

    if args.previews:
        os.makedirs(args.previews, exist_ok=True)
        for name in DESIGNS:
            p = os.path.join(args.previews, f"icon_{name}.png")
            render(name, S).resize((256, 256), Image.LANCZOS).save(p)
            print(f"wrote {p}")
        return

    os.makedirs(os.path.join(REPO, "assets"), exist_ok=True)
    master = render(args.design, S)
    _save_ico(master, OUT_ICO)
    master.resize((256, 256), Image.LANCZOS).save(OUT_PNG)
    print(f"wrote {OUT_ICO} ({args.design})")
    print(f"wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
