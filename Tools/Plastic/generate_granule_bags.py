"""Draw all eight plastic resource textures as 256x256 anti-aliased RGBA.

Requires Python 3.13+ and Pillow 11+. Self-contained: no historical script,
external image or font is read. Fixed seeds make every run identical.

Granules: _a/_b/_c sealed pellet pouches, _d an open tote of pellets.
Sheets:   _a loose film sheets, _b a sheet stack, _c a half-used roll,
          _d a large wound roll.

Geometry lives in a 64-unit design space, supersampled 32x (2048 px) and
Lanczos-downsampled to 256 px. Each silhouette is grown by a round (not
square) dilation into a pure black contour; colour and alpha are resampled
separately, so every pixel with 0 < alpha < 255 is pure black and RimWorld's
cutout or UI blending cannot produce a light halo.
"""

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
RESOURCE = ROOT / "Textures/Things/Item/Resource"
SIZE = 256  # output pixels
DESIGN = 64  # design units across the canvas
SS = 32  # supersampled pixels per design unit
N = DESIGN * SS  # 2048 px working canvas
INK = (0, 0, 0)
FAMILIES = ("PlasticGranule", "PlasticSheet")
TIERS = "abcd"

# pk-gpt palette (tote and sheets)
CREAM = (219, 229, 223)
LIGHT = (246, 247, 232)
MID = (180, 202, 199)
GAP = (22, 31, 31)  # shadow between pellets inside the tote

# original-generator palette (half-used roll)
PLASTIC_HI = (248, 251, 252)
PLASTIC_TOP = (228, 238, 241)
PLASTIC_BOT = (184, 201, 209)
SHEET_FRONT_HI = (244, 249, 250)
SHEET_BACK = (198, 211, 215)


# --------------------------------------------------------------- geometry
def compose(m, n):
    """Affine m after n; each is (a, b, c, d, e, f): x' = ax+by+c, y' = dx+ey+f."""
    a, b, c, d, e, f = m
    p, q, r, s, t, u = n
    return (
        a * p + b * s,
        a * q + b * t,
        a * r + b * u + c,
        d * p + e * s,
        d * q + e * t,
        d * r + e * u + f,
    )


def translate(x, y):
    return (1, 0, x, 0, 1, y)


def scaling(k):
    return (k, 0, 0, 0, k, 0)


def rotation(degrees):
    """Screen-space rotation (y down); positive turns clockwise."""
    r = math.radians(degrees)
    return (math.cos(r), -math.sin(r), 0, math.sin(r), math.cos(r), 0)


IDENTITY = (1, 0, 0, 0, 1, 0)


def ellipse_points(box, steps=72, start=0.0, end=360.0):
    x0, y0, x1, y1 = box
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    pts = []
    for i in range(steps + 1):
        t = math.radians(start + (end - start) * i / steps)
        pts.append((cx + rx * math.cos(t), cy + ry * math.sin(t)))
    return pts if end - start < 360 else pts[:-1]


def diag_ramp(w, h):
    """0 at top-left, 255 at bottom-right (key light from the upper left)."""
    base = Image.linear_gradient("L")
    v = base.resize((w, h), Image.Resampling.BILINEAR)
    u = base.transpose(Image.Transpose.TRANSPOSE).resize(
        (w, h), Image.Resampling.BILINEAR
    )
    return ImageChops.add(v.point(lambda p: p // 2), u.point(lambda p: p // 2))


def dilate(mask, radius_px):
    """Round dilation: union of the mask shifted around a circle."""
    if radius_px < 0.5:
        return mask
    out = mask.copy()
    steps = max(24, round(math.tau * radius_px / 2.5))
    seen = set()
    for i in range(steps):
        t = math.tau * i / steps
        dx, dy = round(radius_px * math.cos(t)), round(radius_px * math.sin(t))
        if (dx, dy) in seen:
            continue
        seen.add((dx, dy))
        out = ImageChops.lighter(out, ImageChops.offset(mask, dx, dy))
    return out


def rgb(c):
    return tuple(c[:3])


class Pen:
    """Draws design-unit geometry, through an affine transform, on one layer."""

    def __init__(self, image, matrix=IDENTITY):
        self.image = image
        self.matrix = matrix
        self.draw = ImageDraw.Draw(image)
        a, b, _, d, e, _ = matrix
        self.k = math.sqrt(abs(a * e - b * d))

    def sub(self, matrix):
        return Pen(self.image, compose(self.matrix, matrix))

    def layer(self):
        return Pen(Image.new("RGBA", (N, N)), self.matrix)

    def map(self, pts):
        a, b, c, d, e, f = self.matrix
        return [((a * x + b * y + c) * SS, (d * x + e * y + f) * SS) for x, y in pts]

    def poly(self, pts, fill):
        self.draw.polygon(self.map(pts), fill=rgb(fill) + (255,))

    def line(self, pts, fill, width, screen=False):
        px = width * SS * (1 if screen else self.k)
        self.draw.line(
            self.map(pts),
            fill=rgb(fill) + (255,),
            width=max(1, round(px)),
            joint="curve",
        )

    def ellipse(self, box, fill=None, outline=None, width=0.5):
        if fill is not None:
            self.poly(ellipse_points(box), fill)
        if outline is not None:
            self.ring(box, outline, width)

    def ring(self, box, colour, width):
        h = width / 2
        inset = (box[0] + h, box[1] + h, box[2] - h, box[3] - h)
        pts = ellipse_points(inset)
        self.line(pts + pts[:2], colour, width)

    def arc(self, box, start, end, colour, width):
        h = width / 2
        inset = (box[0] + h, box[1] + h, box[2] - h, box[3] - h)
        self.line(ellipse_points(inset, 48, start, end), colour, width)

    def grad_poly(self, pts, c_tl, c_br, outline=None, width=0.9):
        screen = self.map(pts)
        x0 = math.floor(min(p[0] for p in screen))
        y0 = math.floor(min(p[1] for p in screen))
        x1 = math.ceil(max(p[0] for p in screen)) + 1
        y1 = math.ceil(max(p[1] for p in screen)) + 1
        w, h = x1 - x0, y1 - y0
        mask = Image.new("L", (w, h))
        ImageDraw.Draw(mask).polygon([(x - x0, y - y0) for x, y in screen], fill=255)
        grad = Image.composite(
            Image.new("RGBA", (w, h), rgb(c_br) + (255,)),
            Image.new("RGBA", (w, h), rgb(c_tl) + (255,)),
            diag_ramp(w, h),
        )
        self.image.paste(grad, (x0, y0), mask)
        if outline is not None:
            self.line(pts + pts[:2], outline, width)

    def grad_ellipse(self, box, c_tl, c_br, outline=None, width=0.9):
        self.grad_poly(ellipse_points(box), c_tl, c_br)
        if outline is not None:
            self.ring(box, outline, width)

    def exterior(self, layer, radius):
        """Composite `layer` with a black contour grown around its alpha."""
        grown = dilate(layer.image.getchannel("A"), radius * self.k * SS)
        ink = Image.new("RGBA", (N, N), INK + (255,))
        ink.putalpha(grown)
        ink.alpha_composite(layer.image)
        self.image.alpha_composite(ink)


# --------------------------------------------------------------- granules
def pouch(pen, center, scale=1.0, angle=0, seed=1, shade=1.0):
    """One flexible pellet pouch, nominally 16 x 23 design units.

    All sizes share the same seal and folds. Bigger bags contain more pellets,
    rather than making the pellets themselves 1.6 times larger.
    """
    bag = pen.layer()
    p = bag.sub(compose(translate(*center), compose(rotation(angle), scaling(scale))))

    def colour(c):
        return tuple(round(v * shade) for v in c)

    def polygon(pts, c):
        p.poly(pts, colour(c))

    def line(pts, c, width=0.5):
        p.line(pts, colour(c), width)

    # Slightly kinked edges, pinched weld and a soft gusseted bottom, not a jar.
    outline = [
        (-6.8, -10.4),
        (6.1, -10.7),
        (6.3, -7.7),
        (5.7, -5.8),
        (7.1, -1.6),
        (7.3, 6.8),
        (5.8, 9.5),
        (1.6, 10.2),
        (-5.5, 9.3),
        (-7.2, 7.0),
        (-6.7, 1.0),
        (-6.0, -5.6),
        (-6.8, -7.8),
    ]
    polygon(outline, (198, 221, 222))
    polygon(
        [
            (-6.0, -7.4),
            (5.4, -7.6),
            (5.1, -4),
            (6.4, 6.8),
            (4.8, 8.5),
            (-5.3, 8),
            (-5.6, 0),
        ],
        (218, 234, 231),
    )
    polygon(
        [
            (4.1, -5.7),
            (5.7, -5.8),
            (7.1, -1.6),
            (7.3, 6.8),
            (5.8, 9.5),
            (0.8, 10),
            (3.8, 7.5),
            (5.3, 3),
        ],
        (157, 190, 193),
    )
    # Pellets fill the lower body; a clear headspace separates them from seal.
    polygon(
        [
            (-5.0, -1.8),
            (-1.6, -3.3),
            (2.8, -2.7),
            (5.4, -1),
            (5.7, 6.6),
            (3.9, 8),
            (-4.9, 7.5),
            (-5.7, 5),
        ],
        (158, 183, 178),
    )
    rng = random.Random(seed)
    rows, cols = (4, 4) if scale == 1 else (6, 6)
    for row in range(rows):
        for col in range(cols):
            x = -4.1 + col * 8.1 / (cols - 1) + rng.uniform(-0.23, 0.23)
            y = -1.4 + row * 7.5 / (rows - 1) + rng.uniform(-0.3, 0.3)
            rx, ry = rng.uniform(1.0, 1.18) / scale, rng.uniform(0.65, 0.82) / scale
            pellet = [
                (
                    x + rx * math.cos(t * math.tau / 24),
                    y + ry * math.sin(t * math.tau / 24),
                )
                for t in range(24)
            ]
            polygon(pellet, (215, 227, 215))
            line(pellet[:13], (133, 161, 156), 0.22 / scale)
            line(
                [(x - rx * 0.6, y - ry * 0.4), (x + rx * 0.15, y - ry * 0.5)],
                (248, 249, 232),
                0.45 / scale,
            )
    # Two pressure seams with a bright film strip between, no open mouth.
    line([(-6.1, -9.3), (5.5, -9.6)], (253, 255, 247), 0.65)
    line([(-6.0, -8.5), (5.5, -8.8)], (84, 117, 119), 0.55)
    line([(-5.9, -7.2), (5.5, -7.5)], (89, 123, 124), 0.55)
    # Edge welds and diagonal glints cross the contents to read as clear film.
    line([(-5.6, -5.8), (-5.9, 1.1), (-6.0, 6.3), (-4.5, 8.0)], (247, 253, 242), 0.65)
    line([(5.0, -5.0), (6.0, 1.0), (6.1, 6.1)], (208, 231, 229), 0.45)
    line([(-4.4, -4.6), (-1.1, -5.2), (0.9, -4.9)], (253, 255, 246), 0.6)
    line([(-4.7, 0.3), (-3.8, 2.1), (-3.5, 4.7)], (245, 251, 237), 0.55)
    line([(-4.7, 8.0), (-1.0, 8.8), (3.8, 8.3)], (230, 244, 229), 0.5)
    line([(-6.7, 6.8), (-4.5, 5.7)], (103, 143, 146), 0.45)
    line([(5.9, 7.1), (4.1, 5.6)], (101, 140, 143), 0.45)
    # Constant screen-space contour: small bags stay bold, big ones supple.
    p.line(outline + outline[:2], INK, POUCH_CONTOUR, screen=True)
    pen.image.alpha_composite(bag.image)


POUCH_CONTOUR = 0.9


def granule_a(pen):
    pouch(pen, (32, 32), angle=-7, seed=101)


def granule_b(pen):
    # Identical small-bag geometry; only placement, angle and contents change.
    pouch(pen, (24, 28), angle=-18, seed=102, shade=0.96)
    pouch(pen, (39, 29), angle=14, seed=103, shade=0.98)
    pouch(pen, (31, 39), angle=-6, seed=101)


def granule_c(pen):
    # Bottom -> top: visible offset seams, side folds and lower gussets.
    pouch(pen, (36, 28), scale=1.6, angle=12, seed=201, shade=0.90)
    pouch(pen, (25, 32), scale=1.6, angle=-18, seed=202, shade=0.95)
    pouch(pen, (34, 35), scale=1.6, angle=-7, seed=203)


def grain(pen, x, y, rx=1.8, ry=1.25, angle=0, tint=0):
    """An opaque pellet: upper-left glint, right/bottom shaded lip."""
    pts = []
    for n in range(32):
        t = n * math.tau / 32
        u, v = math.cos(t) * rx, math.sin(t) * ry
        pts.append(
            (
                x + u * math.cos(angle) - v * math.sin(angle),
                y + u * math.sin(angle) + v * math.cos(angle),
            )
        )
    pen.poly(pts, (209 + tint, 222 + tint, 216 + tint))
    pen.line(pts[0:17], (112, 137, 135), 0.45)
    pen.ellipse((x - rx * 0.65, y - ry * 0.65, x + 0.15, y + 0.1), LIGHT)
    pen.line(
        [pts[i % 32] for i in (0, 31, 29, 27, 25, 23, 21, 20)], (110, 137, 137), 0.45
    )


def granule_d(pen):
    # An open rectangular food-grade tote, viewed from above and the front.
    pen.poly([(9, 20), (37, 10), (55, 21), (53, 46), (28, 54), (11, 44)], MID)
    pen.poly([(10, 21), (28, 32), (28, 53), (12, 44)], (188, 209, 205))
    pen.poly([(28, 32), (55, 22), (53, 46), (28, 54)], (147, 176, 177))
    # Pellets are clipped to the inside of the rim, over a dark gap colour.
    mouth = [(12, 21), (37, 12), (52, 21), (28, 30)]
    grains = pen.layer()
    grains.poly(mouth, GAP)
    rng = random.Random(403)
    for row in range(7):
        for col in range(10):
            x = 11 + col * 4.5 + (row % 2) * 1.8 + rng.uniform(-0.5, 0.5)
            y = 12 + row * 3.1 + rng.uniform(-0.4, 0.4)
            grain(
                grains,
                x,
                y,
                rng.uniform(1.8, 2.3),
                rng.uniform(1.1, 1.5),
                rng.uniform(-0.8, 0.8),
                rng.randint(-5, 5),
            )
    clip = Image.new("L", (N, N))
    ImageDraw.Draw(clip).polygon(pen.map(mouth), fill=255)
    pen.image.paste(grains.image, (0, 0), clip)
    # Rolled rim: light back edge, dark front seam.
    pen.line([(10, 20), (37, 10), (55, 21)], LIGHT, 1.7)
    pen.line([(10, 20), (28, 31), (55, 21)], (45, 65, 65), 1.0)
    pen.line([(11, 21), (28, 32), (54, 22)], CREAM, 1.3)
    pen.line([(28, 33), (28, 52)], (79, 108, 110), 0.8)
    pen.line([(14, 27), (14, 42), (24, 48)], (222, 236, 224), 0.9)
    pen.line([(33, 36), (48, 30)], (184, 205, 202), 0.8)
    pen.line([(34, 47), (47, 43)], (116, 147, 148), 0.7)
    # Subtle molded handhold, clearly a container rather than a solid ingot.
    pen.line([(36, 38), (44, 35)], (68, 96, 97), 1.0)


# --------------------------------------------------------------- sheets
def sheet(pen, pts, fill=CREAM, outline=0.5):
    layer = pen.layer()
    layer.poly(pts, fill)
    # Opaque overlapping planes convey a thin, lightly translucent material.
    a, b, c, d = pts
    layer.poly(
        [
            ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2),
            b,
            c,
            ((c[0] + d[0]) / 2, (c[1] + d[1]) / 2),
        ],
        (188, 211, 208),
    )
    layer.line([a, b], LIGHT, 0.8)
    layer.line([b, c, d], (105, 135, 136), 0.7)
    pen.exterior(layer, outline)


def sheet_a(pen):
    sheet(pen, [(19, 28), (39, 24), (44, 36), (24, 41)], (181, 203, 199))
    sheet(pen, [(21, 22), (43, 28), (39, 41), (18, 34)])
    sheet(pen, [(23, 23), (43, 24), (41, 36), (20, 35)])
    # Turned-up corner, not a thick slab.
    pen.poly([(38, 35), (41, 32), (41, 36)], LIGHT)
    pen.line([(38, 35), (41, 32)], (120, 149, 149), 0.5)


def sheet_b(pen):
    rng = random.Random(405)
    for n in range(10):
        y = 8.5 - n * 0.8
        x = rng.uniform(-0.6, 0.6)
        pts = [(12 + x, 22 + y), (38 + x, 14 + y), (53 + x, 32 + y), (26 + x, 41 + y)]
        sheet(pen, pts, (194 + n * 2, 211 + n, 205 + n), 0.38)
    # Calm top face, two broad glints rather than busy surface texture.
    pen.poly([(16, 22), (37, 16), (41, 21), (20, 27)], (232, 240, 228))
    pen.line([(28, 39), (50, 32)], (141, 169, 168), 0.8)
    pen.poly([(47, 33), (52, 30), (51, 34)], LIGHT)


def sheet_c(pen):
    """Half-used roll: the original small_roll(extension=10), tilted 27 deg."""
    e = 10
    p = pen.sub(compose(translate(32, 34), compose(rotation(-27), translate(-37, -34))))
    # Loose leading lip first, below the cylinder; unmistakably film, not a box.
    p.grad_poly(
        [(19, 39), (44 + e, 39), (47 + e, 45), (22, 45), (18, 43)],
        SHEET_FRONT_HI,
        SHEET_BACK,
        outline=INK,
        width=0.8,
    )
    p.line([(23, 43), (44 + e, 43)], (240, 248, 248), 0.8)
    cap = (39 + e, 24, 49 + e, 44)
    p.grad_ellipse(cap, PLASTIC_TOP, PLASTIC_BOT)
    # Cylindrical lighting across the axis: crisp strips in roll space.
    step = 0.25
    v = 24.0
    while v < 44.0:
        t = (v + step / 2 - 24) / 20
        if t < 0.28:
            c = [a + (b - a) * t / 0.28 for a, b in zip(PLASTIC_TOP, PLASTIC_HI)]
        else:
            c = [
                a + (b - a) * (t - 0.28) / 0.72 for a, b in zip(PLASTIC_HI, PLASTIC_BOT)
            ]
        p.poly(
            [(20, v), (44 + e, v), (44 + e, v + step + 0.06), (20, v + step + 0.06)],
            tuple(round(x) for x in c),
        )
        v += step
    p.line([(20, 24), (44 + e, 24)], INK, 0.8)
    p.line([(20, 44), (44 + e, 44)], INK, 0.8)
    p.arc(cap, -90, 90, INK, 0.8)
    p.line([(25, 27), (42 + e, 27)], (253, 255, 255), 1.4)
    p.line([(28, 39), (44 + e, 39)], (153, 178, 184), 0.7)
    p.grad_ellipse(
        (14, 24, 26, 44), (247, 251, 246), (196, 218, 218), outline=INK, width=0.8
    )
    for k in (0.73, 0.48):
        p.grad_ellipse(
            (20 - 6 * k, 34 - 10 * k, 20 + 6 * k, 34 + 10 * k),
            (240, 247, 239),
            (200, 220, 217),
            outline=(135, 162, 162),
            width=0.6,
        )
    p.grad_ellipse(
        (18.4, 30.6, 21.6, 37.4),
        (86, 115, 117),
        (49, 78, 79),
        outline=(120, 148, 146),
        width=0.6,
    )


def sheet_d(pen):
    # Horizontal axis: back end (43,23), near circular end (22,37).
    # The broad side retains the same milk-white palette as the loose sheets.
    pen.ellipse((28, 8, 58, 40), (184, 205, 201))
    pen.poly([(15, 20), (36, 8), (54, 15), (37, 50), (23, 55), (8, 43)], CREAM)
    pen.poly([(28, 22), (50, 12), (56, 23), (36, 45), (23, 53)], (172, 198, 195))
    pen.poly([(12, 25), (34, 12), (42, 12), (18, 28)], LIGHT)
    pen.line([(25, 29), (49, 15)], (223, 235, 221), 1.5)
    pen.line([(30, 42), (52, 29)], (135, 167, 166), 0.9)
    # Visible sheet lip, tangential to lower-right edge.
    pen.poly([(27, 45), (49, 32), (55, 41), (34, 55), (24, 53)], (196, 216, 208))
    pen.line([(34, 55), (55, 41)], (62, 89, 89), 0.9)
    pen.line([(33, 52), (51, 41)], LIGHT, 0.9)
    # Circular/elliptical wound end, not a solid tube: nested film rings and core.
    pen.ellipse((6, 20, 36, 54), (225, 234, 222), (26, 39, 38), 0.9)
    pen.ellipse((9, 23, 33, 51), None, (120, 151, 148), 0.7)
    pen.ellipse((12, 26, 30, 48), None, (154, 180, 171), 0.7)
    pen.ellipse((15, 29, 27, 45), None, (127, 156, 150), 0.7)
    pen.ellipse((18, 32, 24, 42), (85, 109, 105), (51, 73, 69), 0.65)
    pen.line([(10, 30), (12, 26), (17, 24), (22, 24)], LIGHT, 0.9)
    pen.line([(15, 33), (17, 30), (21, 29)], (249, 248, 232), 0.7)
    pen.line([(20, 35), (21, 34), (22, 34)], (159, 180, 166), 0.7)


# --------------------------------------------------------------- pipeline
# fit: None keeps native design placement (pouch tiers are laid out in final
# canvas units); otherwise the art is uniformly scaled into this outer bbox
# (64-unit coordinates, contour included), matching the shipped silhouettes.
# contour: round black contour grown outside the art, in 64-unit screen space.
JOBS = {
    "PlasticGranule_a": (granule_a, None, 0.7),
    "PlasticGranule_b": (granule_b, None, 0.7),
    "PlasticGranule_c": (granule_c, None, 0.7),
    "PlasticGranule_d": (granule_d, (3, 4, 61, 59), 1.1),
    "PlasticSheet_a": (sheet_a, (16, 20, 48, 44), 0.6),
    "PlasticSheet_b": (sheet_b, (11, 15, 53, 49), 0.75),
    "PlasticSheet_c": (sheet_c, (5, 12, 61, 57), 0.65),
    "PlasticSheet_d": (sheet_d, (2, 5, 62, 59), 1.1),
}


def render(design, matrix):
    pen = Pen(Image.new("RGBA", (N, N)), matrix)
    design(pen)
    return pen.image


def fitted_matrix(design, box, contour):
    raw = render(design, IDENTITY).getchannel("A").getbbox()
    x0, y0, x1, y1 = (v / SS for v in raw)
    tw, th = box[2] - box[0] - 2 * contour, box[3] - box[1] - 2 * contour
    k = min(tw / (x1 - x0), th / (y1 - y0))
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return compose(
        translate(cx, cy),
        compose(scaling(k), translate(-(x0 + x1) / 2, -(y0 + y1) / 2)),
    )


def fill_holes(mask):
    """Make enclosed transparent pockets opaque; only outside air stays clear."""
    probe = mask.copy()
    ImageDraw.floodfill(probe, (0, 0), 128)
    return probe.point(lambda v: 0 if v == 128 else 255)


def finish(art, contour):
    """Black contour, hole fill, separate Lanczos of colour and alpha."""
    silhouette = art.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    outer = fill_holes(dilate(silhouette, contour * SS))
    flat = Image.new("RGBA", (N, N), INK + (255,))
    flat.alpha_composite(art)
    colour = flat.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    alpha = outer.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    alpha = alpha.point(lambda a: 0 if a < 8 else 255 if a > 248 else a)
    # Lanczos ringing outside the true footprint must not leave stray specks.
    support = outer.resize((SIZE, SIZE), Image.Resampling.BOX).point(
        lambda a: 255 if a else 0
    )
    alpha = ImageChops.multiply(alpha, support)
    opaque = alpha.point(lambda a: 255 if a == 255 else 0)
    clean = Image.new("RGB", (SIZE, SIZE))
    clean.paste(colour, mask=opaque)
    clean.putalpha(alpha)
    return clean


def generate():
    images = {}
    for name, (design, box, contour) in JOBS.items():
        matrix = IDENTITY if box is None else fitted_matrix(design, box, contour)
        images[name] = finish(render(design, matrix), contour)
    return images


def components(pixels, test):
    pending = {i for i, p in enumerate(pixels) if test(p[3])}
    sizes = []
    while pending:
        queue = [pending.pop()]
        count = 0
        while queue:
            i = queue.pop()
            count += 1
            x, y = i % SIZE, i // SIZE
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                j = ny * SIZE + nx
                if 0 <= nx < SIZE and 0 <= ny < SIZE and j in pending:
                    pending.remove(j)
                    queue.append(j)
        sizes.append(count)
    return sizes


def inspect(image):
    if image.size != (SIZE, SIZE) or image.mode != "RGBA":
        raise ValueError(f"Expected {SIZE}x{SIZE} RGBA image")
    pixels = (
        list(image.get_flattened_data())
        if hasattr(image, "get_flattened_data")
        else list(image.getdata())
    )
    alpha = {p[3] for p in pixels}
    dirty = sum(p[:3] != (0, 0, 0) for p in pixels if p[3] == 0)
    halo = sum(p[:3] != (0, 0, 0) for p in pixels if 0 < p[3] < 255)
    cutout = components(pixels, lambda a: a >= 128)
    any_alpha = components(pixels, lambda a: a > 0)
    bbox = image.getbbox()
    if dirty or halo or len(cutout) != 1 or len(any_alpha) != 1:
        raise ValueError(
            f"Invalid cutout: transparent RGB={dirty}, semitransparent non-black={halo}, "
            f"components(alpha>=128)={cutout}, components(alpha>0)={any_alpha}"
        )
    if 0 not in alpha or 255 not in alpha:
        raise ValueError("Expected fully transparent and fully opaque pixels")
    if bbox[0] == 0 or bbox[1] == 0 or bbox[2] == SIZE or bbox[3] == SIZE:
        raise ValueError(f"Silhouette touches canvas edge: {bbox}")
    return {
        "size": list(image.size),
        "mode": image.mode,
        "alpha_min": min(alpha),
        "alpha_max": max(alpha),
        "alpha_levels": len(alpha),
        "semitransparent_pixels": sum(0 < p[3] < 255 for p in pixels),
        "transparent_rgb_nonzero": dirty,
        "semitransparent_nonblack": halo,
        "bbox": list(bbox),
        "coverage_percent": round(sum(p[3] for p in pixels) / 255 / SIZE**2 * 100, 3),
        "components": cutout,
    }


# --------------------------------------------------------------- preview
def checker(draw, x, y, w, cell, light):
    for yy in range(0, w, cell):
        for xx in range(0, w, cell):
            check = (xx // cell + yy // cell) % 2
            v = (218 + check * 20) if light else (46 + check * 9)
            draw.rectangle(
                (
                    x + xx,
                    y + yy,
                    min(x + xx + cell, x + w) - 1,
                    min(y + yy + cell, y + w) - 1,
                ),
                fill=(v, v, v),
            )


def preview(path, after, before=None):
    """One row per texture: before/after at matching size, edge zoom, both bgs.

    Zoom tiles crop the same 96 px (after) / 24 px (before) window centred on
    the silhouette's upper edge, so outline and interior detail are visible.
    """
    font = ImageFont.load_default(size=14)
    gap, header = 12, 38
    zoom_after, zoom_window = 3, 96
    cols = []
    for light in (False, True):
        if before:
            cols += [("before 64 @4x", "before", 4, light)]
        cols += [
            ("after 256", "after", 1, light),
            ("after 64 (game)", "small", 1, light),
        ]
        if before:
            cols += [("before zoom", "bzoom", 12, light)]
        cols += [("after zoom 3x", "azoom", zoom_after, light)]
    tile = 288
    widths = [150 if kind == "small" else tile for _, kind, _, _ in cols]
    width = gap + sum(w + gap for w in widths)
    row = header + tile + gap
    out = Image.new("RGB", (width, gap + len(after) * row), (39, 43, 45))
    draw = ImageDraw.Draw(out)
    for r, name in enumerate(after):
        im = after[name]
        bx0, by0, bx1, _ = im.getbbox()
        cx = (bx0 + bx1) // 2
        cy = by0 + zoom_window // 2 - 8
        cx = min(max(cx, zoom_window // 2), SIZE - zoom_window // 2)
        window = (
            cx - zoom_window // 2,
            cy - zoom_window // 2,
            cx + zoom_window // 2,
            cy + zoom_window // 2,
        )
        tiles = {
            "after": im,
            "small": im.resize((64, 64), Image.Resampling.LANCZOS),
            "azoom": im.crop(window),
        }
        if before:
            old = before[name]
            tiles["before"] = old
            tiles["bzoom"] = old.crop(tuple(v // 4 for v in window))
        top = gap + r * row
        draw.text((gap, top), name, fill="white", font=font)
        x = gap
        for (label, kind, z, light), w in zip(cols, widths):
            draw.text(
                (x, top + 18),
                f"{label} {'light' if light else 'dark'}",
                fill="white",
                font=font,
            )
            y = top + header
            src = tiles[kind]
            size = src.width * z
            checker(draw, x, y, size, max(8, size // 8), light)
            big = src.resize((size, size), Image.Resampling.NEAREST) if z > 1 else src
            out.paste(big, (x, y), big)
            x += w + gap
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path)


# --------------------------------------------------------------- cli
def default_path(name):
    return RESOURCE / name.split("_")[0] / f"{name}.png"


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Write all eight PNGs flat into this folder "
        "(default: Textures/Things/Item/Resource/PlasticGranule|PlasticSheet)",
    )
    parser.add_argument(
        "--preview",
        type=Path,
        help="Optional contact-sheet PNG, outside runtime textures",
    )
    parser.add_argument(
        "--before-dir",
        type=Path,
        help="Optional flat folder of the previous eight PNGs, shown in the preview",
    )
    args = parser.parse_args()
    if args.before_dir and not args.preview:
        parser.error("--before-dir requires --preview")
    if args.preview:
        if args.preview.suffix.lower() != ".png":
            parser.error("--preview must be a .png path")
        if args.preview.resolve().is_relative_to(ROOT / "Textures") or (
            args.output_dir
            and args.preview.resolve().is_relative_to(args.output_dir.resolve())
        ):
            parser.error("--preview must be outside runtime textures and --output-dir")
    before = None
    if args.before_dir:
        before = {}
        for name in JOBS:
            path = args.before_dir / f"{name}.png"
            if not path.is_file():
                parser.error(f"--before-dir missing {path.name}")
            with Image.open(path) as im:
                before[name] = im.convert("RGBA")
    images = generate()
    report = {name: inspect(im) for name, im in images.items()}
    for family in FAMILIES:
        cov = [report[f"{family}_{t}"]["coverage_percent"] for t in TIERS]
        if not all(x < y for x, y in zip(cov, cov[1:])):
            raise ValueError(f"Expected strictly increasing {family} coverage: {cov}")
    for name, im in images.items():
        path = (
            args.output_dir / f"{name}.png" if args.output_dir else default_path(name)
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        im.save(path, optimize=True)
        report[name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    if args.preview:
        preview(args.preview, images, before)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
