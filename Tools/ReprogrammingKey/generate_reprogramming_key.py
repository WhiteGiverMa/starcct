"""Draw the Archotech-palette refactor keycard (Tarkov Labs style), 64x64 RGBA.

Requires Python 3.13+ and Pillow 11+. Deterministic: no randomness.
Tarkov high-tier keycard silhouette (tilted card, lanyard slot, header band,
smart chip, circuit traces) recoloured to RimWorld archotech sage + gold.

From the repo root:

    py -3.15 Tools/ReprogrammingKey/generate_reprogramming_key.py --help
    py -3.15 Tools/ReprogrammingKey/generate_reprogramming_key.py

The default output is the runtime texture; pass --preview with a Temp path to
write the 1x/4x/6x dark-and-light contact sheet.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
TEXTURE = ROOT / "Textures/Things/Item/Special/ReprogrammingKey.png"
SIZE = 64
SS = 8
INK = (0, 0, 0, 255)
ANGLE = -31.0
CENTER = (32.0, 32.5)

# Card half extents (local units = output pixels before rotation).
HU, HV, RADIUS = 18.5, 11.0, 3.0
OUTLINE = 1.9

SAGE_HI = (150, 172, 148)
SAGE_LO = (100, 126, 106)
CELADON = (196, 216, 190)
JADE_DARK = (48, 66, 54)
JADE_DEEP = (30, 44, 36)
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


def rrect(u0, v0, u1, v1, r, steps=10):
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
    m = Image.new("L", (SIZE * SS, SIZE * SS), 0)
    ImageDraw.Draw(m).polygon([pt(*p) for p in points], fill=255)
    return m


def solid(rgb):
    return Image.new("RGBA", (SIZE * SS, SIZE * SS), rgb + (255,))


def gradient(hi, lo):
    """Top-left (hi) to bottom-right (lo) along x + y in screen space."""
    n = SIZE * SS
    ramp = Image.linear_gradient("L").resize((n, n))  # vertical 0..255
    ramp = ImageChops.add(
        ramp.point(lambda p: p // 2),
        ramp.transpose(Image.Transpose.TRANSPOSE).point(lambda p: p // 2),
    )
    a = Image.new("RGBA", (n, n), hi + (255,))
    b = Image.new("RGBA", (n, n), lo + (255,))
    return Image.composite(b, a, ramp)


def shifted(mask, dx, dy):
    return ImageChops.offset(mask, round(dx * SS), round(dy * SS))


def draw_card():
    n = SIZE * SS
    img = Image.new("RGBA", (n, n))
    body = mask_of(rrect(-HU, -HV, HU, HV, RADIUS))
    outer = mask_of(
        rrect(
            -HU - OUTLINE, -HV - OUTLINE, HU + OUTLINE, HV + OUTLINE, RADIUS + OUTLINE
        )
    )
    img.paste(INK, mask=outer)
    img.paste(gradient(SAGE_HI, SAGE_LO), mask=body)

    # Detail layer, clipped to body afterwards.
    det = Image.new("RGBA", (n, n))
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
                    u + r * math.cos(t * math.tau / 16),
                    v + r * math.sin(t * math.tau / 16),
                )
                for t in range(16)
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

    # Bevels: top-left rim highlight, bottom-right rim shadow (inside body).
    d_px = 1.0
    hi_rim = ImageChops.subtract(body, shifted(body, d_px, d_px))
    lo_rim = ImageChops.subtract(body, shifted(body, -d_px, -d_px))
    img.paste(solid(CELADON), mask=hi_rim.point(lambda p: p * 3 // 4))
    img.paste(solid(JADE_DARK), mask=lo_rim)
    return img


def cutout(image):
    image = image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    alpha = image.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    image.putalpha(alpha)
    clean = Image.new("RGBA", image.size)
    clean.paste(image, mask=alpha)
    return clean


def inspect(image):
    if image.size != (64, 64) or image.mode != "RGBA":
        raise ValueError("Expected 64x64 RGBA image")
    pixels = (
        list(image.get_flattened_data())
        if hasattr(image, "get_flattened_data")
        else list(image.getdata())
    )
    alpha = sorted({p[3] for p in pixels})
    dirty = sum(p[:3] != (0, 0, 0) for p in pixels if p[3] == 0)
    pending = {i for i, p in enumerate(pixels) if p[3]}
    components = []
    while pending:
        queue = [pending.pop()]
        count = 0
        while queue:
            i = queue.pop()
            count += 1
            x, y = i % 64, i // 64
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                j = ny * 64 + nx
                if 0 <= nx < 64 and 0 <= ny < 64 and j in pending:
                    pending.remove(j)
                    queue.append(j)
        components.append(count)
    bbox = image.getbbox()
    if alpha != [0, 255] or dirty or len(components) != 1:
        raise ValueError(
            f"Invalid cutout: alpha={alpha}, dirty RGB={dirty}, components={components}"
        )
    if bbox[0] == 0 or bbox[1] == 0 or bbox[2] == 64 or bbox[3] == 64:
        raise ValueError(f"Silhouette touches canvas edge: {bbox}")
    return {
        "size": list(image.size),
        "mode": image.mode,
        "alpha": alpha,
        "transparent_rgb_nonzero": dirty,
        "bbox": list(bbox),
        "coverage_percent": round(sum(components) / 4096 * 100, 3),
        "components": components,
    }


def preview(path, image):
    font = ImageFont.load_default(size=14)
    zooms = (1, 4, 6)
    gap, header = 14, 22
    width = gap + sum(64 * z + gap for z in zooms)
    row = header + 64 * 6 + gap
    out = Image.new("RGB", (width, gap + 2 * row), (39, 43, 45))
    draw = ImageDraw.Draw(out)
    for bg in range(2):
        top = gap + bg * row
        x = gap
        for z in zooms:
            w = 64 * z
            draw.text(
                (x, top), f"{z}x {'light' if bg else 'dark'}", fill="white", font=font
            )
            y = top + header
            cell = 8 * z
            for yy in range(0, w, cell):
                for xx in range(0, w, cell):
                    check = (xx // cell + yy // cell) % 2
                    v = (218 + check * 20) if bg else (46 + check * 9)
                    draw.rectangle(
                        (x + xx, y + yy, x + xx + cell - 1, y + yy + cell - 1),
                        fill=(v, v, v),
                    )
            im = image.resize((w, w), Image.Resampling.NEAREST)
            out.paste(im, (x, y), im)
            x += w + gap
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
    args = parser.parse_args()
    if args.preview:
        if args.preview.suffix.lower() != ".png":
            parser.error("--preview must be a .png path")
        if args.preview.resolve().is_relative_to(ROOT / "Textures"):
            parser.error("--preview must be outside runtime textures")
    image = cutout(draw_card())
    report = inspect(image)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output, optimize=True)
    report["sha256"] = hashlib.sha256(args.output.read_bytes()).hexdigest()
    if args.preview:
        preview(args.preview, image)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
