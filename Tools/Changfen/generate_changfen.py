"""Deterministic plain rice-noodle item textures; Python 3.13+ / Pillow 11+.

64 design units, 32x supersampling, circular black contour, separate
Lanczos colour/alpha, black-matte alpha clamp. No external art or fonts.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
RESOURCE = ROOT / "Textures/Things/Item/Meal"
SIZE, DESIGN, SS = 256, 64, 32
N = DESIGN * SS
INK = (0, 0, 0)
FAMILIES = {"Changfen": "abcd", "ZhuChangfen": "abc"}


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


def rounded_rect(x0, y0, x1, y1, radius=2):
    points = []
    for x, y, start in (
        (x1 - radius, y0 + radius, -90),
        (x1 - radius, y1 - radius, 0),
        (x0 + radius, y1 - radius, 90),
        (x0 + radius, y0 + radius, 180),
    ):
        for i in range(17):
            angle = math.radians(start + i * 90 / 16)
            points.append((x + radius * math.cos(angle), y + radius * math.sin(angle)))
    return points


def curve(start, segments, steps=16):
    """Sample cubic Beziers; shared by supple noodle edges and highlights."""
    out = [start]
    for a, b, end in segments:
        for i in range(1, steps + 1):
            t = i / steps
            u = 1 - t
            out.append(
                (
                    u**3 * start[0]
                    + 3 * u * u * t * a[0]
                    + 3 * u * t * t * b[0]
                    + t**3 * end[0],
                    u**3 * start[1]
                    + 3 * u * u * t * a[1]
                    + 3 * u * t * t * b[1]
                    + t**3 * end[1],
                )
            )
        start = end
    return out


WHITE = (251, 251, 242)
NOODLE = (235, 240, 229)
FOLD = (151, 171, 167)
PLASTIC = (189, 209, 211)
EDGE = (62, 83, 86)
KRAFT = (190, 139, 81)
BROWN = (78, 52, 34)


def folded_strip(pen, x, y, variant=0):
    p = pen.sub(translate(x, y))
    end = 13.4 - 0.5 * (variant % 2)
    shape = curve(
        (-13.2, -1.4),
        [
            ((-10, -2.7), (-5, -1.45), (-1, -2.0)),
            ((4, -2.55), (9, -1.6), (end, -2.0)),
            ((end + 1.3, -0.8), (end - 0.1, 0.7), (end + 0.6, 1.6)),
            ((8, 2.6), (4, 1.8), (0, 2.3)),
            ((-5, 2.9), (-10, 1.5), (-13.5, 2.0)),
            ((-14.7, 1), (-14.0, -0.9), (-13.2, -1.4)),
        ],
    )
    p.grad_poly(shape, WHITE, (211, 224, 215), FOLD, 0.34)
    # Folded-over sheet lip, irregular and broad rather than a sausage casing.
    lip = curve(
        (-13.3, 0.65),
        [
            ((-9, -0.1), (-5, 1.3), (0, 0.65)),
            ((4, 0.1), (9, 1.15), (end, 0.5)),
        ],
    )
    p.line(lip, (173, 190, 181), 0.42)
    p.line([(a, b - 0.45) for a, b in lip], WHITE, 0.56)
    p.line(
        curve((-11, -1.0), [((-6, -1.6), (-3, -0.6), (2.5, -1.2))]),
        (255, 255, 250),
        0.65,
    )
    # Thin pleats at one open end make the stacked sheet construction legible.
    p.line([(-12.8, -0.9), (-13.2, 0.1), (-12.6, 0.8)], (183, 200, 191), 0.35)
    p.line([(end - 0.9, -1.1), (end - 1.4, 0.1), (end - 0.9, 0.7)], FOLD, 0.32)


def rice_roll(pen, x, y, length=18, radius=2.7, angle=0):
    """Tightly wound edible sheet: white cylinder and a real continuous spiral."""
    p = pen.sub(compose(translate(x, y), rotation(angle)))
    r = radius
    p.grad_ellipse((length - r * 0.7, -r, length + r * 0.7, r), WHITE, (181, 201, 195))
    p.grad_poly([(0, -r), (length, -r), (length, r), (0, r)], WHITE, (188, 208, 200))
    p.line([(0.4, r - 0.15), (length, r - 0.15)], (132, 156, 150), 0.35)
    p.line(
        curve(
            (1, -r * 0.60),
            [
                (
                    (length * 0.35, -r * 0.82),
                    (length * 0.8, -r * 0.45),
                    (length - 0.5, -r * 0.6),
                )
            ],
        ),
        (255, 255, 250),
        0.60,
    )
    p.line([(3, r * 0.55), (length - 1, r * 0.55)], (216, 230, 218), 0.36)
    p.grad_ellipse(
        (-r * 0.75, -r, r * 0.75, r),
        (255, 254, 245),
        (225, 234, 219),
        (138, 159, 150),
        0.32,
    )
    spiral = []
    for i in range(145):
        t = i / 144
        a = -math.pi / 2 + t * math.tau * 2.05
        rad = r * (0.83 - 0.75 * t)
        spiral.append((math.cos(a) * rad * 0.75, math.sin(a) * rad))
    p.line(spiral, (143, 164, 150), 0.30)
    p.line([(a - 0.16, b - 0.12) for a, b in spiral[:85]], (255, 255, 248), 0.16)


def meal_box(pen, x, y, scale=1, rolled=False, angle=0):
    """An open food-grade PP tray, oblique top plane and ribbed translucent wall."""
    layer = pen.layer()
    p = layer.sub(compose(translate(x, y), compose(rotation(angle), scaling(scale))))
    plane = (1, 0.34, 0, -0.12, 0.65, 0)
    q = p.sub(plane)
    top = rounded_rect(-18, -12, 18, 12, 3)
    # Molded base below the mouth. Opaque overlapping tints imply clear plastic.
    body = [(a + 0.34 * b, -0.12 * a + 0.65 * b + 4.4) for a, b in top]
    p.grad_poly(body, (207, 224, 224), (139, 168, 174))
    q.grad_poly(top, (237, 246, 242), PLASTIC)
    q.line(top + [top[0]], EDGE, 0.65)
    inner = rounded_rect(-16.3, -10.5, 16.3, 10.5, 2.1)
    q.grad_poly(inner, (158, 184, 184), (207, 225, 218))
    q.line(inner + [inner[0]], (126, 155, 156), 0.4)
    if rolled:
        # Four parallel rolls, their open spiral ends visible toward the viewer.
        for row in range(4):
            rice_roll(q, -12.5, -7.1 + row * 4.65, length=25, radius=2.15)
    else:
        for row in range(4):
            folded_strip(q, 0.2 * (row % 2), -7.1 + row * 4.7, row)
    # The front lip sits over the food; clean double rim, snap tab, fine ribs.
    q.line([(-17, 9.5), (-15.7, 11.2), (15.5, 11.2), (17.6, 9.8)], (245, 253, 248), 1.0)
    q.line([(-15.5, 12), (15.5, 12), (18, 9.7)], EDGE, 0.48)
    front = [
        (a + 0.34 * b, -0.12 * a + 0.65 * b + 3.6)
        for a, b in [(-17.3, 10), (-15, 11.6), (15, 11.6), (17.3, 10)]
    ]
    p.line(front, (237, 249, 246), 0.65)
    p.line([(a, b + 0.55) for a, b in front], (99, 131, 136), 0.40)
    for x0 in (-12, -7, -2, 3, 8, 13):
        xx, yy = x0 + 0.34 * 12, -0.12 * x0 + 0.65 * 12
        p.line([(xx, yy + 0.9), (xx + 0.1, yy + 3.0)], (161, 190, 192), 0.42)
    q.line([(-16.5, -9), (-16.5, 5)], (255, 255, 252), 0.65)
    q.line([(-12, -11.3), (10, -11.3)], (255, 255, 252), 0.6)
    q.poly([(-2.8, 11.5), (2.8, 11.5), (2.5, 13), (-2.5, 13)], (215, 234, 232))
    q.line([(-2.5, 13), (2.5, 13)], EDGE, 0.36)
    # Local edge for overlaps, final circular outline supplies the outer 4.4px.
    pen.exterior(layer, 0.10)


def label(p, rolled=False):
    """Local label space 0..13 x 0..12, placed by an affine on carton face."""
    p.poly([(0, 0), (13, 0), (13, 12), (0, 12)], (241, 234, 207))
    p.poly([(0, 0), (13, 0), (13, 1.4), (0, 1.4)], (82, 94, 86))
    if rolled:
        rice_roll(p, 3.4, 4.8, length=6, radius=1.8)
        p.line([(2, 7.5), (10.7, 7.5)], BROWN, 0.35)
    else:
        p.poly([(1.5, 3.4), (10.8, 3.4), (11.8, 7.8), (2.6, 7.8)], (139, 168, 163))
        for y in (4.1, 5.4, 6.7):
            p.line([(2.7, y), (9.8, y)], (255, 253, 235), 0.75)
        p.line([(2.5, 8), (11.8, 8)], BROWN, 0.4)
    # Pictographic inventory label; no unreadable fake prose or external fonts.
    for i, w in enumerate((0.35, 0.65, 0.25, 0.35, 0.8, 0.3, 0.5, 0.3)):
        x = 1.7 + i * 0.72
        p.poly([(x, 9.3), (x + w, 9.3), (x + w, 11), (x, 11)], BROWN)
    p.line([(9, 9.5), (11.5, 9.5)], (143, 130, 101), 0.4)
    p.line([(9, 10.7), (10.7, 10.7)], (143, 130, 101), 0.4)


def closed_carton(pen, compact=False):
    # Same perspective, markedly smaller stock carton for loose rolled noodles.
    p = pen.sub(
        compose(
            translate(32, 32),
            compose(scaling(0.77 if compact else 1), translate(-32, -32)),
        )
    )
    a, b, c, d = (7, 20), (34, 8), (57, 20), (29, 33)
    bottom_left, bottom_mid, bottom_right = (8, 44), (29, 57), (56, 44)
    p.grad_poly([a, d, bottom_mid, bottom_left], (201, 152, 95), (164, 111, 60))
    p.grad_poly([d, c, bottom_right, bottom_mid], (169, 119, 65), (135, 88, 46))
    p.grad_poly([a, b, c, d], (225, 184, 124), (195, 146, 87))
    p.line([a, d, c], BROWN, 0.7)
    p.line([d, bottom_mid], BROWN, 0.7)
    p.line([(8.5, 21), (28.1, 33.3), (28.1, 54.5)], (229, 186, 125), 0.55)
    # Wide paper packing tape crosses top seam and folds down front panel.
    p.poly([(18.6, 14.8), (23.2, 12.8), (46.5, 24.8), (41.8, 27.1)], (233, 207, 154))
    p.line([(20.8, 14), (44.1, 26)], (155, 118, 69), 0.52)
    p.poly([(41.8, 27.1), (46.5, 24.8), (46.3, 34.4), (41.7, 36.6)], (199, 167, 112))
    p.line([(44.1, 26), (44, 35.4)], (145, 108, 63), 0.45)
    p.line([(8, 43.7), (29, 56.7), (56, 43.7)], (101, 69, 39), 0.5)
    # Label on large front-left face, shaped to its perspective.
    label(p.sub((1.1, 0, 10.8, 0.65, 1.0, 25.0)), compact)
    # Small handling arrows on right panel, printing directly on kraft.
    for x, y in ((49, 36.5), (53, 34.6)):
        p.line([(x, y + 5), (x, y)], BROWN, 0.55)
        p.line([(x - 1.15, y + 1.8), (x, y), (x + 1.15, y + 0.7)], BROWN, 0.55)
    p.line([(48, 43.5), (54, 40.7)], BROWN, 0.5)
    p.line([(12, 41), (16, 43.5)], (143, 95, 51), 0.45)


def changfen_a(p):
    meal_box(p, 32, 30.8, 0.89)


def changfen_b(p):
    meal_box(p, 33, 36.5, 1.0)
    meal_box(p, 29.4, 26.1, 1.0)


def changfen_c(p):
    # Open small corrugated case. Rear flaps and interior precede its contents.
    p.poly([(7, 20), (29, 11), (47, 21), (25, 32)], (106, 75, 47))
    p.grad_poly(
        [(7, 20), (29, 11), (27, 6.8), (5.2, 15.9)], (220, 180, 121), (183, 133, 78)
    )
    p.line([(7, 20), (29, 11)], BROWN, 0.65)
    p.grad_poly(
        [(29, 11), (47, 21), (51, 17), (33, 6.5)], (225, 186, 130), (192, 145, 88)
    )
    p.line([(29, 11), (47, 21)], BROWN, 0.65)
    meal_box(p, 25.5, 24, 0.70)
    meal_box(p, 26.0, 18.4, 0.70)
    # Outer front wall occludes the lower halves of the stacked meal boxes.
    p.grad_poly([(7, 22), (25, 32), (25, 50), (8, 40)], (205, 160, 102), (168, 117, 63))
    p.grad_poly([(25, 32), (47, 22), (46, 40), (25, 50)], (180, 131, 76), (145, 96, 48))
    p.line([(7, 22), (25, 32), (47, 22)], BROWN, 0.7)
    p.line([(25, 32), (25, 50)], BROWN, 0.65)
    # Two outward-folded side flaps make the open case unmistakable.
    p.grad_poly(
        [(7, 22), (25, 32), (20, 36), (3.7, 26)], (222, 179, 118), (194, 143, 84)
    )
    p.line([(7, 22), (25, 32)], (130, 91, 50), 0.5)
    p.line([(3.7, 26), (20, 36), (25, 32)], BROWN, 0.5)
    label(p.sub((0.75, 0, 10, 0.44, 0.78, 29.8)))
    # Extra tray overlaps the carton foot: one connected item-stack silhouette.
    meal_box(p, 42.0, 44, 0.73, angle=-4)


def changfen_d(p):
    closed_carton(p)


def zhu_a(p):
    # One tiny portion: three short, delicate rolls in a centered compact stack.
    # Real overlaps keep the silhouette connected without detached shadows.
    rice_roll(p, 26, 27, length=12, radius=1.9, angle=12)
    rice_roll(p, 24, 31.5, length=14, radius=2.0, angle=-10)
    rice_roll(p, 26, 34.6, length=13, radius=2.05, angle=8)


def zhu_b(p):
    meal_box(p, 32, 30.8, 1.0, rolled=True)
    # Warm paper strip on the tray's near-right corner: readable at game scale.
    # It stays inside the existing silhouette, preserving stack-tier coverage.
    note = p.sub(compose(translate(39.5, 34.5), rotation(-7)))
    note.poly(
        [(-7.3, -3.2), (7.4, -3.2), (7.4, 2.1), (5.9, 4), (-7.3, 4)], (91, 109, 101)
    )
    paper = [(-7.5, -3.7), (7.1, -3.7), (7.1, 1.8), (5.5, 3.4), (-7.5, 3.4)]
    note.grad_poly(
        paper, (255, 231, 132), (236, 190, 78), outline=(126, 96, 42), width=0.32
    )
    note.line([(-6.8, -3.1), (6.5, -3.1)], (255, 245, 183), 0.45)
    note.poly([(5.5, 1.8), (7.1, 1.8), (5.5, 3.4)], (255, 244, 177))
    # A casual two-wave handwritten mark, not text or a food garnish.
    scribble = [
        (
            -5.3 + 10.1 * i / 80,
            -0.15 + 0.85 * math.sin(i / 80 * math.tau * 2) + 0.10 * i / 80,
        )
        for i in range(81)
    ]
    note.line(scribble, (79, 59, 38), 0.76)


def zhu_c(p):
    closed_carton(p, compact=True)


# Contour stays screen-space 1.1 design units (~4.4 output pixels).
JOBS = {
    "Changfen_a": (changfen_a, None, 1.1),
    "Changfen_b": (changfen_b, None, 1.1),
    "Changfen_c": (changfen_c, None, 1.1),
    "Changfen_d": (changfen_d, None, 1.1),
    "ZhuChangfen_a": (zhu_a, None, 1.1),
    "ZhuChangfen_b": (zhu_b, None, 1.1),
    "ZhuChangfen_c": (zhu_c, None, 1.1),
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
    holes = {}
    for threshold in (1, 128):
        mask = image.getchannel("A").point(lambda a: 255 if a >= threshold else 0)
        probe = mask.copy()
        ImageDraw.floodfill(probe, (0, 0), 128)
        values = (
            probe.get_flattened_data()
            if hasattr(probe, "get_flattened_data")
            else probe.getdata()
        )
        holes[str(threshold)] = sum(v == 0 for v in values)
    if any(holes.values()):
        raise ValueError(f"Enclosed transparent pinholes: {holes}")
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
        "components_alpha_gt_zero": any_alpha,
        "enclosed_transparent_pixels": holes,
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Write all seven PNGs flat here instead of runtime folders",
    )
    parser.add_argument(
        "--preview", type=Path, help="Contact sheet outside Textures and output-dir"
    )
    args = parser.parse_args()
    if args.preview:
        if args.preview.suffix.lower() != ".png":
            parser.error("--preview requires a .png path")
        if args.preview.resolve().is_relative_to(ROOT / "Textures") or (
            args.output_dir
            and args.preview.resolve().is_relative_to(args.output_dir.resolve())
        ):
            parser.error("--preview must be outside Textures and output-dir")
    images = generate()
    report = {name: inspect(im) for name, im in images.items()}
    for family, tiers in FAMILIES.items():
        coverage = [report[f"{family}_{tier}"]["coverage_percent"] for tier in tiers]
        if not all(a < b for a, b in zip(coverage, coverage[1:])):
            raise ValueError(f"Expected increasing {family} coverage: {coverage}")
    for name, image in images.items():
        path = (
            (args.output_dir / f"{name}.png")
            if args.output_dir
            else RESOURCE / name.split("_")[0] / f"{name}.png"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, optimize=True)
        report[name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    if args.preview:
        preview(args.preview, images)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
