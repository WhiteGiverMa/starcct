"""Deterministic, hand-drawn food-grade plastic resource textures.

Windows: py -3.13 gen_textures.py (Pillow required; no installation performed).
All outputs are relative to this file. No game files or source textures are used.
"""

from pathlib import Path
import math
import random
from collections import deque

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
S = 4
SIZE = 64
INK = (0, 0, 0, 255)
CREAM = (219, 229, 223, 255)
LIGHT = (246, 247, 232, 255)
MID = (180, 202, 199, 255)
SHADE = (132, 159, 160, 255)


def canvas():
    return Image.new("RGBA", (SIZE * S, SIZE * S))


def polygon(im, pts, fill):
    ImageDraw.Draw(im).polygon(
        [(round(x * S), round(y * S)) for x, y in pts], fill=fill
    )


def line(im, pts, fill, width=0.7):
    ImageDraw.Draw(im).line(
        [(round(x * S), round(y * S)) for x, y in pts],
        fill=fill,
        width=max(1, round(width * S)),
        joint="curve",
    )


def ellipse(im, box, fill, outline=None, width=0.5):
    ImageDraw.Draw(im).ellipse(
        tuple(round(v * S) for v in box),
        fill=fill,
        outline=outline,
        width=max(1, round(width * S)),
    )


def exterior(im, radius=1.3):
    """Black outline OUTSIDE the opaque painted silhouette, never over detail."""
    a = im.getchannel("A")
    radius_px = max(1, round(radius * S))
    expanded = a.filter(ImageFilter.MaxFilter(radius_px * 2 + 1))
    base = Image.new("RGBA", im.size, INK)
    base.putalpha(expanded)
    base.alpha_composite(im)
    return base


def grain(im, x, y, rx=1.8, ry=1.25, angle=0, tint=0):
    """An opaque pellet: upper-left glint, right/bottom shaded lip."""
    pts = []
    for n in range(16):
        t = n * math.tau / 16
        u, v = math.cos(t) * rx, math.sin(t) * ry
        pts.append(
            (
                x + u * math.cos(angle) - v * math.sin(angle),
                y + u * math.sin(angle) + v * math.cos(angle),
            )
        )
    polygon(im, pts, (209 + tint, 222 + tint, 216 + tint, 255))
    line(im, pts[0:9], (112, 137, 135, 255), 0.45)
    ellipse(im, (x - rx * 0.65, y - ry * 0.65, x + 0.15, y + 0.1), LIGHT)
    line(im, [pts[i] for i in (0, 15, 14, 13, 12, 11, 10)], (110, 137, 137, 255), 0.45)


def granules_a():
    im = canvas()
    rng = random.Random(401)
    positions = [
        (21, 23),
        (29, 21),
        (37, 23),
        (43, 27),
        (19, 30),
        (26, 28),
        (34, 29),
        (40, 34),
        (24, 35),
        (30, 36),
        (18, 39),
        (35, 40),
        (44, 40),
        (24, 44),
        (31, 46),
        (39, 46),
    ]
    for x, y in positions:
        g = canvas()
        grain(g, x, y, rng.uniform(1.5, 2), rng.uniform(1, 1.4), rng.uniform(-1, 1))
        im.alpha_composite(exterior(g, 0.85))
    return im


def granules_b():
    im = canvas()
    rng = random.Random(402)
    positions = []
    for row in range(7):
        count = (4, 6, 7, 8, 7, 6, 4)[row]
        for col in range(count):
            positions.append(
                (
                    32 + (col - (count - 1) / 2) * 4.5 + rng.uniform(-0.7, 0.7),
                    17 + row * 4.5 + rng.uniform(-0.7, 0.7),
                )
            )
    for x, y in positions:
        g = canvas()
        grain(
            g,
            x,
            y,
            rng.uniform(2, 2.5),
            rng.uniform(1.5, 1.9),
            rng.uniform(-0.8, 0.8),
            rng.randint(-8, 8),
        )
        im.alpha_composite(exterior(g, 0.65))
    return exterior(im, 0.6)


def granules_c():
    im = canvas()
    # An open rectangular food-grade tote, viewed from above and the front.
    polygon(im, [(9, 20), (37, 10), (55, 21), (53, 46), (28, 54), (11, 44)], MID)
    polygon(im, [(10, 21), (28, 32), (28, 53), (12, 44)], (188, 209, 205, 255))
    polygon(im, [(28, 32), (55, 22), (53, 46), (28, 54)], (147, 176, 177, 255))
    polygon(im, [(12, 21), (37, 12), (52, 21), (28, 30)], (113, 140, 140, 255))
    # Clip the mass of pellets to the inside of the rim.
    grains = canvas()
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
    mask = Image.new("L", im.size)
    ImageDraw.Draw(mask).polygon(
        [(int(x * S), int(y * S)) for x, y in [(12, 21), (37, 12), (52, 21), (28, 30)]],
        fill=255,
    )
    grains.putalpha(mask)
    im.alpha_composite(grains)
    # Rolled rim: light back edge, dark front seam. No transparent faces.
    line(im, [(10, 20), (37, 10), (55, 21)], LIGHT, 1.7)
    line(im, [(10, 20), (28, 31), (55, 21)], (45, 65, 65, 255), 1.0)
    line(im, [(11, 21), (28, 32), (54, 22)], CREAM, 1.3)
    line(im, [(28, 33), (28, 52)], (79, 108, 110, 255), 0.8)
    line(im, [(14, 27), (14, 42), (24, 48)], (222, 236, 224, 255), 0.9)
    line(im, [(33, 36), (48, 30)], (184, 205, 202, 255), 0.8)
    line(im, [(34, 47), (47, 43)], (116, 147, 148, 255), 0.7)
    # Subtle molded handhold, clearly a container rather than a solid ingot.
    line(im, [(36, 38), (44, 35)], (68, 96, 97, 255), 1.0)
    return exterior(im, 1.5)


def sheet(im, pts, fill=CREAM, outline=0.65):
    layer = canvas()
    polygon(layer, pts, fill)
    # Opaque overlapping planes convey a thin, lightly translucent material.
    a, b, c, d = pts
    polygon(
        layer,
        [
            ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2),
            b,
            c,
            ((c[0] + d[0]) / 2, (c[1] + d[1]) / 2),
        ],
        (188, 211, 208, 255),
    )
    line(layer, [a, b], LIGHT, 0.8)
    line(layer, [b, c, d], (105, 135, 136, 255), 0.7)
    im.alpha_composite(exterior(layer, outline))


def sheets_a():
    im = canvas()
    sheet(im, [(19, 28), (39, 24), (44, 36), (24, 41)], (181, 203, 199, 255))
    sheet(im, [(21, 22), (43, 28), (39, 41), (18, 34)])
    sheet(im, [(23, 23), (43, 24), (41, 36), (20, 35)])
    # Turned-up corner, not a thick slab.
    polygon(im, [(38, 35), (41, 32), (41, 36)], LIGHT)
    line(im, [(38, 35), (41, 32)], (120, 149, 149, 255), 0.5)
    return im


def sheets_b():
    im = canvas()
    rng = random.Random(405)
    for n in range(10):
        y = 8.5 - n * 0.8
        x = rng.uniform(-0.6, 0.6)
        pts = [(12 + x, 22 + y), (38 + x, 14 + y), (53 + x, 32 + y), (26 + x, 41 + y)]
        sheet(im, pts, (194 + n * 2, 211 + n, 205 + n, 255), 0.45)
    # Calm top face, two broad glints rather than busy surface texture.
    polygon(im, [(16, 22), (37, 16), (41, 21), (20, 27)], (232, 240, 228, 255))
    line(im, [(28, 39), (50, 32)], (141, 169, 168, 255), 0.8)
    polygon(im, [(47, 33), (52, 30), (51, 34)], LIGHT)
    return exterior(im, 0.8)


def sheets_c():
    im = canvas()
    # Horizontal axis: back end (43,23), near circular end (22,37).
    # The broad side retains the same milk-white palette as the loose sheets.
    ellipse(im, (28, 8, 58, 40), (184, 205, 201, 255))
    polygon(im, [(15, 20), (36, 8), (54, 15), (37, 50), (23, 55), (8, 43)], CREAM)
    polygon(
        im, [(28, 22), (50, 12), (56, 23), (36, 45), (23, 53)], (172, 198, 195, 255)
    )
    polygon(im, [(12, 25), (34, 12), (42, 12), (18, 28)], LIGHT)
    line(im, [(25, 29), (49, 15)], (223, 235, 221, 255), 1.5)
    line(im, [(30, 42), (52, 29)], (135, 167, 166, 255), 0.9)
    # Visible sheet lip, tangential to lower-right edge.
    polygon(
        im, [(27, 45), (49, 32), (55, 41), (34, 55), (24, 53)], (196, 216, 208, 255)
    )
    line(im, [(34, 55), (55, 41)], (62, 89, 89, 255), 0.9)
    line(im, [(33, 52), (51, 41)], LIGHT, 0.9)
    # Circular/elliptical wound end, not a solid tube: nested film rings and core.
    ellipse(im, (6, 20, 36, 54), (225, 234, 222, 255), (26, 39, 38, 255), 0.9)
    ellipse(im, (9, 23, 33, 51), None, (120, 151, 148, 255), 0.7)
    ellipse(im, (12, 26, 30, 48), None, (154, 180, 171, 255), 0.7)
    ellipse(im, (15, 29, 27, 45), None, (127, 156, 150, 255), 0.7)
    ellipse(im, (18, 32, 24, 42), (85, 109, 105, 255), (51, 73, 69, 255), 0.65)
    line(im, [(10, 30), (12, 26), (17, 24), (22, 24)], LIGHT, 0.9)
    line(im, [(15, 33), (17, 30), (21, 29)], (249, 248, 232, 255), 0.7)
    line(im, [(20, 35), (21, 34), (22, 34)], (159, 180, 166, 255), 0.7)
    return exterior(im, 1.3)


def clean_cutout(im):
    """Threshold at the shader cutoff; black RGB where fully transparent.

    RGB is first reconstructed against the unfiltered alpha, avoiding dark
    premultiplication fringes. Pillow RGBA Lanczos already resamples in premul.
    Isolated single pixels are removed, while intentional separated pellets stay.
    """
    im = im.resize((64, 64), Image.Resampling.LANCZOS)
    pixels = list(im.getdata())
    active = {i for i, p in enumerate(pixels) if p[3] >= 128}
    for i in tuple(active):
        x, y = i % 64, i // 64
        if not any(
            (y + dy) * 64 + x + dx in active
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]
            if 0 <= x + dx < 64 and 0 <= y + dy < 64
        ):
            active.remove(i)
    out = Image.new("RGBA", (64, 64))
    out.putdata(
        [(*p[:3], 255) if i in active else (0, 0, 0, 0) for i, p in enumerate(pixels)]
    )
    return out


def fit_coverage(source, target):
    """Calibrate silhouette coverage, preserving aspect and >=2 px margins."""
    box = source.getbbox()
    crop = source.crop(box)
    w, h = crop.size
    lo, hi = 0.2, min(60 * S / w, 60 * S / h)
    best = None
    error = float("inf")
    for _ in range(20):
        scale = (lo + hi) / 2
        nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
        work = canvas()
        resized = crop.resize((nw, nh), Image.Resampling.LANCZOS)
        work.alpha_composite(resized, ((64 * S - nw) // 2, (64 * S - nh) // 2))
        result = clean_cutout(work)
        coverage = result.getchannel("A").histogram()[255] / 4096
        if abs(coverage - target) < error:
            best, error = result, abs(coverage - target)
        if coverage < target:
            lo = scale
        else:
            hi = scale
    return best


def topology(im):
    opaque = set(i for i, p in enumerate(im.getdata()) if p[3])
    comps = []
    pending = set(opaque)
    while pending:
        start = pending.pop()
        q, component = [start], {start}
        while q:
            i = q.pop()
            x, y = i % 64, i // 64
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                j = (y + dy) * 64 + x + dx
                if 0 <= x + dx < 64 and 0 <= y + dy < 64 and j in pending:
                    pending.remove(j)
                    component.add(j)
                    q.append(j)
        comps.append(len(component))
    # Flood fill transparent space from canvas edges to locate enclosed holes.
    clear = set(range(4096)) - opaque
    edge = {i for i in clear if i % 64 in (0, 63) or i // 64 in (0, 63)}
    outside, q = set(edge), deque(edge)
    while q:
        i = q.popleft()
        x, y = i % 64, i // 64
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            j = (y + dy) * 64 + x + dx
            if (
                0 <= x + dx < 64
                and 0 <= y + dy < 64
                and j in clear
                and j not in outside
            ):
                outside.add(j)
                q.append(j)
    return comps, clear - outside


def close_pinholes(im):
    # Enclosed transparent spots between touching pellets become opaque creases.
    _, holes = topology(im)
    for i in holes:
        im.putpixel((i % 64, i // 64), (49, 67, 65, 255))
    return im


def preview(images):
    gap, tile, label = 10, 256, 30
    out = Image.new(
        "RGB", (3 * tile + 4 * gap, 2 * (tile + label) + 3 * gap), (33, 37, 40)
    )
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default(size=16)
    for i, (name, im) in enumerate(images):
        x = gap + (i % 3) * (tile + gap)
        y = gap + (i // 3) * (tile + label + gap)
        for yy in range(0, tile, 16):
            for xx in range(0, tile, 16):
                v = 91 if (xx // 16 + yy // 16) % 2 else 110
                draw.rectangle(
                    (x + xx, y + yy, x + xx + 15, y + yy + 15), fill=(v, v + 3, v + 3)
                )
        big = im.resize((tile, tile), Image.Resampling.NEAREST)
        out.paste(big, (x, y), big)
        cov = im.getchannel("A").histogram()[255] / 4096 * 100
        draw.text(
            (x + 5, y + tile + 6),
            f"{name}  {cov:.1f}%",
            font=font,
            fill=(231, 237, 232),
        )
    out.save(ROOT / "preview.png")


def main():
    assets = ROOT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("PlasticGranule_a", granules_a, 0.15),
        ("PlasticGranule_b", granules_b, 0.43),
        ("PlasticGranule_c", granules_c, 0.60),
        ("PlasticSheet_a", sheets_a, 0.15),
        ("PlasticSheet_b", sheets_b, 0.43),
        ("PlasticSheet_c", sheets_c, 0.60),
    ]
    images = []
    for name, fn, target in jobs:
        im = close_pinholes(fit_coverage(fn(), target))
        path = assets / (name + ".png")
        im.save(path, optimize=True)
        components, holes = topology(im)
        assert not holes and min(components) > 1, (name, components, holes)
        assert set(im.getchannel("A").getdata()) <= {0, 255}
        assert all(p[:3] == (0, 0, 0) for p in im.getdata() if p[3] == 0)
        with Image.open(path) as check:
            assert check.mode == "RGBA" and check.size == (64, 64)
        coverage = im.getchannel("A").histogram()[255] / 4096 * 100
        print(
            f"{name}: {coverage:.2f}% opaque; bbox={im.getbbox()}; "
            f"components={len(components)}, holes={len(holes)}; {path.stat().st_size} bytes"
        )
        images.append((name, im))
    preview(images)
    print(f"Preview: {ROOT / 'preview.png'}")


if __name__ == "__main__":
    main()
