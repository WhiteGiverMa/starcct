# gen_textures.py — procedural item textures for a RimWorld plastic mod
# Graphic_StackCount naming: _a (few) / _b (medium) / _c (full stack, also the
# UI icon). Vanilla style: 64x64 RGBA, soft low-saturation fills, 2px pure-black
# silhouette outline, top-left 45 degree key light.
#
# Pipeline: draw on a 256x256 supersampled canvas (4x) with antialiasing,
# downscale to 64x64 (LANCZOS), binarize alpha (>=128 -> 255 else 0, because the
# game Cutout shader discards at alpha < 0.5), then zero the RGB of fully
# transparent pixels so BC7 compression cannot produce white fringes.
#
# Run:  python gen_textures.py        (deterministic, fixed seed)
# Outputs (all 64x64 RGBA):
#   assets/PlasticGranule_a.png  scattered granules
#   assets/PlasticGranule_b.png  granule pile (~40-46% coverage)
#   assets/PlasticGranule_c.png  open box full of granules (~55%)
#   assets/PlasticSheet_a.png    3 loose film sheets
#   assets/PlasticSheet_b.png    stack of ~9 sheets (~40-46%)
#   assets/PlasticSheet_c.png    horizontal film roll
#   preview.png                  3x2 checkerboard contact sheet (4x nearest)

import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

SS = 4  # supersample factor
S = 64 * SS  # 256 canvas
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "assets")
PREVIEW = os.path.join(ROOT, "preview.png")
SEED = 20261031

# ---------------------------------------------------------------- palette
OUTLINE = (0, 0, 0, 255)  # vanilla signature: pure-black contour
OW = 2 * SS  # 2px at 64x64
PLASTIC_HI = (248, 251, 252, 255)  # lit (top-left)
PLASTIC_TOP = (228, 238, 241, 255)
PLASTIC_MID = (210, 224, 229, 255)
PLASTIC_BOT = (184, 201, 209, 255)  # shaded (bottom-right)
GRANULE_BASE = (236, 242, 244, 255)
GRANULE_SHADE = (190, 208, 214, 255)
CREAM_TOP = (243, 242, 233, 255)  # granule mound, slightly warmer than box
CREAM_SHADE = (210, 212, 200, 255)
SHEET_FRONT = (230, 239, 242, 255)
SHEET_FRONT_HI = (244, 249, 250, 255)
SHEET_BACK = (198, 211, 215, 255)  # underside / curl


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(4))


def shade(c, f):
    """Darken a color by factor f (for depth tints)."""
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f), c[3])


def new_canvas():
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


def diag_grad_image(x0, y0, x1, y1, c_tl, c_br):
    """Gradient image lit from top-left: color varies along s = x + y."""
    w, h = x1 - x0 + 1, y1 - y0 + 1
    span = max(1, (x1 + y1) - (x0 + y0))
    lut = [lerp(c_tl, c_br, i / span) for i in range(w + h + 2)]
    grad = Image.new("RGBA", (w, h))
    rows = []
    for yy in range(h):
        rows.extend(lut[yy : yy + w])
    grad.putdata(rows)
    return grad


def paste_grad_poly(img, pts, c_tl, c_br, outline=None, ow=OW):
    """Polygon filled with a top-left->bottom-right gradient + outline."""
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    x0 = int(min(p[0] for p in pts))
    x1 = int(max(p[0] for p in pts))
    y0 = int(min(p[1] for p in pts))
    y1 = int(max(p[1] for p in pts))
    grad = diag_grad_image(x0, y0, x1, y1, c_tl, c_br)
    img.paste(grad, (x0, y0), mask.crop((x0, y0, x1 + 1, y1 + 1)))
    if outline:
        d = ImageDraw.Draw(img)
        d.polygon(pts, outline=outline, width=ow)
        d.line(pts + [pts[0]], fill=outline, width=ow, joint="curve")


def paste_grad_ellipse(img, box, c_tl, c_br, outline=None, ow=OW):
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse(box, fill=255)
    x0, y0, x1, y1 = (int(v) for v in box)
    grad = diag_grad_image(x0, y0, x1, y1, c_tl, c_br)
    img.paste(grad, (x0, y0), mask.crop((x0, y0, x1 + 1, y1 + 1)))
    if outline:
        ImageDraw.Draw(img).ellipse(box, outline=outline, width=ow)


def black_contour(img, layer, ow=OW):
    """Pure-black outline around the union silhouette of `layer`
    (dilate the alpha, subtract the original, fill the ring black)."""
    alpha = layer.getchannel("A")
    dil = alpha.filter(ImageFilter.MaxFilter(2 * ow + 1))
    ring = ImageChops.subtract(dil, alpha)
    img.paste(Image.new("RGBA", img.size, OUTLINE), (0, 0), ring)
    img.alpha_composite(layer)


def draw_granule(img, cx, cy, rx, ry, tint=1.0, rim=False):
    """One milky granule: diagonal gradient, top-left highlight.
    rim=True adds a thin 1px black contour (only for isolated granules;
    inside piles it would merge into mush)."""
    d = ImageDraw.Draw(img)
    paste_grad_ellipse(
        img,
        [cx - rx, cy - ry, cx + rx, cy + ry],
        shade(GRANULE_BASE, tint),
        shade(GRANULE_SHADE, tint),
        outline=OUTLINE if rim else None,
        ow=SS,
    )
    # bright top-left sliver + specular dot (key light from upper-left)
    d.ellipse(
        [cx - rx * 0.6, cy - ry * 0.75, cx + rx * 0.2, cy - ry * 0.05],
        fill=shade(PLASTIC_HI, tint),
    )
    d.ellipse(
        [cx - rx * 0.42, cy - ry * 0.58, cx - rx * 0.42 + SS, cy - ry * 0.58 + SS],
        fill=shade((255, 255, 255, 255), tint),
    )


# ---------------------------------------------------------------- Granule_a
def gen_granule_a():
    rng = random.Random(SEED + 1)
    img = new_canvas()
    # ~18 granules loosely scattered in the central ~40x40 px (64-space) area
    spots = []
    tries = 0
    while len(spots) < 18 and tries < 600:
        tries += 1
        cx = rng.randint(14 * SS, 50 * SS)
        cy = rng.randint(16 * SS, 50 * SS)
        if all((cx - x) ** 2 + (cy - y) ** 2 > (5.6 * SS) ** 2 for x, y in spots):
            spots.append((cx, cy))
    for cx, cy in sorted(spots, key=lambda p: p[1]):
        rx = int(rng.uniform(2.4, 3.4) * SS)
        ry = int(rx * rng.uniform(0.62, 0.8))
        draw_granule(img, cx, cy, rx, ry)
    return img


# ---------------------------------------------------------------- Granule_b
def gen_granule_b():
    rng = random.Random(SEED + 5)
    img = new_canvas()

    # mound base: overlapping cream ellipses merged into one domed bumpy blob,
    # outlined in pure black around the union (like vanilla Steel_b)
    mound = new_canvas()
    paste_grad_ellipse(
        mound, [8 * SS, 23 * SS, 56 * SS, 52 * SS], CREAM_TOP, CREAM_SHADE
    )
    paste_grad_ellipse(
        mound, [19 * SS, 19 * SS, 45 * SS, 35 * SS], CREAM_TOP, CREAM_SHADE
    )  # crown for dome height
    for i in range(9):  # bumps along the crest
        t = i / 8
        bx = (13 + 38 * t) * SS
        by = (24.5 + abs(t - 0.5) * 6) * SS + rng.randint(-1, 1) * SS
        br = rng.uniform(3.4, 5.2) * SS
        paste_grad_ellipse(
            mound,
            [bx - br, by - br * 0.85, bx + br, by + br * 0.85],
            CREAM_TOP,
            CREAM_SHADE,
        )
    black_contour(img, mound)

    # granules on the mound surface + a few spilled at the foot
    spots = []
    tries = 0
    while len(spots) < 34 and tries < 900:
        tries += 1
        a = rng.uniform(0, math.tau)
        rr = math.sqrt(rng.uniform(0.02, 1.0))
        px = 32 * SS + 19 * SS * rr * math.cos(a)
        py = 36 * SS + 12 * SS * rr * math.sin(a)
        if all((px - x) ** 2 + (py - y) ** 2 > (2.2 * SS) ** 2 for x, y in spots):
            spots.append((px, py))
    for _ in range(13):  # spilled granules at the foot (touching the mound)
        spots.append((rng.uniform(12, 52) * SS, rng.uniform(46, 51) * SS))
    for px, py in sorted(spots, key=lambda p: p[1]):
        rx = int(rng.uniform(2.0, 2.8) * SS)
        ry = int(rx * rng.uniform(0.62, 0.8))
        depth = max(0.0, min(1.0, (py - 26 * SS) / (26 * SS)))
        draw_granule(img, px, py, rx, ry, tint=1.0 - 0.10 * depth)
    return img


# ---------------------------------------------------------------- Granule_c
def gen_granule_c():
    rng = random.Random(SEED + 2)
    img = new_canvas()
    d = ImageDraw.Draw(img)

    # mouth ellipse of the open box (big: this is the full-stack UI icon)
    mouth = [4.0 * SS, 16.0 * SS, 60.0 * SS, 30.5 * SS]
    cx = (mouth[0] + mouth[2]) / 2
    cy = (mouth[1] + mouth[3]) / 2

    # dark interior seen through the opening
    paste_grad_ellipse(img, mouth, (188, 203, 208, 255), (158, 177, 185, 255))

    # granule mound rising above the mouth (clamped inside the rim)
    mound = [mouth[0] + 5 * SS, cy - 8 * SS, mouth[2] - 5 * SS, cy + 3.0 * SS]
    paste_grad_ellipse(img, mound, CREAM_TOP, CREAM_SHADE)
    for i in range(11):  # bumps along the crest
        t = i / 10
        bx = (mouth[0] + 8 * SS) + t * (40 * SS) + rng.randint(-2, 2) * SS
        by = cy - 7.0 * SS + abs(t - 0.5) * 9 * SS + rng.randint(-1, 1) * SS
        br = rng.uniform(2.4, 3.6) * SS
        paste_grad_ellipse(
            img,
            [bx - br, by - br * 0.8, bx + br, by + br * 0.8],
            CREAM_TOP,
            CREAM_SHADE,
        )
    for _ in range(52):  # granule dots on the mound
        a = rng.uniform(0, math.tau)
        rr = rng.uniform(0.05, 0.92)
        px = cx + (mouth[2] - mouth[0]) / 2 * 0.80 * rr * math.cos(a)
        py = (cy - 3.2 * SS) + 6.4 * SS * rr * math.sin(a) * 0.9
        r = rng.uniform(1.0, 1.6) * SS
        col = CREAM_SHADE if rng.random() < 0.55 else (250, 250, 244, 255)
        d.ellipse([px - r, py - r, px + r, py + r], fill=col)

    # back rim (upper arc)
    d.arc(mouth, 180, 360, fill=OUTLINE, width=OW)

    # front face (covers lower half of the mouth)
    front = [
        (4 * SS, 23.2 * SS),
        (60 * SS, 23.2 * SS),
        (57 * SS, 54 * SS),
        (7 * SS, 54 * SS),
    ]
    paste_grad_poly(img, front, PLASTIC_TOP, PLASTIC_BOT, outline=OUTLINE, ow=OW)
    # left-side vertical sheen (key light from upper-left)
    d.rounded_rectangle(
        [11.5 * SS, 26.5 * SS, 15 * SS, 50 * SS],
        radius=1.6 * SS,
        fill=(236, 245, 247, 255),
    )
    # granules faintly visible through the translucent wall under the rim
    for _ in range(12):
        px = rng.uniform(9, 55) * SS
        py = rng.uniform(25.5, 30.5) * SS
        r = rng.uniform(1.0, 1.5) * SS
        d.ellipse([px - r, py - r, px + r, py + r], fill=(216, 227, 225, 255))
    # front rim arc over the face
    d.arc(mouth, 0, 180, fill=OUTLINE, width=OW)
    return img


# ---------------------------------------------------------------- sheets
def _sheet_layer(w, h, curl_corner, rng, tint=1.0, ow=OW):
    """One rectangular film sheet on its own layer, optional curled corner."""
    lw, lh = w + 24 * SS, h + 24 * SS
    layer = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    x0, y0, x1, y1 = 12 * SS, 12 * SS, 12 * SS + w, 12 * SS + h
    jit = lambda: rng.randint(-1, 1) * SS
    pts = [
        (x0 + jit(), y0 + jit()),
        ((x0 + x1) / 2, y0 + jit()),
        (x1 + jit(), y0 + jit()),
        (x1 + jit(), (y0 + y1) / 2),
        (x1 + jit(), y1 + jit()),
        ((x0 + x1) / 2, y1 + jit()),
        (x0 + jit(), y1 + jit()),
        (x0 + jit(), (y0 + y1) / 2),
    ]
    paste_grad_poly(
        layer,
        pts,
        shade(SHEET_FRONT_HI, tint),
        shade(SHEET_FRONT, tint * 0.97),
        outline=OUTLINE,
        ow=ow,
    )
    d = ImageDraw.Draw(layer)
    if curl_corner:
        cs = 3.5 * SS
        if curl_corner == "tr":
            tri = [(x1, y0), (x1 - cs * 2, y0), (x1, y0 + cs * 2)]
        else:
            tri = [(x1, y1), (x1 - cs * 2, y1), (x1, y1 - cs * 2)]
        d.polygon(tri, fill=shade(SHEET_BACK, tint))
        d.line(tri + [tri[0]], fill=OUTLINE, width=max(2, SS - 1))
    # highlight streak along the upper (lit) edge
    d.line(
        [(x0 + 3 * SS, y0 + 2.8 * SS), (x1 - 4 * SS, y0 + 2.8 * SS)],
        fill=shade(SHEET_FRONT_HI, tint),
        width=SS * 2,
    )
    return layer


def gen_sheet_a():
    rng = random.Random(SEED + 3)
    img = new_canvas()
    w, h = 30 * SS, 15 * SS
    # three sheets, spread but slightly overlapping, each readable
    s1 = _sheet_layer(w, h, "tr", rng).rotate(-14, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(s1, (int(4 * SS), int(12 * SS)))
    s2 = _sheet_layer(w, h, "br", rng).rotate(7, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(s2, (int(18 * SS), int(16 * SS)))
    s3 = _sheet_layer(w, h, "tr", rng).rotate(-5, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(s3, (int(11 * SS), int(26 * SS)))
    return img


def gen_sheet_b():
    rng = random.Random(SEED + 6)
    img = new_canvas()
    w, h = 44 * SS, 19 * SS
    n = 8  # ~8 sheets: a stack with visible thickness
    # bottom sheet drawn first; each higher sheet shifts up and jitters,
    # so the pile shows stair-stepped edges at front/right = thickness
    base_x, base_y = 6.0 * SS, 19.0 * SS
    for i in range(n):
        depth = i / (n - 1)  # 0 = bottom, 1 = top
        tint = 0.84 + 0.16 * depth  # lower sheets slightly darker
        # alternate the horizontal stagger so layers peek on both sides
        dx = ((i % 2) * 4.8 - 2.4 + rng.uniform(-1.2, 1.2)) * SS
        dy = (n - 1 - i) * 2.7 * SS  # bottom sheets sit lower
        ang = rng.uniform(-5.0, 5.0)
        curl = "tr" if i == n - 1 else None  # only the top sheet curls
        # buried sheets: thin 1px outline so their edges read as layers
        # instead of merging into a black slab
        ow = OW if i == n - 1 else SS
        layer = _sheet_layer(w, h, curl, rng, tint=tint, ow=ow)
        layer = layer.rotate(ang, resample=Image.BICUBIC, expand=True)
        img.alpha_composite(layer, (int(base_x + dx), int(base_y + dy)))
    return img


def gen_sheet_c():
    img = new_canvas()
    d = ImageDraw.Draw(img)

    top_y, bot_y = 18 * SS, 46 * SS
    face_cx, face_rx = 13 * SS, 7.5 * SS
    face_ry = (bot_y - top_y) / 2
    face_cy = (top_y + bot_y) / 2
    right_cx, right_rx = 50 * SS, 5.5 * SS

    # rounded right end cap
    paste_grad_ellipse(
        img,
        [right_cx - right_rx, top_y, right_cx + right_rx, bot_y],
        PLASTIC_MID,
        PLASTIC_BOT,
    )
    # tube body: highlight band biased toward the top (lit side)
    body = [(face_cx, top_y), (right_cx, top_y), (right_cx, bot_y), (face_cx, bot_y)]
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(body, fill=255)
    grad = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(int(top_y), int(bot_y) + 1):
        t = (y - top_y) / (bot_y - top_y)
        if t < 0.32:  # top edge -> gloss band
            col = lerp(PLASTIC_MID, PLASTIC_HI, t / 0.32)
        else:  # gloss -> shaded bottom
            col = lerp(PLASTIC_HI, PLASTIC_BOT, (t - 0.32) / 0.68)
        gd.line([(0, y), (S, y)], fill=col)
    img.paste(grad, (0, 0), mask)
    # soft shading on the tube right beside the protruding end face.
    # NOTE: composite through the layer's own alpha so we never erase the body.
    shade_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade_layer)
    for x in range(int(face_cx), int(face_cx + 5 * SS)):
        t = (x - face_cx) / (5 * SS)
        sd.line(
            [(x, top_y + 1), (x, bot_y - 1)],
            fill=lerp((196, 210, 216, 110), (210, 224, 229, 0), t),
        )
    img.alpha_composite(shade_layer)
    # film gloss stripe along the tube
    d.rounded_rectangle(
        [face_cx + 3 * SS, top_y + 2.4 * SS, right_cx - 1 * SS, top_y + 4.6 * SS],
        radius=SS,
        fill=(250, 253, 253, 255),
    )

    # black silhouette: tube edges + right cap arc
    d.line([(face_cx, top_y), (right_cx + 1, top_y)], fill=OUTLINE, width=OW)
    d.line([(face_cx, bot_y), (right_cx + 1, bot_y)], fill=OUTLINE, width=OW)
    d.arc(
        [right_cx - right_rx, top_y, right_cx + right_rx, bot_y],
        -90,
        90,
        fill=OUTLINE,
        width=OW,
    )

    # end face with concentric film rings
    face = [face_cx - face_rx, top_y, face_cx + face_rx, bot_y]
    paste_grad_ellipse(
        img, face, (235, 243, 246, 255), (202, 217, 223, 255), outline=OUTLINE, ow=OW
    )
    for k in (0.68, 0.42):
        rb = [
            face_cx - face_rx * k,
            face_cy - face_ry * k,
            face_cx + face_rx * k,
            face_cy + face_ry * k,
        ]
        d.ellipse(rb, outline=(142, 158, 164, 255), width=max(2, SS - 1))
    # core
    core = [
        face_cx - face_rx * 0.2,
        face_cy - face_ry * 0.16,
        face_cx + face_rx * 0.2,
        face_cy + face_ry * 0.16,
    ]
    paste_grad_ellipse(
        img,
        core,
        (178, 192, 198, 255),
        (148, 165, 172, 255),
        outline=(110, 124, 130, 255),
        ow=max(2, SS - 1),
    )
    return img


# ---------------------------------------------------------------- finalize
def finalize(img):
    """64x64, binary alpha (Cutout discards <0.5), transparent RGB -> black."""
    out = img.resize((64, 64), Image.LANCZOS)
    a = out.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    out.putalpha(a)
    # zero RGB where fully transparent (prevents BC7 white fringe)
    clean = Image.new("RGBA", out.size, (0, 0, 0, 0))
    clean.paste(out, (0, 0), a)
    return clean


def alpha_stats(img):
    a = img.getchannel("A")
    px = list(a.getdata())
    cov = sum(1 for v in px if v == 255) / len(px)
    w, h = img.size
    grid = [[a.getpixel((x, y)) for y in range(h)] for x in range(w)]
    holes = 0
    for x in range(1, w - 1):
        for y in range(1, h - 1):
            if (
                grid[x][y] == 0
                and grid[x - 1][y]
                and grid[x + 1][y]
                and grid[x][y - 1]
                and grid[x][y + 1]
            ):
                holes += 1
    return cov, holes


def make_preview(items):
    """3x2 contact sheet: 4x nearest upscale, checkerboard, label strips."""
    cell, gap, label_h = 256, 10, 26
    cols, rows = 3, 2
    W = cell * cols + gap * (cols + 1)
    H = (cell + label_h) * rows + gap * (rows + 1)
    prev = Image.new("RGB", (W, H), (40, 40, 44))
    pd = ImageDraw.Draw(prev)
    try:
        font = ImageFont.load_default(size=18)
    except TypeError:
        font = ImageFont.load_default()

    checker = Image.new("RGB", (cell, cell))
    cd = ImageDraw.Draw(checker)
    for y in range(0, cell, 16):
        for x in range(0, cell, 16):
            c = (210, 210, 210) if (x // 16 + y // 16) % 2 == 0 else (168, 168, 168)
            cd.rectangle([x, y, x + 15, y + 15], fill=c)

    for i, (name, im) in enumerate(items):
        r, c = divmod(i, cols)
        x0 = gap + c * (cell + gap)
        y0 = gap + r * (cell + label_h + gap)
        prev.paste(checker, (x0, y0))
        big = im.resize((cell, cell), Image.NEAREST)
        prev.paste(big, (x0, y0), big)
        pd.rectangle([x0, y0 + cell, x0 + cell, y0 + cell + label_h], fill=(30, 30, 34))
        pd.text((x0 + 8, y0 + cell + 4), name, fill=(235, 235, 240), font=font)
    prev.save(PREVIEW)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    # remove stale outputs from the older naming scheme
    keep = {
        "PlasticGranule_a.png",
        "PlasticGranule_b.png",
        "PlasticGranule_c.png",
        "PlasticSheet_a.png",
        "PlasticSheet_b.png",
        "PlasticSheet_c.png",
    }
    for f in os.listdir(OUT_DIR):
        if f.endswith(".png") and f not in keep:
            os.remove(os.path.join(OUT_DIR, f))
            print(f"removed stale {f}")
    gens = [
        ("PlasticGranule_a", gen_granule_a),
        ("PlasticGranule_b", gen_granule_b),
        ("PlasticGranule_c", gen_granule_c),
        ("PlasticSheet_a", gen_sheet_a),
        ("PlasticSheet_b", gen_sheet_b),
        ("PlasticSheet_c", gen_sheet_c),
    ]
    items = []
    for name, fn in gens:
        out = finalize(fn())
        path = os.path.join(OUT_DIR, name + ".png")
        out.save(path)
        cov, holes = alpha_stats(out)
        print(f"{name}: 64x64 RGBA, opaque coverage {cov * 100:.1f}%, holes {holes}")
        items.append((name, out))
    make_preview(items)
    print(f"preview -> {PREVIEW}")


if __name__ == "__main__":
    main()
