"""Draw the Archotech-palette refactor keycard (Tarkov Labs style), 256x256 RGBA.

Requires Python 3.13+ and Pillow 11+. Deterministic: no randomness.
Tarkov high-tier keycard silhouette (tilted card, lanyard slot, header band,
smart chip, circuit traces) recoloured to RimWorld archotech sage + gold.

From the repo root:

    py -3.15 Tools/ReprogrammingKey/generate_reprogramming_key.py --help
    py -3.15 Tools/ReprogrammingKey/generate_reprogramming_key.py

The default output is the runtime texture; pass --preview with a Temp path to
write the dark-and-light contact sheet (game-scale 64, native 256, edge zoom).

Geometry lives in a 64-unit design space, supersampled 32x (2048 px) and
Lanczos-downsampled to 256 px. The silhouette keeps smooth anti-aliased alpha;
every pixel with 0 < alpha < 255 sits in the pure black outline, so its RGB is
(0, 0, 0) and RimWorld's cutout/UI blending cannot produce a light halo.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
TEXTURE = ROOT / "Textures/Things/Item/Special/ReprogrammingKey.png"
SIZE = 256  # output pixels
DESIGN = 64  # design-space units across the canvas
SS = 32  # supersampled pixels per design unit
N = DESIGN * SS  # 2048 px working canvas
INK = (0, 0, 0, 255)
ANGLE = -31.0
CENTER = (32.0, 32.5)

# Card half extents (design units, before rotation).
HU, HV, RADIUS = 18.5, 11.0, 3.0
OUTLINE = 1.1  # ~4.4 px at 256

SAGE_HI = (150, 172, 148)
SAGE_LO = (100, 126, 106)
CELADON = (196, 216, 190)
JADE_DARK = (48, 66, 54)
JADE_DEEP = (30, 44, 36)
RIM_SHADOW = (74, 96, 80)
GOLD = (235, 195, 65)
GOLD_BRIGHT = (255, 226, 108)
GOLD_SHADOW = (170, 124, 32)

_rad = math.radians(ANGLE)
_cos, _sin = math.cos(_rad), math.sin(_rad)


def pt(u, v):
    return (
        (CENTER[0] + u * _cos - v * _sin) * SS,
        (CENTER[1] + u * _sin + v * _cos) * SS,
    )


def rrect(u0, v0, u1, v1, r, steps=24):
    pts = []
    corners = (
        (u1 - r, v0 + r, -90),
        (u1 - r, v1 - r, 0),
        (u0 + r, v1 - r, 90),
        (u0 + r, v0 + r, 180),
    )
    for cu, cv, start in corners:
        for i in range(steps + 1):
            t = math.radians(start + 90 * i / steps)
            pts.append((cu + r * math.cos(t), cv + r * math.sin(t)))
    return pts


def mask_of(points):
    m = Image.new("L", (N, N), 0)
    ImageDraw.Draw(m).polygon([pt(*p) for p in points], fill=255)
    return m


def solid(rgb):
    return Image.new("RGBA", (N, N), rgb + (255,))


def gradient(hi, lo):
    """Top-left (hi) to bottom-right (lo) along x + y in screen space."""
    ramp = Image.linear_gradient("L").resize((N, N))  # vertical 0..255
    ramp = ImageChops.add(
        ramp.point(lambda p: p // 2),
        ramp.transpose(Image.Transpose.TRANSPOSE).point(lambda p: p // 2),
    )
    a = Image.new("RGBA", (N, N), hi + (255,))
    b = Image.new("RGBA", (N, N), lo + (255,))
    return Image.composite(b, a, ramp)


def shifted(mask, dx, dy):
    return ImageChops.offset(mask, round(dx * SS), round(dy * SS))


def draw_card():
    """Return (opaque art on black, silhouette mask), both N x N."""
    img = Image.new("RGBA", (N, N), INK)
    body = mask_of(rrect(-HU, -HV, HU, HV, RADIUS))
    outer = mask_of(
        rrect(
            -HU - OUTLINE, -HV - OUTLINE, HU + OUTLINE, HV + OUTLINE, RADIUS + OUTLINE
        )
    )
    img.paste(gradient(SAGE_HI, SAGE_LO), mask=body)

    # Detail layer, clipped to body afterwards.
    det = Image.new("RGBA", (N, N))
    d = ImageDraw.Draw(det)

    def poly(points, rgb):
        d.polygon([pt(*p) for p in points], fill=rgb + (255,))

    def line(points, rgb, w):
        d.line(
            [pt(*p) for p in points],
            fill=rgb + (255,),
            width=max(1, round(w * SS)),
            joint="curve",
        )

    def dot(u, v, r, rgb):
        poly(
            [
                (
                    u + r * math.cos(t * math.tau / 32),
                    v + r * math.sin(t * math.tau / 32),
                )
                for t in range(32)
            ],
            rgb,
        )

    # Header band at the right end: gold, lit from top-left, with dark chevrons.
    band = rrect(9.0, -HV - 2, HU + 2, HV + 2, 0.01)
    poly(band, GOLD)
    poly(
        [(9.0, -HV - 2), (HU + 2, -HV - 2), (HU + 2, -HV + 2.0), (9.0, -HV + 2.0)],
        GOLD_BRIGHT,
    )
    poly(
        [(9.0, HV - 2.0), (HU + 2, HV - 2.0), (HU + 2, HV + 2), (9.0, HV + 2)],
        GOLD_SHADOW,
    )
    line([(9.0, -HV - 1), (9.0, HV + 1)], JADE_DEEP, 1.1)
    for cu in (11.6, 15.4):
        line([(cu, -5.6), (cu + 2.6, 0), (cu, 5.6)], (128, 86, 16), 1.8)
        line([(cu - 0.4, -5.9), (cu + 2.2, -0.3)], GOLD_BRIGHT, 0.5)

    # Security strip along the bottom edge.
    poly([(-HU - 1, 4.9), (9.0, 4.9), (9.0, 7.1), (-HU - 1, 7.1)], JADE_DEEP)
    line([(-HU - 1, 7.6), (9.0, 7.6)], CELADON, 0.7)

    # Lanyard slot: recessed, so the lower-right inner wall catches light.
    slot = rrect(-16.2, -5.0, -13.4, 4.0, 1.3)
    poly(slot, JADE_DEEP)
    line(
        [(-13.5, -4.0), (-13.5, 3.0), (-14.6, 4.0), (-15.6, 4.0)], (120, 146, 124), 0.55
    )

    # Smart chip contact pad.
    chip = rrect(-11.0, -7.2, -3.6, -0.6, 1.0)
    poly(rrect(-11.6, -7.8, -3.0, 0.0, 1.4), GOLD_SHADOW)
    poly(chip, GOLD)
    poly(rrect(-11.0, -7.2, -3.6, -5.6, 0.8), GOLD_BRIGHT)
    line([(-7.3, -5.4), (-7.3, -0.6)], GOLD_SHADOW, 0.6)
    line([(-11.0, -3.9), (-3.6, -3.9)], GOLD_SHADOW, 0.6)
    line([(-10.6, -5.2), (-9.4, -5.2)], GOLD_BRIGHT, 0.45)

    # Archotech circuit traces from chip to header with nodes.
    line([(-3.0, -3.9), (1.0, -3.9), (3.4, -6.3), (9.0, -6.3)], GOLD_BRIGHT, 0.85)
    line([(-3.0, -1.6), (2.2, -1.6), (4.6, 0.8), (9.0, 0.8)], GOLD_BRIGHT, 0.85)
    dot(3.4, -6.3, 1.0, GOLD_BRIGHT)
    dot(4.6, 0.8, 1.0, GOLD_BRIGHT)

    # Archotech glyph: hexagon outline with luminous core.
    hx, hy, hr = 1.6, 2.2, 2.1
    hexpts = [
        (
            hx + hr * math.cos(math.radians(30 + 60 * k)),
            hy + hr * math.sin(math.radians(30 + 60 * k)),
        )
        for k in range(6)
    ]
    poly(hexpts, JADE_DARK)
    line(hexpts + [hexpts[0]], GOLD, 0.6)
    dot(hx, hy, 0.9, GOLD_BRIGHT)

    # Micro-data blocks under the chip.
    for i, w in enumerate((1.6, 0.8, 1.2, 0.8, 1.8)):
        u = -11.0 + sum((1.6, 0.8, 1.2, 0.8, 1.8)[:i]) + i * 0.7
        poly(
            [(u, 1.0), (u + w, 1.0), (u + w, 3.6), (u, 3.6)],
            CELADON if i % 2 == 0 else JADE_DARK,
        )

    img.paste(det, mask=ImageChops.multiply(det.getchannel("A"), body))

    # Bevels: top-left rim highlight, and a narrow mid-jade bottom-right rim
    # that stays distinct from the black outline instead of doubling it.
    hi_rim = ImageChops.subtract(body, shifted(body, 0.7, 0.7))
    lo_rim = ImageChops.subtract(body, shifted(body, -0.45, -0.45))
    img.paste(solid(CELADON), mask=hi_rim.point(lambda p: p * 3 // 4))
    img.paste(solid(RIM_SHADOW), mask=lo_rim)
    return img, outer


def cutout(art, outer):
    """Downsample RGB and alpha separately; outline-edge pixels stay black.

    The art is opaque (black outside the body), so RGB resampling never mixes
    in transparent colour. Faint Lanczos ringing is clamped at both alpha ends,
    and RGB is zeroed wherever alpha < 255 (that band lies inside the outline).
    """
    rgb = art.convert("RGB").resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    alpha = outer.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    alpha = alpha.point(lambda a: 0 if a < 8 else 255 if a > 248 else a)
    opaque = alpha.point(lambda a: 255 if a == 255 else 0)
    clean = Image.new("RGB", rgb.size)
    clean.paste(rgb, mask=opaque)
    clean.putalpha(alpha)
    return clean


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
    semi = sum(0 < p[3] < 255 for p in pixels)
    covered = sum(p[3] for p in pixels) / 255
    pending = {i for i, p in enumerate(pixels) if p[3]}
    components = []
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
        components.append(count)
    bbox = image.getbbox()
    if dirty or halo or len(components) != 1:
        raise ValueError(
            f"Invalid cutout: transparent RGB={dirty}, "
            f"semitransparent non-black={halo}, components={components}"
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
        "semitransparent_pixels": semi,
        "transparent_rgb_nonzero": dirty,
        "semitransparent_nonblack": halo,
        "bbox": list(bbox),
        "coverage_percent": round(covered / (SIZE * SIZE) * 100, 3),
        "components": components,
    }


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


def preview(path, image, before=None):
    """Dark/light rows: game-scale 64, native 256 and a 6x outline edge crop.

    With an older texture as `before`, its 1x view and the same edge crop at
    matching magnification are shown first for comparison.
    """
    font = ImageFont.load_default(size=14)
    crop = (120, 140, 184, 204)  # middle of the card's lower long edge, 64 px
    tiles = []
    if before is not None:
        before = before.convert("RGBA")
        k = before.width / SIZE
        bc = tuple(round(c * k) for c in crop)
        tiles += [
            ("before 64 (1x)", before, 1),
            ("before edge", before.crop(bc), 384 // (bc[2] - bc[0])),
        ]
    tiles += [
        ("after 64 (game 1x)", image.resize((64, 64), Image.Resampling.LANCZOS), 1),
        ("after 256 native", image, 1),
        ("after edge 6x", image.crop(crop), 6),
    ]
    gap, header = 14, 22
    tallest = max(im.height * z for _, im, z in tiles)
    width = gap + sum(max(im.width * z, 150) + gap for _, im, z in tiles)
    row = header + tallest + gap
    out = Image.new("RGB", (width, gap + 2 * row), (39, 43, 45))
    draw = ImageDraw.Draw(out)
    for bg in range(2):
        top = gap + bg * row
        x = gap
        for label, im, z in tiles:
            w = im.width * z
            draw.text(
                (x, top),
                f"{label} {'light' if bg else 'dark'}",
                fill="white",
                font=font,
            )
            y = top + header
            checker(draw, x, y, w, max(8, w // 8), bg)
            big = im.resize((w, w), Image.Resampling.NEAREST) if z > 1 else im
            out.paste(big, (x, y), big)
            x += max(w, 150) + gap
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=TEXTURE,
        help="Texture PNG to write (default: repository runtime texture)",
    )
    parser.add_argument(
        "--preview",
        type=Path,
        help="Optional contact-sheet PNG path, outside runtime textures",
    )
    parser.add_argument(
        "--before",
        type=Path,
        help="Optional older texture shown in the preview for comparison",
    )
    args = parser.parse_args()
    if args.preview:
        if args.preview.suffix.lower() != ".png":
            parser.error("--preview must be a .png path")
        if args.preview.resolve().is_relative_to(ROOT / "Textures"):
            parser.error("--preview must be outside runtime textures")
    if args.before and not args.preview:
        parser.error("--before requires --preview")
    image = cutout(*draw_card())
    report = inspect(image)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, optimize=True)
    report["sha256"] = hashlib.sha256(args.output.read_bytes()).hexdigest()
    if args.preview:
        before = Image.open(args.before) if args.before else None
        preview(args.preview, image, before)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
