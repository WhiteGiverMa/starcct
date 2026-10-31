"""Draw the three sealed-pellet-bag tiers; the carton and sheets are read-only.

Requires Python 3.13+ and Pillow 11+. No historical generator is imported.
Geometry uses the original artists' supersampling/cutout approach and palette.
"""

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
TEXTURES = ROOT / "Textures/Things/Item/Resource/PlasticGranule"
SIZE = 64
SS = 8
INK = (0, 0, 0, 255)


def canvas():
    return Image.new("RGBA", (SIZE * SS, SIZE * SS))


def pouch(target, center, scale=1.0, angle=0, seed=1, shade=1.0):
    """One flexible pouch, nominally 16 x 23 pixels including its contour.

    All sizes share the same seal and folds. Bigger bags contain more pellets,
    rather than making the pellets themselves 1.6 times larger.
    """
    layer = canvas()
    draw = ImageDraw.Draw(layer)
    radians = math.radians(angle)
    cos, sin = math.cos(radians), math.sin(radians)

    def point(x, y):
        return (
            round((center[0] + scale * (x * cos - y * sin)) * SS),
            round((center[1] + scale * (x * sin + y * cos)) * SS),
        )

    def color(rgb):
        return tuple(round(c * shade) for c in rgb) + (255,)

    def polygon(points, rgb):
        draw.polygon([point(*p) for p in points], fill=color(rgb))

    def line(points, rgb, width=0.5):
        draw.line(
            [point(*p) for p in points],
            fill=color(rgb),
            width=max(1, round(width * SS * scale)),
            joint="curve",
        )

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
                    x + rx * math.cos(t * math.tau / 12),
                    y + ry * math.sin(t * math.tau / 12),
                )
                for t in range(12)
            ]
            polygon(pellet, (215, 227, 215))
            line(pellet[:7], (133, 161, 156), 0.22 / scale)
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
    # A constant screen-space contour keeps small bags bold, big ones supple.
    draw.line(
        [point(*p) for p in outline + [outline[0]]],
        fill=INK,
        width=round(1.35 * SS),
        joint="curve",
    )
    target.alpha_composite(layer)


def cutout(image):
    image = image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    alpha = image.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    image.putalpha(alpha)
    clean = Image.new("RGBA", image.size)
    clean.paste(image, mask=alpha)
    return clean


def generate():
    a, b, c = canvas(), canvas(), canvas()
    pouch(a, (32, 32), angle=-7, seed=101)
    # Identical small-bag geometry; only placement, angle and contents change.
    pouch(b, (24, 28), angle=-18, seed=102, shade=0.96)
    pouch(b, (39, 29), angle=14, seed=103, shade=0.98)
    pouch(b, (31, 39), angle=-6, seed=101)
    # Bottom -> top: visible offset seams, side folds and lower gussets.
    pouch(c, (36, 28), scale=1.6, angle=12, seed=201, shade=0.90)
    pouch(c, (25, 32), scale=1.6, angle=-18, seed=202, shade=0.95)
    pouch(c, (34, 35), scale=1.6, angle=-7, seed=203)
    return dict(zip("abc", map(cutout, (a, b, c))))


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
    if alpha != [0, 255] or dirty or len(components) != 1:
        raise ValueError(
            f"Invalid cutout: alpha={alpha}, dirty RGB={dirty}, components={components}"
        )
    return {
        "size": list(image.size),
        "mode": image.mode,
        "alpha": alpha,
        "transparent_rgb_nonzero": dirty,
        "bbox": image.getbbox(),
        "coverage_percent": sum(components) / 4096 * 100,
        "components": components,
    }


def preview(path, after, before_dir, zoom):
    """Four tiers at native size and nearest zoom, dark and light checkerboards."""
    states = []
    if before_dir:
        states.append(
            (
                "BEFORE",
                {
                    s: Image.open(before_dir / f"PlasticGranule_{s}.png").convert(
                        "RGBA"
                    )
                    for s in "abcd"
                },
            )
        )
    states.append(("AFTER", after))
    tile, gap, header = 64 * zoom, 12, 28
    row_height = header + 64 + 8 + tile + gap
    out = Image.new(
        "RGB",
        (4 * (tile + gap) + gap, len(states) * 2 * row_height + gap),
        (39, 43, 45),
    )
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default(size=14)
    for state_index, (name, images) in enumerate(states):
        for bg in range(2):
            top = gap + (state_index * 2 + bg) * row_height
            for col, tier in enumerate("abcd"):
                x = gap + col * (tile + gap)
                draw.text(
                    (x, top),
                    f"{name}  _{tier}  1x / {zoom}x  {'light' if bg else 'dark'}",
                    fill="white",
                    font=font,
                )
                for factor, y in ((1, top + header), (zoom, top + header + 72)):
                    width = 64 * factor
                    left = x + (tile - width) // 2
                    for yy in range(0, width, 8 * factor):
                        for xx in range(0, width, 8 * factor):
                            check = (xx // (8 * factor) + yy // (8 * factor)) % 2
                            value = (218 + check * 20) if bg else (46 + check * 9)
                            draw.rectangle(
                                (
                                    left + xx,
                                    y + yy,
                                    left + xx + 8 * factor - 1,
                                    y + yy + 8 * factor - 1,
                                ),
                                fill=(value, value, value),
                            )
                    im = images[tier].resize((width, width), Image.Resampling.NEAREST)
                    out.paste(im, (left, y), im)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=TEXTURES,
        help="Write only PlasticGranule_a/b/c.png here (default: repository texture folder)",
    )
    parser.add_argument(
        "--preview",
        type=Path,
        help="Optional contact-sheet PNG path, outside runtime textures",
    )
    parser.add_argument(
        "--before-dir",
        type=Path,
        help="Optional folder containing before PlasticGranule_a/b/c/d.png",
    )
    parser.add_argument("--preview-zoom", type=int, choices=(4, 6), default=4)
    args = parser.parse_args()
    if args.before_dir and not args.preview:
        parser.error("--before-dir requires --preview")
    if args.preview and args.preview.suffix.lower() != ".png":
        parser.error("--preview must be a .png path")
    if args.preview and (
        args.preview.resolve().is_relative_to(ROOT / "Textures")
        or args.preview.resolve().is_relative_to(args.output_dir.resolve())
    ):
        parser.error("--preview must be outside runtime textures and --output-dir")
    if args.before_dir:
        for tier in "abcd":
            if not (args.before_dir / f"PlasticGranule_{tier}.png").is_file():
                parser.error(f"--before-dir missing PlasticGranule_{tier}.png")
    images = generate()
    report = {tier: inspect(im) for tier, im in images.items()}
    with Image.open(TEXTURES / "PlasticGranule_d.png") as carton:
        images["d"] = carton.copy()
    report["d"] = inspect(images["d"])
    if not all(
        report[x]["coverage_percent"] < report[y]["coverage_percent"]
        for x, y in zip("abc", "bcd")
    ):
        raise ValueError("Expected strictly increasing a < b < c < d coverage")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for tier in "abc":
        images[tier].save(args.output_dir / f"PlasticGranule_{tier}.png", optimize=True)
    for tier in "abcd":
        path = (
            TEXTURES if tier == "d" else args.output_dir
        ) / f"PlasticGranule_{tier}.png"
        report[tier]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    if args.preview:
        preview(args.preview, images, args.before_dir, args.preview_zoom)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
