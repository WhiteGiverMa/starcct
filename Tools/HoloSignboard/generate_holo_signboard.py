"""Generate every holographic signboard texture with local Pillow drawing.

Python 3.13+ / Pillow 11+; no numpy, network service, source mod texture, or
external artwork is required. Windows Chinese fonts are the only host assets.
All geometry is supersampled and reduced with Lanczos. Fixed random seeds make
rice grains, breading and char siu glaze deterministic.

Run from the repository root:

    py -3.15 Tools/HoloSignboard/generate_holo_signboard.py

Outputs (18 runtime PNGs):
  Textures/Things/Building/HoloSignboard/      standing 2x1 sign (9 PNGs)
  Textures/Things/Building/WallHoloSignboard/  wall-mounted 1x1 sign (9 PNGs)
Contact sheets, world-scale verification composites and an alpha/geometry
report are written beside this script.

Wall rotation semantics follow vanilla Placeworker_AttachedToWall: the wall is
the cell in the rotation's facing direction (Rot North = wall to the north).
Map holograms are deliberately narrow top-down ribbons; the full frontal menu
is retained only in WallHoloSignboard_UI.png and the detail preview crops.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Textures" / "Things" / "Building" / "HoloSignboard"
WALL_OUT = ROOT / "Textures" / "Things" / "Building" / "WallHoloSignboard"
TOOL_DIR = Path(__file__).resolve().parent
PREVIEW = TOOL_DIR / "preview.png"
PREVIEW_WALL = TOOL_DIR / "preview_wall.png"
VERIFY_STANDING = TOOL_DIR / "verify_standing.png"
REPORT = TOOL_DIR / "texture_report.json"

BASE_SOUTH_SIZE = (640, 384)
BASE_SIDE_SIZE = (384, 640)
HOLO_SIZE = (1024, 1024)
WALL_BASE_SIZE = (256, 256)
BASE_SCALE = 4
HOLO_SCALE = 3

# XML contracts (Defs/ThingDefs/AyameICCT_Buildings_HoloSignboard.xml).
STAND_BASE_DRAW = (2.4, 1.6)
STAND_HOLO_DRAW = 3.8
STAND_HOLO_OFFSET = 0.73
WALL_BASE_DRAW = 1.0
WALL_HOLO_DRAW = 2.6
WALL_BASE_OFFSETS = {
    "north": (0.0, 0.9),
    "south": (0.0, -0.9),
    "east": (0.9, 0.0),
    "west": (-0.9, 0.0),
}
WALL_HOLO_OFFSETS = {
    # The square hologram canvas is centred just inside the room. The actual
    # pixels are anchored to the base emitter below, rather than to this centre.
    "north": (0.0, 0.72),
    "south": (0.0, -0.72),
    "east": (0.72, 0.0),
    "west": (-0.72, 0.0),
}
# The build-menu icon deliberately retains the old, full frontal composition.
WALL_UI_HOLO_OFFSET = (0.0, 1.25)
# Direction of the supporting wall cell for each rotation (vanilla semantics).
WALL_CELL = {"north": (0, 1), "south": (0, -1), "east": (1, 0), "west": (-1, 0)}
RESAMPLE = Image.Resampling.LANCZOS

FONT_DIR = Path(r"C:\Windows\Fonts")
FONT_SERIF = FONT_DIR / "NotoSerifSC-VF.ttf"
FONT_SANS = FONT_DIR / "NotoSansSC-VF.ttf"
FONT_YAHEI = FONT_DIR / "msyhbd.ttc"
FONT_LATIN = FONT_DIR / "bahnschrift.ttf"
FONT_MONO = FONT_DIR / "CascadiaMono.ttf"

BLACK = (0, 0, 0, 255)
NEON = (91, 255, 24, 255)
MINT = (197, 255, 145, 255)
DEEP_GREEN = (3, 65, 39, 255)
SUNSET = (239, 62, 48, 255)
GOLD = (255, 211, 91, 255)
CREAM = (255, 246, 207, 255)


@lru_cache(maxsize=96)
def get_font(path: str, pixels: int, variation: str = "") -> ImageFont.FreeTypeFont:
    """Load a real CJK font; variable Noto fonts allow a true display weight."""
    candidates = [Path(path)]
    if "Noto" in Path(path).name:
        candidates.append(FONT_YAHEI)
    elif "msyh" in Path(path).name:
        candidates.extend((FONT_SANS, FONT_DIR / "simhei.ttf"))
    else:
        candidates.append(FONT_DIR / "arial.ttf")
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            font = ImageFont.truetype(str(candidate), pixels)
            if variation and "Noto" in candidate.name:
                try:
                    font.set_variation_by_name(variation)
                except (OSError, ValueError):
                    pass
            return font
        except OSError as exc:
            last_error = exc
    raise RuntimeError(f"No usable font for {path}: {last_error}")


class Pen:
    """Draw in final-image coordinates on a supersampled RGBA canvas.

    Pillow replaces (rather than blends) RGBA pixels when drawing onto an RGBA
    image, which would punch holes through food and panels. Translucent
    primitives are therefore rendered on a bbox-sized layer and
    alpha-composited ("over"); set ``blend = False`` for a deliberate replace.
    """

    def __init__(self, image: Image.Image, scale: int):
        self.image = image
        self.scale = scale
        self.draw = ImageDraw.Draw(image, "RGBA")
        self.blend = True

    def points(self, points):
        return [(round(x * self.scale), round(y * self.scale)) for x, y in points]

    def box(self, box):
        return tuple(round(v * self.scale) for v in box)

    def _render(self, bbox, colours, fn):
        translucent = any(c is not None and len(c) == 4 and c[3] < 255 for c in colours)
        if not (self.blend and translucent):
            fn(self.draw, 0, 0)
            return
        x0, y0, x1, y1 = bbox
        x0 = max(0, int(x0) - 2)
        y0 = max(0, int(y0) - 2)
        x1 = min(self.image.width, int(x1) + 3)
        y1 = min(self.image.height, int(y1) + 3)
        if x1 <= x0 or y1 <= y0:
            return
        layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        fn(ImageDraw.Draw(layer, "RGBA"), x0, y0)
        self.image.alpha_composite(layer, (x0, y0))

    @staticmethod
    def _bounds(pts, pad=0):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)

    @staticmethod
    def _shift(pts, ox, oy):
        return [(x - ox, y - oy) for x, y in pts]

    @staticmethod
    def _shift_box(b, ox, oy):
        return (b[0] - ox, b[1] - oy, b[2] - ox, b[3] - oy)

    def polygon(self, points, fill):
        pts = self.points(points)
        self._render(
            self._bounds(pts),
            (fill,),
            lambda d, ox, oy: d.polygon(self._shift(pts, ox, oy), fill=fill),
        )

    def line(self, points, fill, width=1.0):
        pts = self.points(points)
        w = max(1, round(width * self.scale))
        self._render(
            self._bounds(pts, w),
            (fill,),
            lambda d, ox, oy: d.line(
                self._shift(pts, ox, oy), fill=fill, width=w, joint="curve"
            ),
        )

    def rectangle(self, box, fill, outline=None, width=1.0):
        b = self.box(box)
        w = max(1, round(width * self.scale))
        self._render(
            b,
            (fill, outline),
            lambda d, ox, oy: d.rectangle(
                self._shift_box(b, ox, oy), fill=fill, outline=outline, width=w
            ),
        )

    def rounded(self, box, radius, fill, outline=None, width=1.0):
        b = self.box(box)
        w = max(1, round(width * self.scale))
        r = round(radius * self.scale)
        self._render(
            b,
            (fill, outline),
            lambda d, ox, oy: d.rounded_rectangle(
                self._shift_box(b, ox, oy),
                radius=r,
                fill=fill,
                outline=outline,
                width=w,
            ),
        )

    def ellipse(self, box, fill, outline=None, width=1.0):
        b = self.box(box)
        w = max(1, round(width * self.scale))
        self._render(
            b,
            (fill, outline),
            lambda d, ox, oy: d.ellipse(
                self._shift_box(b, ox, oy), fill=fill, outline=outline, width=w
            ),
        )

    def arc(self, box, start, end, fill, width=1.0):
        b = self.box(box)
        w = max(1, round(width * self.scale))
        self._render(
            b,
            (fill,),
            lambda d, ox, oy: d.arc(
                self._shift_box(b, ox, oy), start=start, end=end, fill=fill, width=w
            ),
        )

    def text(
        self,
        xy,
        text,
        font_path,
        size,
        fill,
        anchor="mm",
        variation="",
        stroke_width=0.0,
        stroke_fill=None,
    ):
        font = get_font(str(font_path), round(size * self.scale), variation)
        pos = self.points([xy])[0]
        sw = round(stroke_width * self.scale)
        bbox = self.draw.textbbox(pos, text, font=font, anchor=anchor, stroke_width=sw)
        self._render(
            bbox,
            (fill, stroke_fill),
            lambda d, ox, oy: d.text(
                (pos[0] - ox, pos[1] - oy),
                text,
                font=font,
                fill=fill,
                anchor=anchor,
                stroke_width=sw,
                stroke_fill=stroke_fill,
            ),
        )


def new_canvas(size, scale):
    return Image.new("RGBA", (size[0] * scale, size[1] * scale), (0, 0, 0, 0))


def vertical_gradient(size, top, bottom):
    ramp = Image.linear_gradient("L").resize(size, Image.Resampling.BILINEAR)
    return Image.composite(
        Image.new("RGBA", size, bottom), Image.new("RGBA", size, top), ramp
    )


def shifted(mask: Image.Image, dx: int, dy: int):
    out = Image.new("L", mask.size, 0)
    out.paste(mask, (dx, dy))
    return out


def alpha_scaled(mask: Image.Image, factor: float):
    return mask.point(lambda a: max(0, min(255, round(a * factor))))


def dilate(mask: Image.Image, radius: int):
    if radius <= 0:
        return mask
    return mask.filter(ImageFilter.MaxFilter(radius * 2 + 1))


def finish(image: Image.Image, size):
    """Downsample once and remove hidden RGB from fully transparent pixels."""
    out = image.resize(size, RESAMPLE)
    alpha = out.getchannel("A").point(lambda a: 0 if a < 3 else a)
    out.putalpha(alpha)
    visible = alpha.point(lambda a: 255 if a else 0)
    clean = Image.new("RGBA", size, (0, 0, 0, 0))
    clean.paste(out, (0, 0), visible)
    clean.putalpha(alpha)
    return clean


def clip_alpha(image: Image.Image, bounds):
    """Keep even the faintest glow inside the measured CeleTech content rect."""
    x0, y0, x1, y1 = bounds
    clip = Image.new("L", image.size, 0)
    ImageDraw.Draw(clip).rectangle((x0, y0, x1 - 1, y1 - 1), fill=255)
    alpha = ImageChops.multiply(image.getchannel("A"), clip)
    clean = Image.new("RGBA", image.size, (0, 0, 0, 0))
    clean.paste(image, (0, 0), clip)
    clean.putalpha(alpha)
    return clean


def polygon_mask(size, points, scale):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon(
        [(round(x * scale), round(y * scale)) for x, y in points], fill=255
    )
    return mask


def ramp_alpha(size, box, a_start, a_end, horizontal=False):
    """Full-canvas L mask with a linear ramp inside ``box`` (canvas pixels).

    Vertical ramps run top -> bottom, horizontal ramps left -> right.
    """
    x0, y0, x1, y1 = (round(v) for v in box)
    ramp = Image.linear_gradient("L")
    if horizontal:
        ramp = ramp.transpose(Image.Transpose.TRANSPOSE)
    ramp = ramp.point(lambda v: round(a_start + (a_end - a_start) * v / 255))
    ramp = ramp.resize((max(1, x1 - x0), max(1, y1 - y0)), Image.Resampling.BILINEAR)
    out = Image.new("L", size, 0)
    out.paste(ramp, (x0, y0))
    return out


def colour_layer(size, colour, alpha_mask):
    layer = Image.new("RGBA", size, colour[:3] + (0,))
    layer.putalpha(alpha_mask)
    return layer


def solve_linear(a, b):
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[pivot] = m[pivot], m[col]
        div = m[col][col]
        m[col] = [v / div for v in m[col]]
        for r in range(n):
            if r != col and m[r][col]:
                f = m[r][col]
                m[r] = [rv - f * cv for rv, cv in zip(m[r], m[col])]
    return [m[i][n] for i in range(n)]


def perspective_warp(image, src_quad, dst_quad, scale):
    """Projectively map src_quad onto dst_quad (final coords, TL/TR/BR/BL)."""
    rows, rhs = [], []
    for (x, y), (u, v) in zip(dst_quad, src_quad):
        x, y, u, v = x * scale, y * scale, u * scale, v * scale
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rhs.append(u)
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        rhs.append(v)
    coeffs = solve_linear(rows, rhs)
    return image.transform(
        image.size,
        Image.Transform.PERSPECTIVE,
        coeffs,
        Image.Resampling.BICUBIC,
    )


def composite_at(base, layer, x, y):
    """alpha_composite that tolerates negative or overflowing offsets."""
    temp = Image.new("RGBA", base.size, (0, 0, 0, 0))
    temp.paste(layer, (round(x), round(y)))
    base.alpha_composite(temp)


def world_composite(layers, ppu, x_range, z_range, background=(0, 0, 0, 0)):
    """Place textures by RimWorld world coordinates (x right, z up).

    ``layers`` holds (image, (center_x, center_z), (draw_w, draw_h)).
    """
    width = round((x_range[1] - x_range[0]) * ppu)
    height = round((z_range[1] - z_range[0]) * ppu)
    out = Image.new("RGBA", (width, height), background)
    for image, (cx, cz), (dw, dh) in layers:
        w, h = round(dw * ppu), round(dh * ppu)
        scaled = image.resize((w, h), RESAMPLE)
        composite_at(
            out,
            scaled,
            (cx - dw / 2 - x_range[0]) * ppu,
            (z_range[1] - (cz + dh / 2)) * ppu,
        )
    return out


def stand_holo_y(z):
    """Standing hologram texture row for world z (offset 0.73, size 3.8)."""
    return 512 + (STAND_HOLO_OFFSET - z) * HOLO_SIZE[1] / STAND_HOLO_DRAW


def stand_base_z(y):
    return (BASE_SOUTH_SIZE[1] / 2 - y) * STAND_BASE_DRAW[1] / BASE_SOUTH_SIZE[1]


# --------------------------------------------------------------------- base


def draw_base_south():
    image = new_canvas(BASE_SOUTH_SIZE, BASE_SCALE)
    p = Pen(image, BASE_SCALE)

    # Stepped black silhouette: same 405 x 172 px footprint as CeleTech.
    p.rounded((125, 146, 516, 318), 11, BLACK)
    p.rounded((512, 163, 525, 208), 7, BLACK)
    p.rounded((120, 196, 136, 222), 5, BLACK)
    p.rounded((120, 289, 137, 312), 5, BLACK)
    p.rectangle((127, 303, 515, 317), BLACK)

    # Lower casting and bevelled front apron.
    p.polygon(
        [(132, 274), (510, 274), (510, 304), (503, 311), (139, 311), (132, 305)],
        (82, 82, 82, 255),
    )
    p.rectangle((137, 283, 505, 302), (134, 134, 134, 255))
    p.rectangle((137, 302, 505, 307), (96, 96, 96, 255))
    p.line([(140, 309), (501, 309)], (57, 57, 57, 255), 1.4)
    p.line([(139, 286), (503, 286)], (188, 188, 188, 255), 1.2)
    p.polygon([(132, 282), (144, 282), (137, 302), (132, 302)], (120, 120, 120, 255))
    p.polygon([(498, 282), (510, 282), (510, 302), (504, 302)], (70, 70, 70, 255))

    # Upper metal shell and the recessed holographic emission trough.
    p.polygon(
        [(136, 154), (504, 154), (511, 162), (511, 220), (131, 220), (131, 162)],
        (246, 246, 246, 255),
    )
    p.polygon(
        [(141, 159), (499, 159), (505, 165), (505, 216), (136, 216), (136, 165)],
        (134, 134, 134, 255),
    )
    p.rectangle((141, 167, 502, 217), (246, 246, 246, 255))
    p.rectangle((145, 174, 499, 211), (40, 40, 40, 255))
    p.rectangle((146, 175, 498, 184), (82, 82, 82, 255))
    p.rectangle((146, 185, 498, 201), (40, 40, 40, 255))
    p.rectangle((146, 201, 498, 207), (57, 57, 57, 255))
    p.line([(148, 176), (496, 176)], (120, 120, 120, 255), 1.0)
    p.line([(148, 208), (496, 208)], (0, 0, 0, 255), 1.4)
    # Emitter guide rails and tiny status lights remain inside the dark slot.
    p.line([(157, 189), (483, 189)], (23, 48, 29, 255), 1.0)
    for x in (158, 169, 471, 482):
        p.rectangle((x, 190, x + 5, 192), (77, 165, 83, 255))
    p.line([(145, 214), (500, 214)], (255, 255, 255, 255), 1.0)

    # Broad silver fascia, matching the reference's 191-grey front plane.
    p.rectangle((131, 220, 511, 282), (191, 191, 191, 255))
    p.line([(136, 222), (506, 222)], (220, 220, 220, 255), 1.1)
    p.line([(136, 280), (506, 280)], (154, 154, 154, 255), 1.0)
    p.line([(135, 224), (135, 276)], (197, 197, 197, 255), 1.0)
    p.line([(507, 224), (507, 276)], (161, 161, 161, 255), 1.0)
    p.rectangle((515, 172, 519, 201), (96, 96, 96, 255))
    p.rectangle((123, 202, 128, 216), (82, 82, 82, 255))
    p.rectangle((123, 295, 128, 305), (96, 96, 96, 255))

    # Tea-restaurant franchise badge replaces CELE TECH without moving the shell.
    p.rounded((267, 232, 375, 273), 3, (96, 96, 96, 255))
    p.rounded(
        (270, 233, 372, 270),
        2,
        (24, 51, 35, 255),
        outline=(211, 171, 72, 255),
        width=1.1,
    )
    p.rectangle((272, 235, 370, 238), (209, 55, 42, 255))
    p.text((321, 250), "ICCT", FONT_LATIN, 21, (255, 241, 192, 255))
    p.text((321, 263), "茶 餐 厅", FONT_YAHEI, 9.5, (147, 255, 132, 255))
    p.ellipse((278, 243, 282, 247), (255, 82, 47, 255))
    p.ellipse((360, 243, 364, 247), (106, 255, 48, 255))

    # Understated fasteners and green power indicators.
    for x in (148, 494):
        p.ellipse((x - 2, 253, x + 2, 257), (120, 120, 120, 255))
        p.line([(x - 1.2, 255), (x + 1.2, 255)], (70, 70, 70, 255), 0.7)
    p.rectangle((150, 266, 174, 268), (153, 153, 153, 255))
    p.rectangle((468, 266, 492, 268), (153, 153, 153, 255))
    return clip_alpha(finish(image, BASE_SOUTH_SIZE), (120, 147, 525, 319))


def draw_base_west():
    image = new_canvas(BASE_SIDE_SIZE, BASE_SCALE)
    p = Pen(image, BASE_SCALE)

    p.polygon(
        [
            (158, 146),
            (241, 146),
            (271, 168),
            (271, 535),
            (264, 552),
            (137, 552),
            (128, 543),
            (128, 168),
        ],
        BLACK,
    )
    p.polygon(
        [
            (162, 155),
            (236, 155),
            (261, 173),
            (261, 532),
            (255, 542),
            (143, 542),
            (138, 536),
            (138, 173),
        ],
        (212, 212, 212, 255),
    )
    p.polygon([(162, 155), (236, 155), (260, 173), (139, 173)], (229, 229, 229, 255))
    p.line([(140, 174), (140, 497)], (248, 248, 248, 255), 1.2)
    p.line([(259, 176), (259, 495)], (153, 153, 153, 255), 1.4)

    # Long side-on emitter: x=200 is also the side hologram's alignment axis.
    p.rounded((163, 167, 239, 478), 9, (246, 246, 246, 255))
    p.rounded((168, 179, 233, 468), 4, (120, 120, 120, 255))
    p.rectangle((173, 190, 229, 457), (40, 40, 40, 255))
    p.rectangle((173, 190, 182, 457), (57, 57, 57, 255))
    p.rectangle((209, 190, 216, 457), (60, 60, 60, 255))
    p.rectangle((216, 190, 229, 457), (40, 40, 40, 255))
    p.line([(177, 193), (177, 453)], (82, 82, 82, 255), 1.0)
    p.line([(225, 194), (225, 452)], (23, 48, 29, 255), 1.1)
    for y in (207, 224, 424, 441):
        p.rectangle((218, y, 225, y + 3), (78, 177, 77, 255))
    p.line([(169, 471), (234, 471)], (255, 255, 255, 255), 1.1)

    # Faceted bottom casting and the two reference ventilation recesses.
    p.polygon(
        [
            (138, 502),
            (163, 478),
            (237, 478),
            (261, 502),
            (261, 537),
            (255, 542),
            (143, 542),
            (138, 537),
        ],
        (120, 120, 120, 255),
    )
    p.polygon(
        [(138, 502), (163, 478), (163, 537), (143, 542), (138, 537)],
        (146, 146, 146, 255),
    )
    p.polygon([(163, 478), (237, 478), (261, 502), (163, 502)], (165, 165, 165, 255))
    p.rectangle((164, 486, 193, 533), (82, 82, 82, 255))
    p.rectangle((169, 489, 190, 531), (96, 96, 96, 255))
    p.rectangle((200, 489, 217, 515), (82, 82, 82, 255))
    p.rectangle((203, 491, 214, 513), (96, 96, 96, 255))
    p.line([(143, 539), (255, 539)], (60, 60, 60, 255), 1.4)

    # Small vertical franchise plaque on the matching side plane.
    p.polygon([(238, 329), (259, 341), (259, 396), (238, 385)], (110, 110, 110, 255))
    p.polygon([(241, 336), (256, 344), (256, 389), (241, 381)], (24, 51, 35, 255))
    p.line([(242, 337), (255, 344)], (232, 64, 43, 255), 2.0)
    for letter, y in zip("ICCT", (348, 360, 372, 384)):
        p.text((248, y), letter, FONT_LATIN, 13, (255, 241, 192, 255))
    return clip_alpha(finish(image, BASE_SIDE_SIZE), (129, 147, 271, 552))


# ----------------------------------------------------------- hologram panel
# The emitter trough of HoloSignboardBase_south spans base rows 174-211, which
# at drawOffset (0,0,0.73) / drawSize 3.8 lands on hologram rows ~689-730.
# The panel body ends above it and a trapezoid projection skirt plunges into
# the trough, with its brightest emission line inside the dark slot and an
# alpha feather that dies out by row ~748.
STAND_BODY_BOTTOM = 676
STAND_EMIT_Y = 717
STAND_CLIP = (296, 140, 728, 752)


def panel_polygon():
    return [
        (337, 164),
        (687, 164),
        (702, 179),
        (702, 664),
        (690, STAND_BODY_BOTTOM),
        (334, STAND_BODY_BOTTOM),
        (321, 664),
        (321, 179),
    ]


def stand_skirt_polygon():
    return [
        (327, STAND_BODY_BOTTOM - 6),
        (697, STAND_BODY_BOTTOM - 6),
        (679, STAND_EMIT_Y + 1),
        (345, STAND_EMIT_Y + 1),
    ]


def clipped_overlay(base, overlay, mask):
    alpha = ImageChops.multiply(overlay.getchannel("A"), mask)
    overlay.putalpha(alpha)
    base.alpha_composite(overlay)


def fancy_text(
    image,
    text,
    center,
    size,
    font_path=FONT_SERIF,
    variation="Black",
    top_colour=(255, 128, 54, 255),
    bottom_colour=(226, 42, 49, 255),
    rim=(255, 225, 124),
    dark_rim=(141, 24, 43),
    shade=(103, 20, 43),
    glow=(255, 71, 27),
    glow_alpha=0.48,
    top=None,
):
    """Gradient CJK display lettering with neon rim, extrusion and halo.

    ``center`` is in final coordinates; pass ``top`` to anchor the glyph top.
    """
    scale = HOLO_SCALE
    k = size / 92
    font = get_font(str(font_path), round(size * scale), variation)
    bbox = font.getbbox(text)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = max(6, round(18 * k)) * scale
    mask = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    ImageDraw.Draw(mask).text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=255)

    def px(v):
        return max(1, round(v * k * scale))

    tile = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    halo = mask.filter(ImageFilter.GaussianBlur(px(7)))
    tile.alpha_composite(colour_layer(mask.size, glow, alpha_scaled(halo, glow_alpha)))
    outer = dilate(mask, px(5))
    tile.alpha_composite(
        colour_layer(mask.size, shade, alpha_scaled(shifted(outer, px(3), px(4)), 0.94))
    )
    tile.alpha_composite(colour_layer(mask.size, rim, dilate(mask, px(4))))
    tile.alpha_composite(colour_layer(mask.size, dark_rim, dilate(mask, px(2))))
    gradient = vertical_gradient(mask.size, top_colour, bottom_colour)
    gradient.putalpha(mask)
    tile.alpha_composite(gradient)
    top_glint = ImageChops.subtract(mask, shifted(mask, 0, px(2)))
    tile.alpha_composite(
        colour_layer(mask.size, (255, 211, 138), alpha_scaled(top_glint, 0.72))
    )

    x = round(center[0] * scale - tile.width / 2)
    if top is None:
        y = round(center[1] * scale - tile.height / 2)
    else:
        y = round(top * scale - pad)
    composite_at(image, tile, x, y)


def add_title(image):
    fancy_text(image, "茶餐厅", (512, 0), 92, top=179)


def hex_lattice(p: Pen, x0, y0, cols, rows, radius=15, colour=(4, 103, 48, 44)):
    for row in range(rows):
        cy = y0 + row * radius * 1.667
        for col in range(cols):
            cx = x0 + col * radius * 1.733 + (radius * 0.867 if row % 2 else 0)
            pts = [
                (
                    cx + radius * math.cos(math.tau * k / 6),
                    cy + radius * math.sin(math.tau * k / 6),
                )
                for k in range(6)
            ]
            p.line(pts + pts[:1], colour, 0.8)
            if (row + col) % 5 == 0:
                p.line(pts[1:3], (218, 255, 169, 42), 0.7)


def holo_surface(image, mask, box, scale=HOLO_SCALE, top_alpha=165, bottom_alpha=116):
    """Layered translucent hologram coating: halo, gradient sheet, edge bloom,
    alternating scanlines, a soft sweep band and fine lattice (all clipped)."""
    x0, y0, x1, y1 = box
    # Outer halo only: never stack it under the sheet, or the glass turns solid.
    halo = mask.filter(ImageFilter.GaussianBlur(11 * scale))
    halo = ImageChops.multiply(halo, ImageChops.invert(mask))
    image.alpha_composite(
        colour_layer(image.size, (76, 255, 22), alpha_scaled(halo, 0.40))
    )

    sheet = vertical_gradient(image.size, (118, 255, 46, 255), (46, 232, 24, 255))
    ramp = ramp_alpha(
        image.size, (0, y0 * scale, image.width, y1 * scale), top_alpha, bottom_alpha
    )
    # The middle of the sheet thins out a little more than its rim.
    core = mask.filter(ImageFilter.GaussianBlur(36 * scale))
    sheet_alpha = ImageChops.subtract(
        ImageChops.multiply(ramp, mask), alpha_scaled(core, 0.14)
    )
    sheet.putalpha(sheet_alpha)
    image.alpha_composite(sheet)

    # Brighter rim fading inward: the hologram reads as luminous coated glass.
    inner = mask.filter(ImageFilter.GaussianBlur(14 * scale))
    edge = ImageChops.subtract(mask, inner)
    image.alpha_composite(
        colour_layer(image.size, (196, 255, 140), alpha_scaled(edge, 0.62))
    )

    pattern = new_canvas((image.width // scale, image.height // scale), scale)
    p = Pen(pattern, scale)
    hex_lattice(p, x0 - 4, y0 + 4, int((x1 - x0) / 26) + 2, int((y1 - y0) / 25) + 2)
    for y in range(int(y0) + 2, int(y1), 6):
        p.line([(x0, y), (x1, y)], (230, 255, 196, 34), 1.3)
        p.line([(x0, y + 3), (x1, y + 3)], (0, 60, 24, 30), 1.3)
    clipped_overlay(image, pattern, mask)

    sweep = Image.new("RGBA", image.size, (0, 0, 0, 0))
    sp = Pen(sweep, scale)
    sweep_y = y0 + (y1 - y0) * 0.58
    sp.rectangle((x0, sweep_y - 9, x1, sweep_y + 9), (225, 255, 190, 30))
    sp.rectangle((x0, sweep_y - 2, x1, sweep_y + 2), (240, 255, 215, 42))
    sweep = sweep.filter(ImageFilter.GaussianBlur(3 * scale))
    clipped_overlay(image, sweep, mask)


def projection_skirt(image, polygon, emit_y, emit_x0, emit_x1, feather=30):
    """Trapezoid beam rising from an emitter slot, brightest at the slot."""
    scale = HOLO_SCALE
    ys = [y for _, y in polygon]
    mask = polygon_mask(image.size, polygon, scale)
    ramp = ramp_alpha(
        image.size, (0, min(ys) * scale, image.width, max(ys) * scale), 62, 188
    )
    image.alpha_composite(
        colour_layer(image.size, (120, 255, 58), ImageChops.multiply(ramp, mask))
    )
    beams = new_canvas((image.width // scale, image.height // scale), scale)
    p = Pen(beams, scale)
    top_y = min(ys)
    top_x0 = min(x for x, y in polygon if y == top_y)
    top_x1 = max(x for x, y in polygon if y == top_y)
    n = 15
    for i in range(n + 1):
        t = i / n
        bx = emit_x0 + (emit_x1 - emit_x0) * t
        tx = top_x0 + (top_x1 - top_x0) * t
        alpha = 120 if i % 3 == 0 else 62
        p.line(
            [(bx, emit_y), (tx, top_y)],
            (226, 255, 190, alpha),
            1.3 if i % 3 == 0 else 0.8,
        )
    clipped_overlay(image, beams, mask)

    # Bloom inside the slot, then a feathered spill that fades out downward.
    glow = Image.new("L", image.size, 0)
    gd = ImageDraw.Draw(glow)
    cx = (emit_x0 + emit_x1) / 2
    rx = (emit_x1 - emit_x0) / 2 + 10
    gd.ellipse(
        tuple(
            round(v * scale)
            for v in (cx - rx, emit_y - 9, cx + rx, emit_y + feather * 0.5)
        ),
        fill=255,
    )
    glow = glow.filter(ImageFilter.GaussianBlur(7 * scale))
    image.alpha_composite(
        colour_layer(image.size, (96, 255, 40), alpha_scaled(glow, 0.78))
    )
    core = Image.new("RGBA", image.size, (0, 0, 0, 0))
    cp = Pen(core, scale)
    cp.line([(emit_x0 + 2, emit_y), (emit_x1 - 2, emit_y)], (210, 255, 160, 235), 4.2)
    cp.line([(emit_x0 + 8, emit_y), (emit_x1 - 8, emit_y)], (250, 255, 235, 255), 1.6)
    image.alpha_composite(core.filter(ImageFilter.GaussianBlur(0.5 * scale)))
    fade = ramp_alpha(
        image.size,
        (0, emit_y * scale, image.width, (emit_y + feather) * scale),
        255,
        0,
    )
    keep_above = Image.new("L", image.size, 255)
    ImageDraw.Draw(keep_above).rectangle(
        (0, round(emit_y * scale), image.width, image.height), fill=0
    )
    image.putalpha(
        ImageChops.multiply(image.getchannel("A"), ImageChops.lighter(fade, keep_above))
    )


def cubic_points(p0, p1, p2, p3, steps=28):
    points = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        points.append(
            (
                u**3 * p0[0]
                + 3 * u * u * t * p1[0]
                + 3 * u * t * t * p2[0]
                + t**3 * p3[0],
                u**3 * p0[1]
                + 3 * u * u * t * p1[1]
                + 3 * u * t * t * p2[1]
                + t**3 * p3[1],
            )
        )
    return points


def add_steam(image, positions):
    layer = new_canvas(HOLO_SIZE, HOLO_SCALE)
    p = Pen(layer, HOLO_SCALE)
    for x, y, height in positions:
        pts = cubic_points(
            (x, y),
            (x - 11, y - height * 0.28),
            (x + 13, y - height * 0.67),
            (x + 2, y - height),
        )
        p.line(pts, (255, 250, 210, 150), 2.1)
        p.line([(px + 2, py) for px, py in pts], (255, 255, 235, 62), 3.8)
    layer = layer.filter(ImageFilter.GaussianBlur(0.7 * HOLO_SCALE))
    image.alpha_composite(layer)


def blob_points(cx, cy, rx, ry, seed, count=30):
    rng = random.Random(seed)
    values = [rng.uniform(0.88, 1.10) for _ in range(count)]
    # Smooth the random radius so curds and sauce read as soft cooked food.
    values = [
        (values[i - 1] + values[i] * 2 + values[(i + 1) % count]) / 4
        for i in range(count)
    ]
    return [
        (
            cx + rx * values[i] * math.cos(math.tau * i / count),
            cy + ry * values[i] * math.sin(math.tau * i / count),
        )
        for i in range(count)
    ]


def rotated_ellipse_points(cx, cy, rx, ry, angle, count=12):
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    points = []
    for i in range(count):
        t = math.tau * i / count
        x, y = rx * math.cos(t), ry * math.sin(t)
        points.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return points


def draw_plate(p: Pen, cx, top):
    # Soft green contact shadow, porcelain body, raised rim and glazed highlight.
    p.ellipse((cx - 70, top + 77, cx + 72, top + 101), (0, 40, 26, 85))
    p.ellipse(
        (cx - 73, top + 25, cx + 74, top + 97),
        (164, 190, 171, 255),
        outline=(40, 91, 63, 210),
        width=1.2,
    )
    p.ellipse(
        (cx - 74, top, cx + 74, top + 73),
        (250, 251, 229, 255),
        outline=(79, 125, 91, 255),
        width=1.4,
    )
    p.ellipse(
        (cx - 66, top + 7, cx + 66, top + 65),
        (219, 229, 197, 255),
        outline=(255, 255, 245, 255),
        width=2.0,
    )
    p.arc((cx - 69, top + 4, cx + 69, top + 72), 9, 168, (255, 255, 250, 255), 2.2)
    p.arc((cx - 68, top + 28, cx + 68, top + 94), 18, 160, (229, 242, 218, 255), 2.0)
    p.arc((cx - 66, top + 31, cx + 66, top + 94), 32, 142, (108, 145, 117, 160), 1.0)
    # Tiny red maker's mark on the front of the white porcelain.
    p.ellipse((cx - 8, top + 78, cx + 8, top + 85), (196, 57, 44, 180))
    p.line([(cx - 5, top + 81), (cx + 5, top + 81)], (255, 221, 157, 220), 0.8)


def rice_mound(p: Pen, cx, cy, rx, ry, seed, grains=74):
    p.polygon(blob_points(cx, cy, rx, ry, seed), (255, 244, 207, 255))
    p.line(blob_points(cx, cy, rx, ry, seed)[:17], (255, 255, 234, 255), 1.4)
    rng = random.Random(seed + 91)
    for i in range(grains):
        angle = rng.uniform(0, math.tau)
        radius = math.sqrt(rng.random()) * 0.90
        x = cx + math.cos(angle) * rx * radius
        y = cy + math.sin(angle) * ry * radius
        grx = rng.uniform(2.2, 3.7)
        gry = rng.uniform(1.0, 1.65)
        colour = rng.choice(
            (
                (255, 255, 238, 255),
                (255, 249, 220, 255),
                (238, 226, 190, 255),
                (255, 252, 229, 255),
            )
        )
        p.polygon(
            rotated_ellipse_points(x, y, grx, gry, rng.uniform(-55, 55), 10), colour
        )
        if i % 3 == 0:
            p.line([(x - 1.4, y - 0.5), (x + 0.8, y - 0.8)], (255, 255, 250, 220), 0.55)


def egg_curd(p: Pen, cx, cy, rx, ry, seed):
    pts = blob_points(cx, cy, rx, ry, seed, 24)
    p.polygon(pts, (244, 166, 33, 255))
    inner = [(cx + (x - cx) * 0.91, cy + (y - cy) * 0.86 - 1) for x, y in pts]
    p.polygon(inner, (255, 202, 55, 255))
    p.polygon(
        blob_points(cx - rx * 0.14, cy - ry * 0.23, rx * 0.65, ry * 0.48, seed + 1, 20),
        (255, 232, 104, 255),
    )
    p.line(
        cubic_points(
            (cx - rx * 0.65, cy),
            (cx - rx * 0.15, cy - ry * 0.5),
            (cx + rx * 0.35, cy + ry * 0.5),
            (cx + rx * 0.7, cy - ry * 0.15),
            16,
        ),
        (227, 143, 26, 220),
        1.0,
    )
    p.line(
        [
            (cx - rx * 0.5, cy - ry * 0.48),
            (cx - rx * 0.08, cy - ry * 0.67),
            (cx + rx * 0.18, cy - ry * 0.55),
        ],
        (255, 249, 164, 240),
        1.2,
    )


def tomato_wedge(p: Pen, cx, cy, size, angle, seed):
    # A chunky wedge with skin, translucent pulp, seed pockets and juice glints.
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)

    def map_pt(x, y):
        return (cx + (x * ca - y * sa) * size, cy + (x * sa + y * ca) * size)

    outer = [
        (-0.9, 0.48),
        (-0.83, -0.28),
        (-0.30, -0.72),
        (0.34, -0.67),
        (0.86, -0.24),
        (0.78, 0.45),
        (0.12, 0.72),
    ]
    p.polygon([map_pt(x, y) for x, y in outer], (154, 28, 36, 255))
    inner = [
        (-0.72, 0.35),
        (-0.67, -0.20),
        (-0.24, -0.53),
        (0.29, -0.50),
        (0.67, -0.18),
        (0.60, 0.31),
        (0.10, 0.53),
    ]
    p.polygon([map_pt(x, y) for x, y in inner], (239, 63, 45, 255))
    pulp = [
        (-0.43, 0.20),
        (-0.39, -0.19),
        (-0.05, -0.37),
        (0.38, -0.26),
        (0.44, 0.13),
        (0.09, 0.35),
    ]
    p.polygon([map_pt(x, y) for x, y in pulp], (255, 111, 52, 255))
    p.polygon(
        [
            map_pt(x, y)
            for x, y in [
                (-0.60, 0.35),
                (0.1, 0.53),
                (0.60, 0.31),
                (0.73, 0.39),
                (0.12, 0.72),
                (-0.9, 0.48),
            ]
        ],
        (199, 38, 38, 255),
    )
    rng = random.Random(seed)
    for x, y in ((-0.20, -0.05), (0.18, -0.10), (0.03, 0.18)):
        x += rng.uniform(-0.04, 0.04)
        sx, sy = map_pt(x, y)
        p.polygon(
            rotated_ellipse_points(sx, sy, 1.8, 0.9, angle + 25, 10),
            (255, 220, 126, 255),
        )
    p.line(
        [map_pt(-0.55, -0.24), map_pt(-0.26, -0.46), map_pt(0.02, -0.43)],
        (255, 205, 155, 245),
        1.3,
    )
    p.line([map_pt(0.50, 0.03), map_pt(0.47, 0.18)], (255, 159, 112, 230), 1.0)


def scallions(p: Pen, cx, cy, seed):
    rng = random.Random(seed)
    for i in range(15):
        x = cx + rng.uniform(-48, 48)
        y = cy + rng.uniform(-22, 23)
        w = rng.uniform(3.0, 5.5)
        h = rng.uniform(2.0, 3.6)
        colour = rng.choice(
            (
                (36, 154, 53, 255),
                (71, 194, 62, 255),
                (122, 224, 80, 255),
                (20, 115, 45, 255),
            )
        )
        p.polygon(
            [
                (x - w, y - h),
                (x + w * 0.6, y - h * 0.6),
                (x + w, y + h),
                (x - w * 0.5, y + h * 0.6),
            ],
            colour,
        )
        if i % 3 == 0:
            p.line(
                [(x - w * 0.5, y - h * 0.5), (x + w * 0.4, y - h * 0.25)],
                (195, 255, 139, 220),
                0.65,
            )


def draw_tomato_egg(image):
    p = Pen(image, HOLO_SCALE)
    add_steam(image, ((388, 352, 25), (423, 349, 29), (454, 354, 22)))
    draw_plate(p, 419, 350)
    rice_mound(p, 419, 374, 59, 37, 1101, 96)
    # Keep rice and tomato jus visible around smaller, distinct egg curds.
    p.polygon(blob_points(421, 380, 48, 23, 1110), (205, 57, 31, 205))
    p.polygon(blob_points(418, 375, 41, 19, 1111), (237, 83, 34, 220))
    for args in (
        (402, 354, 14, 9, 1201),
        (435, 357, 15, 10, 1202),
        (392, 383, 14, 9, 1204),
        (438, 389, 14, 9, 1205),
    ):
        egg_curd(p, *args)
    # Five large, fully exposed red wedges make the tomato half unmistakable.
    for args in (
        (379, 369, 18, -22, 1301),
        (413, 371, 19, 12, 1302),
        (451, 371, 18, -10, 1303),
        (417, 393, 18, -12, 1305),
        (424, 348, 15, 18, 1306),
    ):
        tomato_wedge(p, *args)
    scallions(p, 420, 369, 1401)
    # Juice droplets and a bright porcelain reflection finish the illustration.
    p.ellipse((467, 399, 473, 403), (239, 69, 38, 220))
    p.ellipse((374, 394, 379, 398), (255, 139, 56, 220))
    p.arc((351, 354, 487, 419), 160, 218, (255, 255, 255, 230), 1.5)


def curry_sauce(p: Pen, cx, cy, seed):
    pts = blob_points(cx, cy, 48, 31, seed)
    p.polygon(pts, (139, 74, 22, 255))
    inner = [(cx + (x - cx) * 0.95, cy + (y - cy) * 0.90 - 1) for x, y in pts]
    p.polygon(inner, (191, 112, 30, 255))
    p.polygon(blob_points(cx + 4, cy - 6, 38, 18, seed + 1), (218, 146, 43, 255))
    p.line(
        cubic_points(
            (cx - 28, cy + 9), (cx - 7, cy + 20), (cx + 21, cy + 12), (cx + 35, cy + 2)
        ),
        (255, 194, 78, 210),
        1.6,
    )
    p.line(
        cubic_points(
            (cx - 5, cy - 17), (cx + 9, cy - 23), (cx + 22, cy - 19), (cx + 30, cy - 12)
        ),
        (255, 211, 100, 180),
        1.1,
    )


def vegetable_piece(p: Pen, cx, cy, size, kind, angle):
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    base = [(-0.8, -0.6), (0.55, -0.7), (0.8, 0.45), (-0.55, 0.7)]
    pts = [
        (cx + (x * ca - y * sa) * size, cy + (x * sa + y * ca) * size) for x, y in base
    ]
    if kind == "carrot":
        p.polygon(pts, (150, 64, 22, 255))
        p.polygon(
            [(cx + (x - cx) * 0.86, cy + (y - cy) * 0.82 - 1) for x, y in pts],
            (239, 116, 34, 255),
        )
        p.line(
            [(cx - size * 0.4, cy - size * 0.35), (cx + size * 0.25, cy - size * 0.4)],
            (255, 187, 71, 255),
            1.0,
        )
    else:
        p.polygon(pts, (172, 119, 43, 255))
        p.polygon(
            [(cx + (x - cx) * 0.86, cy + (y - cy) * 0.82 - 1) for x, y in pts],
            (244, 205, 104, 255),
        )
        p.line(
            [(cx - size * 0.4, cy - size * 0.35), (cx + size * 0.25, cy - size * 0.4)],
            (255, 239, 158, 255),
            1.0,
        )


def katsu_slice(p: Pen, x, y, w, h, lean, seed):
    # Each strip has a craggy fried crust and a visible pale pork cut face.
    top = [
        (x, y),
        (x + w - 2, y - 2),
        (x + w + lean, y + h - 10),
        (x + lean + 1, y + h - 7),
    ]
    p.polygon(top, (115, 60, 24, 255))
    crust = [
        (x + 1, y + 1),
        (x + w - 3, y),
        (x + w + lean - 1, y + h - 14),
        (x + lean + 2, y + h - 11),
    ]
    p.polygon(crust, (202, 119, 34, 255))
    p.polygon(
        [
            (x + 2, y + 2),
            (x + w - 4, y + 1),
            (x + w + lean - 3, y + h * 0.40),
            (x + lean + 3, y + h * 0.45),
        ],
        (239, 165, 53, 255),
    )
    face = [
        (x + lean + 1, y + h - 11),
        (x + w + lean - 1, y + h - 14),
        (x + w + lean + 1, y + h - 4),
        (x + lean + 2, y + h),
    ]
    p.polygon(face, (255, 224, 166, 255))
    p.line(
        [(x + lean + 3, y + h - 7), (x + w + lean - 1, y + h - 10)],
        (255, 248, 210, 255),
        1.0,
    )
    p.line(
        [(x + lean + 2, y + h), (x + w + lean + 1, y + h - 4)], (113, 58, 26, 255), 1.0
    )
    rng = random.Random(seed)
    for i in range(13):
        bx = x + rng.uniform(3, w - 3) + lean * rng.random() * 0.5
        by = y + rng.uniform(3, h - 16)
        r = rng.uniform(0.7, 1.6)
        colour = rng.choice(
            (
                (255, 216, 112, 255),
                (177, 99, 29, 255),
                (237, 165, 52, 255),
                (126, 72, 27, 255),
            )
        )
        p.polygon(
            rotated_ellipse_points(bx, by, r, r * 0.65, rng.uniform(-40, 40), 8), colour
        )


def draw_curry_katsu(image):
    p = Pen(image, HOLO_SCALE)
    add_steam(image, ((390, 529, 24), (430, 527, 27), (458, 532, 20)))
    draw_plate(p, 419, 529)
    # Rice sits to the left; curry floods the right and front of the plate.
    rice_mound(p, 396, 554, 38, 33, 2101, 62)
    curry_sauce(p, 441, 574, 2110)
    for args in (
        (455, 583, 8, "potato", 14),
        (431, 590, 7, "carrot", -12),
        (468, 566, 7, "carrot", 18),
        (444, 599, 6, "potato", -8),
        (419, 578, 6, "potato", 20),
    ):
        vegetable_piece(p, *args)
    # Six low, diagonally overlapping slices expose pork and crisp breading.
    for i in range(6):
        katsu_slice(p, 372 + i * 15.5, 542 + i * 1.3, 18, 35, 6.0, 2200 + i)
    scallions(p, 450, 584, 2301)
    p.ellipse((472, 588, 477, 591), (255, 199, 79, 220))
    p.arc((351, 533, 487, 598), 160, 218, (255, 255, 255, 230), 1.5)


def menu_card(image, top, number, name1, name2, english, price):
    p = Pen(image, HOLO_SCALE)
    bottom = top + 162
    p.blend = False  # the card is a darker see-through window in the sheet
    p.rounded(
        (336, top, 688, bottom),
        8,
        (3, 65, 39, 136),
        outline=(195, 255, 128, 205),
        width=1.5,
    )
    p.blend = True
    p.line([(344, top + 3), (498, top + 3)], (241, 255, 186, 150), 1.0)
    p.rectangle((337, top + 12, 340, bottom - 12), (255, 100, 52, 210))
    # Tiny holographic bracket corners and a numbered selection chip.
    p.line([(336, top + 19), (336, top + 7), (350, top + 7)], MINT, 2.0)
    p.line([(674, bottom - 7), (688, bottom - 7), (688, bottom - 20)], MINT, 2.0)
    p.ellipse(
        (649, top + 10, 677, top + 38),
        (115, 255, 62, 48),
        outline=(210, 255, 152, 220),
        width=1.1,
    )
    p.text((663, top + 24), number, FONT_LATIN, 14, CREAM)

    x = 518
    p.text(
        (x, top + 19),
        "CHEF'S SIGNATURE",
        FONT_LATIN,
        8.5,
        (157, 255, 121, 235),
        anchor="lm",
    )
    p.text(
        (x, top + 43),
        name1,
        FONT_SANS,
        23,
        (255, 239, 163, 255),
        anchor="lm",
        variation="Black",
    )
    p.text(
        (x, top + 69),
        name2,
        FONT_SANS,
        23,
        (255, 119, 70, 255),
        anchor="lm",
        variation="Black",
    )
    p.text((x, top + 91), english, FONT_LATIN, 8.5, (202, 255, 175, 220), anchor="lm")
    p.text((x + 24, top + 123), price, FONT_LATIN, 27, (255, 229, 111, 255))
    p.rounded(
        (594, top + 107, 674, top + 137),
        5,
        (230, 62, 45, 230),
        outline=(255, 195, 107, 255),
        width=1.0,
    )
    p.text((634, top + 122), "点单 +", FONT_YAHEI, 13.5, (255, 250, 213, 255))
    p.line([(520, top + 146), (674, top + 146)], (117, 255, 80, 90), 0.8)
    p.text(
        (520, top + 153),
        "FRESH · HOT · SYNTH-FREE",
        FONT_LATIN,
        7.5,
        (171, 255, 137, 180),
        anchor="lm",
    )


def draw_hologram_front():
    # Separate layers ensure menu-card backgrounds never cover the illustrations.
    image = new_canvas(HOLO_SIZE, HOLO_SCALE)
    panel = panel_polygon()
    panel_mask = polygon_mask(image.size, panel, HOLO_SCALE)
    projection_skirt(image, stand_skirt_polygon(), STAND_EMIT_Y, 345, 679, feather=31)
    skirt_floor = image.copy()
    image = new_canvas(HOLO_SIZE, HOLO_SCALE)
    holo_surface(image, panel_mask, (321, 164, 702, STAND_BODY_BOTTOM))

    p = Pen(image, HOLO_SCALE)
    p.line(panel + panel[:1], (170, 255, 104, 215), 2.6)
    inner = [
        (337, 172),
        (681, 172),
        (694, 184),
        (694, 658),
        (683, STAND_BODY_BOTTOM - 8),
        (341, STAND_BODY_BOTTOM - 8),
        (329, 660),
        (329, 184),
    ]
    p.line(inner + inner[:1], (222, 255, 164, 105), 1.0)
    p.line([(321, 185), (321, 652)], (35, 172, 34, 200), 2.0)
    p.rounded((701, 218, 709, 351), 3, (91, 255, 31, 100))
    p.line([(703, 226), (703, 342)], (205, 255, 133, 165), 1.4)

    add_title(image)
    p.rounded(
        (385, 272, 639, 294),
        9,
        (18, 104, 48, 132),
        outline=(220, 255, 155, 120),
        width=0.8,
    )
    p.text(
        (512, 283), "星际加盟店  ·  线上点单", FONT_YAHEI, 16.5, (255, 245, 188, 255)
    )
    p.text(
        (512, 305),
        "INTERSTELLAR CHA CHAAN TENG  //  24H",
        FONT_LATIN,
        9,
        (85, 38, 40, 235),
    )

    menu_card(image, 318, "01", "番茄炒蛋", "盖浇饭", "TOMATO · EGG · RICE", "$38")
    menu_card(image, 489, "02", "咖喱猪排", "盖浇饭", "CURRY · KATSU · RICE", "$46")
    draw_tomato_egg(image)
    draw_curry_katsu(image)

    p = Pen(image, HOLO_SCALE)
    p.ellipse((348, 659, 356, 667), (220, 255, 141, 255))
    p.text(
        (363, 663),
        "ICCT  //  AUTHENTIC RIMWARD FLAVOUR",
        FONT_LATIN,
        8.5,
        (65, 55, 35, 230),
        anchor="lm",
    )
    p.text((676, 663), "ONLINE", FONT_LATIN, 8.5, (101, 29, 38, 240), anchor="rm")
    for y in range(240, 650, 34):
        p.line([(313, y), (317, y)], (121, 255, 72, 105), 1.0)
    for x, y in ((316, 180), (698, 159), (711, 485), (332, 166)):
        p.line([(x - 4, y), (x + 4, y)], (223, 255, 168, 170), 1.0)
        p.line([(x, y - 4), (x, y + 4)], (223, 255, 168, 170), 1.0)

    skirt_floor.alpha_composite(image)
    return clip_alpha(finish(skirt_floor, HOLO_SIZE), STAND_CLIP)


def draw_hologram_west():
    image = new_canvas(HOLO_SIZE, HOLO_SCALE)
    p = Pen(image, HOLO_SCALE)
    blade = [
        (504, 29),
        (514, 30),
        (518, 196),
        (518, 485),
        (522, 632),
        (528, 681),
        (511, 705),
        (490, 682),
        (499, 632),
        (501, 487),
        (500, 195),
    ]
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).polygon(p.points(blade), fill=255)
    halo = mask.filter(ImageFilter.GaussianBlur(8 * HOLO_SCALE))
    layer = Image.new("RGBA", image.size, (71, 255, 24, 0))
    layer.putalpha(alpha_scaled(halo, 0.48))
    image.alpha_composite(layer)

    fill = vertical_gradient(image.size, (154, 255, 93, 190), (44, 232, 23, 130))
    fill.putalpha(alpha_scaled(mask, 0.76))
    image.alpha_composite(fill)
    p.line([(508, 31), (510, 199), (510, 480), (508, 624)], (220, 255, 167, 255), 5.0)
    p.line([(503, 40), (503, 480), (500, 626)], (70, 255, 30, 205), 2.0)
    p.line([(515, 42), (515, 486), (518, 624)], (137, 255, 76, 190), 2.0)

    # Side-on red title and golden menu blocks refract through the green blade.
    for y, h, colour in (
        (185, 58, (255, 89, 48, 180)),
        (253, 25, (255, 190, 65, 165)),
        (332, 77, (255, 98, 47, 145)),
        (424, 41, (255, 214, 88, 180)),
        (507, 68, (255, 101, 48, 135)),
    ):
        p.polygon([(501, y), (517, y + 2), (517, y + h), (501, y + h - 2)], colour)
        p.line([(503, y + 4), (514, y + 4)], (255, 239, 165, 190), 1.0)
    for y in range(50, 623, 17):
        width = 7 if y % 34 else 12
        p.line([(509 - width / 2, y), (509 + width / 2, y)], (228, 255, 177, 120), 0.8)
    # Base-projection flare and top glint reproduce the reference's vertical span.
    p.polygon(
        [(499, 628), (519, 628), (528, 682), (511, 704), (490, 682)], (91, 255, 40, 58)
    )
    p.line([(508, 633), (509, 694)], (225, 255, 175, 165), 2.2)
    p.line([(496, 682), (523, 682)], (160, 255, 94, 145), 1.3)
    p.line([(509, 20), (509, 39)], (230, 255, 193, 185), 1.2)
    p.line([(500, 30), (519, 30)], (213, 255, 158, 200), 1.2)
    p.ellipse((505, 25, 513, 34), (244, 255, 212, 255))
    return clip_alpha(finish(image, HOLO_SIZE), (490, 19, 528, 706))


# ------------------------------------------------------- wall: char siu rice
def choy_sum(p: Pen, M, base, tip, leaf_side, seed, s):
    """A stalk of Cantonese choy sum: pale stem, glossy leaves, yellow buds."""
    rng = random.Random(seed)
    bx, by = base
    tx, ty = tip
    dx, dy = tx - bx, ty - by
    length = math.hypot(dx, dy)
    nx, ny = -dy / length, dx / length
    w = 5.0
    stem = [
        (bx + nx * w, by + ny * w),
        (tx + nx * w * 0.55, ty + ny * w * 0.55),
        (tx - nx * w * 0.55, ty - ny * w * 0.55),
        (bx - nx * w, by - ny * w),
    ]
    p.polygon([M(*q) for q in stem], (150, 205, 96, 255))
    p.line(
        [M(bx + nx * 1.2, by + ny * 1.2), M(tx + nx * 0.6, ty + ny * 0.6)],
        (216, 255, 172, 255),
        1.3 * s,
    )
    p.line(
        [M(bx - nx * 2.8, by - ny * 2.8), M(tx - nx * 1.6, ty - ny * 1.6)],
        (92, 150, 60, 230),
        0.8 * s,
    )
    for t, side, size in (
        (0.52, leaf_side, 1.0),
        (0.78, -leaf_side, 0.82),
        (0.95, leaf_side, 0.9),
    ):
        cx = bx + dx * t
        cy = by + dy * t
        angle = math.degrees(math.atan2(dy, dx)) + side * 34 + rng.uniform(-6, 6)
        a = math.radians(angle)
        ca, sa = math.cos(a), math.sin(a)
        L, W = 34 * size, 15 * size
        pts = []
        for i in range(22):
            u = i / 21
            pts.append((u * L, -W * math.sin(math.pi * u) ** 0.8))
        for i in range(21, -1, -1):
            u = i / 21
            pts.append((u * L, W * 0.85 * math.sin(math.pi * u) ** 0.8))
        world = [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]
        p.polygon([M(*q) for q in world], (24, 112, 42, 255))
        inner = [
            (
                cx + (x * 0.9) * ca - (y * 0.78) * sa,
                cy + (x * 0.9) * sa + (y * 0.78) * ca,
            )
            for x, y in pts
        ]
        p.polygon([M(*q) for q in inner], (46, 158, 58, 255))
        p.line(
            [M(cx, cy), M(cx + L * 0.92 * ca, cy + L * 0.92 * sa)],
            (150, 226, 110, 230),
            1.0 * s,
        )
        hl = [
            (cx + (L * u) * ca - (-W * 0.45) * sa, cy + (L * u) * sa + (-W * 0.45) * ca)
            for u in (0.25, 0.5, 0.7)
        ]
        p.line([M(*q) for q in hl], (176, 255, 140, 180), 0.9 * s)
    for _ in range(5):
        fx = tx + rng.uniform(-4, 4)
        fy = ty + rng.uniform(-4, 4)
        p.ellipse(
            (
                M(fx, fy)[0] - 1.8 * s,
                M(fx, fy)[1] - 1.8 * s,
                M(fx, fy)[0] + 1.8 * s,
                M(fx, fy)[1] + 1.8 * s,
            ),
            (255, 222, 64, 255),
        )


def char_siu_slice(p: Pen, M, cx, cy, angle, seed, s, L=25.0, W=15.0):
    """Thick honey-glazed char siu slab: lacquered red bark along the top,
    smoke-ring rimmed pink cut face, marbled fat seams and charred tips."""
    rng = random.Random(seed)
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)

    def T(u, v):
        return M(cx + u * ca - v * sa, cy + u * sa + v * ca)

    def slab(l, w, oy=0.0, arch=2.4, n=5.0, count=48):
        pts = []
        for i in range(count):
            t = math.tau * i / count
            c, si = math.cos(t), math.sin(t)
            u = l * math.copysign(abs(c) ** (2 / n), c)
            v = w * math.copysign(abs(si) ** (2 / n), si)
            if v < 0:
                v -= arch * (1 - (u / l) ** 2)
            pts.append(T(u, v + oy))
        return pts

    p.polygon(slab(L, W, 4.6), (40, 12, 6, 110))
    p.polygon(slab(L, W, 3.0), (92, 16, 18, 255))  # visible slab thickness
    p.polygon(slab(L, W), (124, 22, 24, 255))
    p.polygon(slab(L * 0.95, W * 0.9, -0.3), (182, 32, 38, 255))
    # Smoke ring around a juicy pink cut face.
    p.polygon(slab(L * 0.84, W * 0.74, 0.4, arch=1.4), (210, 66, 58, 255))
    p.polygon(slab(L * 0.74, W * 0.6, 0.6, arch=1.0), (238, 132, 108, 255))
    p.polygon(slab(L * 0.5, W * 0.3, 0.2, arch=0.4), (248, 164, 138, 255))
    for v0, col, wid in (
        (-W * 0.18, (255, 232, 214, 245), 1.8),
        (W * 0.34, (255, 216, 196, 225), 1.2),
    ):
        pts = []
        for i in range(13):
            u = -0.74 + 1.48 * i / 12
            pts.append(T(u * L, v0 + math.sin(u * 5 + seed) * 1.0))
        p.line(pts, col, wid * s)
    for _ in range(6):
        u = rng.uniform(-0.65, 0.65) * L
        v = rng.uniform(-W * 0.45, W * 0.5)
        p.line([T(u - 2.5, v), T(u + 2.5, v + 0.5)], (214, 96, 80, 210), 0.7 * s)
    # Lacquered glaze gloss along the bark.
    gloss = [
        T(u * L * 0.82, -W * 0.86 - 2.0 * (1 - u * u))
        for u in (-0.85, -0.45, 0.0, 0.4, 0.75)
    ]
    p.line(gloss, (255, 120, 96, 245), 2.2 * s)
    p.line(gloss[1:3], (255, 236, 214, 240), 1.0 * s)
    for _ in range(8):
        side = rng.choice((-1, 1))
        u = side * rng.uniform(0.66, 0.98) * L
        v = rng.uniform(-W * 0.85, W * 0.8)
        r = rng.uniform(1.0, 2.3)
        q = T(u, v)
        p.polygon(
            rotated_ellipse_points(
                q[0], q[1], r * s, r * 0.7 * s, rng.uniform(0, 180), 8
            ),
            (52, 10, 8, 235),
        )


def sunny_egg(p: Pen, M, cx, cy, s, seed):
    white_pts = blob_points(cx, cy, 36, 21, seed, 30)
    p.polygon([M(x, y + 2.5) for x, y in white_pts], (150, 120, 70, 110))
    lace = blob_points(cx, cy, 37.5, 22, seed + 3, 30)
    p.polygon([M(*q) for q in lace], (220, 160, 82, 255))
    p.polygon([M(*q) for q in white_pts], (255, 253, 244, 255))
    p.polygon(
        [M(x, y - 1) for x, y in blob_points(cx - 4, cy - 2, 28, 15, seed + 1, 24)],
        (255, 255, 252, 255),
    )
    p.line(
        [M(cx - 30, cy - 4), M(cx - 20, cy - 13), M(cx - 6, cy - 16)],
        (255, 255, 255, 255),
        1.4 * s,
    )
    yx, yy = cx + 5, cy - 3
    # Runny yolk spilling toward the rice.
    p.polygon(
        [
            M(yx + 8, yy + 4),
            M(yx + 20, yy + 10),
            M(yx + 26, yy + 18),
            M(yx + 21, yy + 21),
            M(yx + 12, yy + 14),
            M(yx + 4, yy + 8),
        ],
        (255, 176, 30, 255),
    )
    p.ellipse(
        (
            M(yx + 20, yy + 16)[0] - 3 * s,
            M(yx + 20, yy + 16)[1] - 3 * s,
            M(yx + 20, yy + 16)[0] + 3 * s,
            M(yx + 20, yy + 16)[1] + 3 * s,
        ),
        (255, 186, 40, 255),
    )
    p.ellipse(
        (
            M(yx - 14, yy - 11)[0],
            M(yx - 14, yy - 11)[1],
            M(yx + 14, yy + 11)[0],
            M(yx + 14, yy + 11)[1],
        ),
        (226, 118, 14, 255),
    )
    p.ellipse(
        (
            M(yx - 13, yy - 11)[0],
            M(yx - 13, yy - 11)[1],
            M(yx + 12, yy + 8)[0],
            M(yx + 12, yy + 8)[1],
        ),
        (255, 172, 28, 255),
    )
    p.ellipse(
        (
            M(yx - 9, yy - 9)[0],
            M(yx - 9, yy - 9)[1],
            M(yx + 5, yy + 1)[0],
            M(yx + 5, yy + 1)[1],
        ),
        (255, 214, 92, 255),
    )
    p.ellipse(
        (
            M(yx - 7, yy - 8)[0],
            M(yx - 7, yy - 8)[1],
            M(yx - 1, yy - 4)[0],
            M(yx - 1, yy - 4)[1],
        ),
        (255, 252, 226, 255),
    )


def rooster_motif(p: Pen, M, x, y, s):
    """Tiny Hong Kong 'rooster bowl' decoration."""
    p.line(
        [M(x - 6, y - 2), M(x - 18, y - 14), M(x - 20, y - 4)],
        (24, 70, 40, 255),
        2.2 * s,
    )
    p.line([M(x - 5, y), M(x - 15, y - 18)], (40, 120, 60, 255), 1.8 * s)
    p.line([M(x - 4, y + 1), M(x - 22, y - 9)], (20, 40, 30, 255), 1.6 * s)
    p.polygon([M(*q) for q in blob_points(x, y, 9, 6, 77, 16)], (214, 50, 38, 255))
    p.ellipse(
        (
            M(x + 5, y - 11)[0],
            M(x + 5, y - 11)[1],
            M(x + 12, y - 4)[0],
            M(x + 12, y - 4)[1],
        ),
        (214, 50, 38, 255),
    )
    p.polygon(
        [
            M(x + 6, y - 11),
            M(x + 8, y - 15),
            M(x + 10, y - 12),
            M(x + 12, y - 14),
            M(x + 12, y - 10),
        ],
        (240, 40, 40, 255),
    )
    p.polygon(
        [M(x + 12, y - 8), M(x + 16, y - 7), M(x + 12, y - 6)], (250, 200, 60, 255)
    )
    p.line([M(x - 1, y + 5), M(x - 2, y + 11)], (220, 150, 40, 255), 1.0 * s)
    p.line([M(x + 3, y + 5), M(x + 4, y + 11)], (220, 150, 40, 255), 1.0 * s)
    p.line([M(x - 4, y - 1), M(x + 4, y + 2)], (255, 160, 80, 220), 0.9 * s)


def draw_char_siu_rice(image, cx, cy, s):
    """A steaming 'Sorrowful Rice' bowl. Local units: rim radius 100."""
    p = Pen(image, HOLO_SCALE)

    def M(x, y):
        return (cx + x * s, cy + y * s)

    def E(x0, y0, x1, y1):
        return (cx + x0 * s, cy + y0 * s, cx + x1 * s, cy + y1 * s)

    def arc_pts(rx, ry, oy, t0, t1, n=40, ox=0.0):
        return [
            (
                ox + rx * math.cos(t0 + (t1 - t0) * i / n),
                oy + ry * math.sin(t0 + (t1 - t0) * i / n),
            )
            for i in range(n + 1)
        ]

    add_steam(
        image,
        (
            (cx - 46 * s, cy - 52 * s, 42 * s),
            (cx - 6 * s, cy - 60 * s, 50 * s),
            (cx + 38 * s, cy - 54 * s, 40 * s),
        ),
    )
    # Contact shadow, foot ring and the porcelain body.
    p.ellipse(E(-88, 70, 88, 96), (0, 40, 26, 95))
    p.polygon([M(-46, 64), M(46, 64), M(41, 88), M(-41, 88)], (190, 204, 198, 255))
    p.polygon([M(-46, 64), M(46, 64), M(44, 72), M(-44, 72)], (228, 234, 228, 255))
    p.line([M(-41, 86), M(41, 86)], (36, 86, 168, 255), 1.6 * s)
    body = arc_pts(100, 80, 0, 0, math.pi)
    p.polygon([M(*q) for q in body], (188, 204, 198, 255))
    p.polygon(
        [M(*q) for q in arc_pts(90, 74, 0, 0.03, math.pi, ox=-8)], (250, 251, 244, 255)
    )
    p.line(
        [M(*q) for q in arc_pts(100, 80, 0, 0.02, math.pi - 0.02)],
        (58, 98, 92, 255),
        1.4 * s,
    )
    # Cobalt bands and the rooster / banana-leaf decoration.
    p.line(
        [M(*q) for q in arc_pts(97, 30, 6, 0.06, math.pi - 0.06)],
        (38, 88, 172, 255),
        3.0 * s,
    )
    p.line(
        [M(*q) for q in arc_pts(70, 22, 44, 0.25, math.pi - 0.25)],
        (38, 88, 172, 230),
        1.2 * s,
    )
    rooster_motif(p, M, -30, 40, s)
    leaf = [(26, 52), (40, 30), (56, 22), (50, 40), (34, 54)]
    p.polygon([M(*q) for q in leaf], (54, 150, 66, 255))
    p.line([M(28, 52), M(52, 26)], (190, 240, 160, 230), 1.0 * s)
    p.ellipse(E(52, 40, 62, 50), (232, 84, 116, 255))
    p.ellipse(E(55, 43, 59, 47), (255, 210, 120, 255))
    p.line(
        [M(*q) for q in arc_pts(86, 66, 0, 2.3, 2.78, 12)],
        (255, 255, 255, 235),
        2.4 * s,
    )

    # Bowl mouth: interior wall and the back rim.
    p.ellipse(
        E(-100, -26, 100, 26),
        (234, 238, 232, 255),
        outline=(60, 100, 92, 255),
        width=1.2 * s,
    )
    p.ellipse(E(-93, -21, 93, 21), (196, 206, 200, 255))
    p.arc(E(-100, -26, 100, 26), 180, 360, (40, 90, 172, 255), 1.6 * s)

    # Rice dome with individually drawn grains.
    dome = arc_pts(93, 54, -2, math.pi, 2 * math.pi) + arc_pts(93, 20, 1, 0, math.pi)
    p.polygon([M(*q) for q in dome], (255, 246, 214, 255))
    rng = random.Random(5101)
    for i in range(150):
        ang = rng.uniform(math.pi, 2 * math.pi)
        rad = math.sqrt(rng.random()) * 0.95
        gx = math.cos(ang) * 90 * rad
        gy = -2 + math.sin(ang) * 52 * rad + rng.uniform(0, 14)
        colour = rng.choice(
            (
                (255, 255, 240, 255),
                (250, 240, 210, 255),
                (236, 222, 186, 255),
                (255, 252, 230, 255),
            )
        )
        q = M(gx, gy)
        grain = rotated_ellipse_points(
            q[0],
            q[1],
            rng.uniform(2.6, 4.0) * s,
            rng.uniform(1.1, 1.7) * s,
            rng.uniform(-60, 60),
            10,
        )
        p.polygon([(x + 0.5 * s, y + 0.7 * s) for x, y in grain], (206, 190, 150, 200))
        p.polygon(grain, colour)
    # Sweet soy glaze soaking softly into the rice around the meat.
    sauce = Image.new("RGBA", image.size, (0, 0, 0, 0))
    sp = Pen(sauce, HOLO_SCALE)
    for bx, by, rx, ry, sd in (
        (-40, 4, 44, 10, 5201),
        (-4, 12, 28, 6, 5202),
        (68, 10, 18, 5, 5203),
    ):
        sp.polygon(
            [M(*q) for q in blob_points(bx, by, rx, ry, sd, 22)], (150, 70, 22, 190)
        )
        sp.polygon(
            [
                M(*q)
                for q in blob_points(bx - 4, by - 2, rx * 0.6, ry * 0.45, sd + 7, 18)
            ],
            (212, 128, 46, 200),
        )
    image.alpha_composite(sauce.filter(ImageFilter.GaussianBlur(1.8 * HOLO_SCALE)))
    for dx, dy in ((-50, 12), (-20, 4), (6, 14), (70, 6)):
        q = M(dx, dy)
        p.ellipse(
            (q[0] - 2.4 * s, q[1] - 1.4 * s, q[0] + 2.4 * s, q[1] + 1.4 * s),
            (176, 88, 26, 230),
        )
        p.ellipse(
            (q[0] - 1.2 * s, q[1] - 1.0 * s, q[0] + 0.2 * s, q[1] - 0.2 * s),
            (255, 214, 150, 230),
        )

    # Greens behind, then shingled char siu (back to front), then the egg.
    choy_sum(p, M, (4, -16), (98, -60), -1, 5301, s)
    choy_sum(p, M, (16, -8), (106, -30), 1, 5302, s)
    for i, (sx, sy, ang) in enumerate(
        ((14, -36, 14), (-6, -32, 4), (-26, -26, -6), (-46, -18, -14), (-62, -8, -22))
    ):
        q = M(sx + 1, sy + 13)
        p.ellipse(
            (q[0] - 26 * s, q[1] - 6 * s, q[0] + 26 * s, q[1] + 6 * s),
            (120, 64, 20, 120),
        )
        char_siu_slice(p, M, sx, sy, ang, 5400 + i, s)
    sunny_egg(p, M, 44, -4, s, 5501)
    # Purple onion rings and scallion confetti.
    orng = random.Random(5601)
    for ox, oy in ((-70, 0), (-16, -6), (16, -42), (70, 12), (-44, -40), (60, -30)):
        rx = orng.uniform(5, 7)
        p.arc(
            E(ox - rx, oy - rx * 0.55, ox + rx, oy + rx * 0.55),
            orng.uniform(0, 90),
            orng.uniform(250, 340),
            (150, 56, 146, 255),
            1.6 * s,
        )
        p.arc(
            E(ox - rx + 1.5, oy - rx * 0.55 + 1, ox + rx - 1.5, oy + rx * 0.55 - 1),
            200,
            330,
            (226, 170, 226, 230),
            0.8 * s,
        )
    for _ in range(16):
        gx, gy = orng.uniform(-80, 70), orng.uniform(-44, 12)
        q = M(gx, gy)
        p.polygon(
            rotated_ellipse_points(
                q[0], q[1], 2.4 * s, 1.5 * s, orng.uniform(0, 180), 8
            ),
            orng.choice(((60, 180, 60, 255), (120, 222, 84, 255), (30, 130, 50, 255))),
        )
    # Glossy sauce drizzle over the meat and the front rim on top of the rice.
    front_rim = arc_pts(100, 26, 0, 0, math.pi) + arc_pts(93, 20, 1, math.pi, 0)
    p.polygon([M(*q) for q in front_rim], (252, 253, 248, 255))
    p.line(
        [M(*q) for q in arc_pts(100, 26, 0, 0.02, math.pi - 0.02)],
        (40, 90, 172, 255),
        1.6 * s,
    )
    p.arc(E(-96, -23, 96, 23), 28, 70, (255, 255, 255, 255), 1.6 * s)


# ------------------------------------------------------------ wall: panels
# Every wall projection is anchored to the emitter slot of the matching
# WallHoloSignboardBase texture under the XML offsets declared above.
WALL_PANEL = (282, 96, 742, 640)
WALL_FRONT_EMIT = (412, 612, 672)  # x0, x1, y of the base slot in holo px
WALL_BACK_EMIT = (412, 612, 552)
WALL_SIDE_EMIT_X = 473  # east variant; west mirrors around x = 512
WALL_SIDE_EMIT_Y = (556, 736)


def wall_holo_xy(rot, wx, wz):
    ox, oz = WALL_HOLO_OFFSETS[rot]
    k = HOLO_SIZE[0] / WALL_HOLO_DRAW
    return 512 + (wx - ox) * k, 512 - (wz - oz) * k


def wall_base_world(rot, px, py):
    ox, oz = WALL_BASE_OFFSETS[rot]
    k = WALL_BASE_SIZE[0] / WALL_BASE_DRAW
    return ox + (px - 128) / k, oz + (128 - py) / k


def wall_panel_polygon():
    x0, y0, x1, y1 = WALL_PANEL
    c = 14
    return [
        (x0 + c, y0),
        (x1 - c, y0),
        (x1, y0 + c),
        (x1, y1 - c),
        (x1 - c, y1),
        (x0 + c, y1),
        (x0, y1 - c),
        (x0, y0 + c),
    ]


def draw_wall_panel_ss():
    """Front-facing wall menu on a supersampled canvas (no beam)."""
    image = new_canvas(HOLO_SIZE, HOLO_SCALE)
    x0, y0, x1, y1 = WALL_PANEL
    panel = wall_panel_polygon()
    mask = polygon_mask(image.size, panel, HOLO_SCALE)
    holo_surface(image, mask, WALL_PANEL)
    p = Pen(image, HOLO_SCALE)
    p.line(panel + panel[:1], (170, 255, 104, 220), 2.6)
    inner = [
        (x0 + 18, y0 + 8),
        (x1 - 18, y0 + 8),
        (x1 - 8, y0 + 18),
        (x1 - 8, y1 - 18),
        (x1 - 18, y1 - 8),
        (x0 + 18, y1 - 8),
        (x0 + 8, y1 - 18),
        (x0 + 8, y0 + 18),
    ]
    p.line(inner + inner[:1], (222, 255, 164, 100), 1.0)
    for x, y in (
        (x0 + 3, y0 + 3),
        (x1 - 3, y0 + 3),
        (x1 - 3, y1 - 3),
        (x0 + 3, y1 - 3),
    ):
        p.line([(x - 5, y), (x + 5, y)], (223, 255, 168, 190), 1.0)
        p.line([(x, y - 5), (x, y + 5)], (223, 255, 168, 190), 1.0)
    for y in range(170, 600, 36):
        p.line([(x0 - 7, y), (x0 - 2, y)], (121, 255, 72, 105), 1.0)
        p.line([(x1 + 2, y), (x1 + 7, y)], (121, 255, 72, 105), 1.0)

    fancy_text(image, "茶餐厅", (512, 150), 78)
    p.rounded(
        (352, 196, 672, 222),
        10,
        (18, 104, 48, 132),
        outline=(220, 255, 155, 120),
        width=0.8,
    )
    p.text((512, 209), "主厨首推  ·  黯然销魂", FONT_YAHEI, 16, (255, 245, 188, 255))
    p.text(
        (512, 236),
        "INTERSTELLAR CHA CHAAN TENG  //  SIGNATURE",
        FONT_LATIN,
        8.5,
        (85, 38, 40, 235),
    )

    # Showcase card with a warm sunburst behind the bowl.
    card = (300, 248, 724, 476)
    p.blend = False
    p.rounded(card, 10, (3, 65, 39, 128), outline=(195, 255, 128, 205), width=1.5)
    p.blend = True
    rays = new_canvas(HOLO_SIZE, HOLO_SCALE)
    rp = Pen(rays, HOLO_SCALE)
    for i in range(18):
        a0 = math.pi + math.pi * i / 18
        a1 = a0 + math.pi / 36
        rp.polygon(
            [
                (512, 404),
                (512 + 260 * math.cos(a0), 404 + 200 * math.sin(a0)),
                (512 + 260 * math.cos(a1), 404 + 200 * math.sin(a1)),
            ],
            (255, 196, 84, 30),
        )
    rp.ellipse((392, 312, 632, 432), (255, 150, 60, 34))
    rays = rays.filter(ImageFilter.GaussianBlur(2 * HOLO_SCALE))
    card_mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(card_mask).rounded_rectangle(
        tuple(round(v * HOLO_SCALE) for v in card), radius=10 * HOLO_SCALE, fill=255
    )
    clipped_overlay(image, rays, card_mask)
    p.line(
        [(card[0], card[1] + 22), (card[0], card[1] + 8), (card[0] + 14, card[1] + 8)],
        MINT,
        2.0,
    )
    p.line(
        [(card[2] - 14, card[3] - 8), (card[2], card[3] - 8), (card[2], card[3] - 22)],
        MINT,
        2.0,
    )
    p.rectangle((301, 262, 304, 462), (255, 100, 52, 210))
    # "No.1" badge.
    p.ellipse(
        (314, 260, 362, 308), (230, 62, 45, 235), outline=(255, 211, 91, 255), width=1.6
    )
    p.text((338, 278), "No.1", FONT_LATIN, 14, (255, 246, 207, 255))
    p.text((338, 294), "招牌", FONT_YAHEI, 10, (255, 230, 150, 255))
    p.text((710, 266), "HOT", FONT_LATIN, 10, (255, 213, 114, 235), anchor="rm")

    draw_char_siu_rice(image, 512, 362, 1.22)

    fancy_text(
        image,
        "黯然销魂饭",
        (512, 507),
        42,
        top_colour=(255, 240, 160, 255),
        bottom_colour=(255, 168, 58, 255),
        rim=(236, 54, 42),
        dark_rim=(96, 18, 30),
        shade=(80, 14, 30),
        glow=(255, 80, 30),
        glow_alpha=0.55,
    )
    p = Pen(image, HOLO_SCALE)
    p.text(
        (512, 541), "CHAR SIU  &  SUNNY EGG RICE", FONT_LATIN, 11, (214, 255, 178, 240)
    )
    p.line([(318, 556), (706, 556)], (117, 255, 80, 110), 0.9)
    p.rounded(
        (312, 564, 470, 606),
        8,
        (3, 65, 39, 130),
        outline=(195, 255, 128, 180),
        width=1.0,
    )
    p.text((372, 585), "$58", FONT_LATIN, 30, (255, 229, 111, 255))
    p.text((446, 579), "PER", FONT_LATIN, 8, (190, 255, 160, 220))
    p.text((446, 591), "BOWL", FONT_LATIN, 8, (190, 255, 160, 220))
    p.rounded(
        (540, 564, 712, 606),
        8,
        (230, 62, 45, 238),
        outline=(255, 195, 107, 255),
        width=1.2,
    )
    p.rounded((546, 568, 706, 576), 4, (246, 112, 82, 240))
    p.text((626, 585), "点单 +", FONT_YAHEI, 20, (255, 250, 213, 255))
    p.ellipse((304, 619, 312, 627), (220, 255, 141, 255))
    p.text(
        (318, 623),
        "ICCT  //  SORROWFUL RICE SPECIAL",
        FONT_LATIN,
        8.5,
        (65, 55, 35, 230),
        anchor="lm",
    )
    p.text((718, 623), "ONLINE", FONT_LATIN, 8.5, (101, 29, 38, 240), anchor="rm")
    return image


def draw_wall_hologram_north(panel_ss):
    """Rot North: mounted on a north wall, full front view rising off the
    emitter on the wall face."""
    image = new_canvas(HOLO_SIZE, HOLO_SCALE)
    ex0, ex1, ey = WALL_FRONT_EMIT
    x0, _, x1, y1 = WALL_PANEL
    skirt = [(x0 + 12, y1 - 8), (x1 - 12, y1 - 8), (ex1, ey + 1), (ex0, ey + 1)]
    projection_skirt(image, skirt, ey, ex0, ex1, feather=20)
    image.alpha_composite(panel_ss)
    return clip_alpha(finish(image, HOLO_SIZE), (236, 52, 788, 700))


def draw_wall_hologram_south(panel_ss):
    """Rot South: mounted on a south wall facing north; the viewer sees the
    mirrored back of a flatter, dimmer projection with strong backlight."""
    image = new_canvas(HOLO_SIZE, HOLO_SCALE)
    ex0, ex1, ey = WALL_BACK_EMIT
    x0, y0, x1, y1 = WALL_PANEL
    dst = [(306, 214), (718, 214), (730, 534), (294, 534)]
    back = perspective_warp(
        panel_ss.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
        [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
        dst,
        HOLO_SCALE,
    )
    back.putalpha(alpha_scaled(back.getchannel("A"), 0.64))
    # Backlight: green bloom behind the sheet plus a sunset glow behind the title.
    quad_mask = polygon_mask(image.size, dst, HOLO_SCALE).filter(
        ImageFilter.GaussianBlur(16 * HOLO_SCALE)
    )
    image.alpha_composite(
        colour_layer(image.size, (70, 255, 30), alpha_scaled(quad_mask, 0.42))
    )
    warm = Image.new("L", image.size, 0)
    ImageDraw.Draw(warm).ellipse(
        tuple(round(v * HOLO_SCALE) for v in (370, 222, 654, 300)), fill=255
    )
    warm = warm.filter(ImageFilter.GaussianBlur(14 * HOLO_SCALE))
    image.alpha_composite(
        colour_layer(image.size, (255, 86, 40), alpha_scaled(warm, 0.50))
    )
    image.alpha_composite(back)
    beam = new_canvas(HOLO_SIZE, HOLO_SCALE)
    projection_skirt(
        beam,
        [(306, 528), (718, 528), (ex1, ey + 1), (ex0, ey + 1)],
        ey,
        ex0,
        ex1,
        feather=18,
    )
    image.alpha_composite(beam)
    return clip_alpha(finish(image, HOLO_SIZE), (236, 150, 788, 600))


def side_quads(mirror):
    """Panel quad for the side views (TL, TR, BR, BL in screen space)."""
    near_x, far_x = 466, 198
    quad = {
        "near_top": (near_x, 296),
        "near_bottom": (near_x, 716),
        "far_top": (far_x, 340),
        "far_bottom": (far_x, 712),
    }
    if mirror:
        quad = {k: (1024 - x, y) for k, (x, y) in quad.items()}
        return [
            quad["near_top"],
            quad["far_top"],
            quad["far_bottom"],
            quad["near_bottom"],
        ]
    return [quad["far_top"], quad["near_top"], quad["near_bottom"], quad["far_bottom"]]


def draw_wall_hologram_side(panel_ss, mirror):
    """Rot East (mirror=False): wall to the east, sign swings out westward at
    roughly 30 degrees; Rot West mirrors the geometry but keeps text readable."""
    image = new_canvas(HOLO_SIZE, HOLO_SCALE)
    x0, y0, x1, y1 = WALL_PANEL
    dst = side_quads(mirror)
    side = perspective_warp(
        panel_ss, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], dst, HOLO_SCALE
    )
    side.putalpha(alpha_scaled(side.getchannel("A"), 0.92))

    def X(x):
        return 1024 - x if mirror else x

    ex = X(WALL_SIDE_EMIT_X)
    ey0, ey1 = WALL_SIDE_EMIT_Y
    # Light fan leaving the wall strip, fading away from the wall.
    fan = [(ex, ey0 - 4), (ex, ey1 + 4), (X(300), 708), (X(300), 360)]
    fan_mask = polygon_mask(image.size, fan, HOLO_SCALE)
    xs = sorted((ex, X(300)))
    ramp = ramp_alpha(
        image.size,
        (xs[0] * HOLO_SCALE, 0, xs[1] * HOLO_SCALE, image.height),
        *((0, 150) if not mirror else (150, 0)),
        horizontal=True,
    )
    image.alpha_composite(
        colour_layer(image.size, (110, 255, 50), ImageChops.multiply(ramp, fan_mask))
    )
    halo = polygon_mask(image.size, dst, HOLO_SCALE).filter(
        ImageFilter.GaussianBlur(12 * HOLO_SCALE)
    )
    image.alpha_composite(
        colour_layer(image.size, (76, 255, 22), alpha_scaled(halo, 0.30))
    )
    image.alpha_composite(side)
    p = Pen(image, HOLO_SCALE)
    near = [q for q in dst if abs(q[0] - X(466)) < 1]
    p.line(near, (226, 255, 186, 235), 2.4)
    for i in range(9):
        t = i / 8
        y = ey0 + (ey1 - ey0) * t
        ty = near[0][1] + (near[1][1] - near[0][1]) * (0.35 + 0.6 * t)
        p.line([(ex, y), (X(466), ty)], (226, 255, 190, 70), 0.9)
    glow = Image.new("L", image.size, 0)
    ImageDraw.Draw(glow).rounded_rectangle(
        tuple(round(v * HOLO_SCALE) for v in (ex - 8, ey0 - 6, ex + 8, ey1 + 6)),
        radius=6 * HOLO_SCALE,
        fill=255,
    )
    glow = glow.filter(ImageFilter.GaussianBlur(6 * HOLO_SCALE))
    image.alpha_composite(
        colour_layer(image.size, (96, 255, 40), alpha_scaled(glow, 0.85))
    )
    p.line([(ex, ey0), (ex, ey1)], (210, 255, 160, 240), 4.0)
    p.line([(ex, ey0 + 6), (ex, ey1 - 6)], (250, 255, 235, 255), 1.6)
    bounds = (150, 236, 530, 770)
    if mirror:
        bounds = (1024 - bounds[2], bounds[1], 1024 - bounds[0], bounds[3])
    return clip_alpha(finish(image, HOLO_SIZE), bounds)


# ------------------------------------------------------ wall: top-down maps
# One physical screen, projected once onto the XZ plane. All four directional
# PNGs bake the SAME rigid rotation; Graphic_Multi selects, it does not rotate
# four independently supplied materials. Never typeset the east/west separately.
def cardinal_images(north):
    return {
        "north": north,
        "east": north.transpose(Image.Transpose.ROTATE_270),
        "south": north.transpose(Image.Transpose.ROTATE_180),
        "west": north.transpose(Image.Transpose.ROTATE_90),
    }


def draw_wall_map_north(panel_ss):
    """Full menu foreshortened to 0.16 cells, plus a 0.06-cell emitter fan.

    The supporting north wall is at z=1. The slot is at z=0.8414;
    the screen runs z=0.78..0.62, toward the room (negative z).
    Rotation about the canvas centre also rotates its XML offset about the
    building centre: R(x,z)=(z,-x), i.e. clockwise in PNG coordinates.
    """
    image = new_canvas(HOLO_SIZE, HOLO_SCALE)
    slot = wall_base_world("north", 128, 143)[1]
    points = [(-0.258, slot), (0.258, slot), (0.50, 0.78), (-0.50, 0.78)]
    polygon = [wall_holo_xy("north", x, z) for x, z in points]
    mask = polygon_mask(image.size, polygon, HOLO_SCALE)
    image.alpha_composite(colour_layer(image.size, (92, 255, 42), alpha_scaled(mask, 0.28)))
    p = Pen(image, HOLO_SCALE)
    for i in range(13):
        t = i / 12
        p.line([wall_holo_xy("north", -0.258 + 0.516*t, slot),
                wall_holo_xy("north", -0.50 + t, 0.78)],
               (200, 255, 150, 100 if i % 3 == 0 else 48), 0.65)
    p.line(polygon[:2], (235, 255, 202, 240), 1.8)
    # Preserve the actual frontal artwork, not a new upright top-view menu.
    x0, y0 = wall_holo_xy("north", -0.50, 0.78)
    x1, y1 = wall_holo_xy("north", 0.50, 0.62)
    panel = panel_ss.crop(tuple(round(v * HOLO_SCALE) for v in WALL_PANEL))
    panel = panel.resize((round((x1-x0)*HOLO_SCALE), round((y1-y0)*HOLO_SCALE)), RESAMPLE)
    image.alpha_composite(panel, (round(x0*HOLO_SCALE), round(y0*HOLO_SCALE)))
    # Soft local bloom, not a huge opaque green trapezoid hiding the metal base.
    halo = image.getchannel("A").filter(ImageFilter.GaussianBlur(1.5 * HOLO_SCALE))
    glow = colour_layer(image.size, (80, 255, 30), alpha_scaled(halo, 0.22))
    glow.alpha_composite(image)
    return finish(glow, HOLO_SIZE)


# -------------------------------------------------------------- wall: bases
def wall_plaque(p: Pen, box, vertical=False):
    x0, y0, x1, y1 = box
    p.rounded(box, 3, (96, 96, 96, 255))
    p.rounded(
        (x0 + 2, y0 + 2, x1 - 2, y1 - 2),
        2,
        (24, 51, 35, 255),
        outline=(211, 171, 72, 255),
        width=1.0,
    )
    if vertical:
        p.rectangle((x0 + 4, y0 + 4, x0 + 6, y1 - 4), (209, 55, 42, 255))
        cx = (x0 + x1) / 2 + 1.5
        step = (y1 - y0 - 12) / 4
        for i, letter in enumerate("ICCT"):
            p.text(
                (cx, y0 + 8 + step * (i + 0.5)),
                letter,
                FONT_LATIN,
                11,
                (255, 241, 192, 255),
            )
    else:
        p.rectangle((x0 + 4, y0 + 4, x1 - 4, y0 + 6.5), (209, 55, 42, 255))
        cx = (x0 + x1) / 2
        p.text(
            (cx, y0 + (y1 - y0) * 0.47), "ICCT", FONT_LATIN, 14, (255, 241, 192, 255)
        )
        p.text(
            (cx, y0 + (y1 - y0) * 0.80), "茶餐厅", FONT_YAHEI, 7, (147, 255, 132, 255)
        )


def draw_wall_base_north():
    """Rot North: emitter on the lower south face of a north wall (cf. vanilla
    WallLamp_north). The slot on its top lip feeds the upward projection."""
    image = new_canvas(WALL_BASE_SIZE, BASE_SCALE)
    p = Pen(image, BASE_SCALE)
    p.rounded((20, 148, 40, 198), 5, BLACK)
    p.rounded((216, 148, 236, 198), 5, BLACK)
    p.rounded((30, 124, 226, 220), 11, BLACK)
    p.rectangle((24, 156, 34, 190), (120, 120, 120, 255))
    p.rectangle((222, 156, 232, 190), (90, 90, 90, 255))
    p.polygon([(46, 130), (210, 130), (220, 150), (36, 150)], (246, 246, 246, 255))
    p.polygon([(52, 134), (204, 134), (213, 148), (43, 148)], (134, 134, 134, 255))
    p.rectangle((58, 136, 198, 147), (40, 40, 40, 255))
    p.rectangle((60, 137, 196, 140), (82, 82, 82, 255))
    p.rectangle((62, 141, 194, 145), (70, 196, 76, 255))
    p.line([(64, 143), (192, 143)], (205, 255, 165, 255), 0.9)
    p.rectangle((36, 150, 220, 206), (191, 191, 191, 255))
    p.line([(38, 152), (218, 152)], (228, 228, 228, 255), 1.0)
    p.line([(38, 204), (218, 204)], (150, 150, 150, 255), 1.0)
    p.line([(39, 154), (39, 202)], (205, 205, 205, 255), 1.0)
    p.line([(217, 154), (217, 202)], (160, 160, 160, 255), 1.0)
    p.polygon([(36, 206), (220, 206), (213, 215), (43, 215)], (96, 96, 96, 255))
    p.line([(46, 213), (210, 213)], (60, 60, 60, 255), 1.2)
    wall_plaque(p, (93, 157, 163, 200))
    for x in (52, 204):
        p.ellipse((x - 3, 175, x + 3, 181), (120, 120, 120, 255))
        p.line([(x - 2, 178), (x + 2, 178)], (70, 70, 70, 255), 0.8)
    p.ellipse((66, 188, 72, 194), (255, 82, 47, 255))
    p.ellipse((184, 188, 190, 194), (106, 255, 48, 255))
    p.rectangle((76, 190, 86, 192), (153, 153, 153, 255))
    p.rectangle((170, 190, 180, 192), (153, 153, 153, 255))
    return finish(image, WALL_BASE_SIZE)


def draw_wall_base_south():
    """Rot South: bracket on the top edge of a south wall, seen from above;
    its emitter slot runs along the north (room) side."""
    image = new_canvas(WALL_BASE_SIZE, BASE_SCALE)
    p = Pen(image, BASE_SCALE)
    p.rounded((20, 6, 40, 40), 5, BLACK)
    p.rounded((216, 6, 236, 40), 5, BLACK)
    p.rounded((30, 0, 226, 50), 10, BLACK)
    p.rectangle((24, 12, 34, 34), (110, 110, 110, 255))
    p.rectangle((222, 12, 232, 34), (90, 90, 90, 255))
    p.rounded((36, 4, 220, 44), 7, (214, 214, 214, 255))
    p.rectangle((56, 7, 200, 19), (40, 40, 40, 255))
    p.rectangle((58, 10, 198, 15), (70, 196, 76, 255))
    p.line([(60, 12.5), (196, 12.5)], (205, 255, 165, 255), 0.9)
    p.rectangle((40, 21, 216, 33), (246, 246, 246, 255))
    p.line([(42, 22), (214, 22)], (255, 255, 255, 255), 1.0)
    p.rectangle((40, 34, 216, 43), (134, 134, 134, 255))
    p.line([(42, 42), (214, 42)], (82, 82, 82, 255), 1.0)
    p.rounded(
        (104, 23, 152, 32), 2, (24, 51, 35, 255), outline=(211, 171, 72, 255), width=0.8
    )
    p.text((128, 27.5), "ICCT", FONT_LATIN, 7.5, (255, 241, 192, 255))
    for x in (50, 206):
        p.ellipse((x - 3, 24, x + 3, 30), (150, 150, 150, 255))
    p.ellipse((70, 36, 75, 41), (106, 255, 48, 255))
    p.ellipse((181, 36, 186, 41), (255, 82, 47, 255))
    return finish(image, WALL_BASE_SIZE)


def draw_wall_base_side(mirror):
    """Rot East (mirror=False): vertical emitter on the west face of an east
    wall, slot facing the room on the left. Rot West mirrors the geometry."""
    image = new_canvas(WALL_BASE_SIZE, BASE_SCALE)
    p = Pen(image, BASE_SCALE)

    def B(x0, y0, x1, y1):
        if mirror:
            return (256 - x1, y0, 256 - x0, y1)
        return (x0, y0, x1, y1)

    def X(x):
        return 256 - x if mirror else x

    p.rounded(B(14, 8, 44, 26), 5, BLACK)
    p.rounded(B(14, 174, 44, 192), 5, BLACK)
    p.rounded(B(0, 18, 56, 182), 10, BLACK)
    p.rectangle(B(20, 11, 38, 20), (120, 120, 120, 255))
    p.rectangle(B(20, 180, 38, 189), (90, 90, 90, 255))
    p.rounded(B(4, 22, 52, 178), 7, (191, 191, 191, 255))
    p.polygon([(X(6), 36), (X(10), 24), (X(48), 24), (X(52), 36)], (246, 246, 246, 255))
    p.rectangle(B(6, 38, 20, 164), (40, 40, 40, 255))
    p.rectangle(B(7, 40, 10, 162), (82, 82, 82, 255))
    p.rectangle(B(11, 42, 16, 160), (70, 196, 76, 255))
    p.line([(X(13), 44), (X(13), 158)], (205, 255, 165, 255), 0.9)
    p.line([(X(22), 38), (X(22), 162)], (228, 228, 228, 255), 1.0)
    p.line([(X(49), 38), (X(49), 162)], (150, 150, 150, 255), 1.0)
    p.polygon(
        [(X(6), 164), (X(52), 164), (X(48), 177), (X(10), 177)], (120, 120, 120, 255)
    )
    p.line([(X(10), 175), (X(48), 175)], (70, 70, 70, 255), 1.0)
    wall_plaque(p, B(25, 66, 46, 136), vertical=True)
    for y in (48, 152):
        p.ellipse(B(32, y - 3, 38, y + 3), (120, 120, 120, 255))
    p.ellipse(B(32, 142, 37, 147), (106, 255, 48, 255))
    p.ellipse(B(32, 54, 37, 59), (255, 82, 47, 255))
    return finish(image, WALL_BASE_SIZE)


# ---------------------------------------------------------------------- UI
def make_ui(hologram, base):
    """True-proportion composite of the standing sign (beam seated in slot)."""
    half = 1.36
    return world_composite(
        [
            (base, (0.0, 0.0), STAND_BASE_DRAW),
            (hologram, (0.0, STAND_HOLO_OFFSET), (STAND_HOLO_DRAW, STAND_HOLO_DRAW)),
        ],
        HOLO_SIZE[0] / (2 * half),
        (-half, half),
        (-0.58, 2 * half - 0.58),
    )


def make_wall_ui(hologram, base):
    half = 0.96
    ox, oz = WALL_BASE_OFFSETS["north"]
    hx, hz = WALL_UI_HOLO_OFFSET
    z0 = 0.48
    return world_composite(
        [
            (base, (ox, oz), (WALL_BASE_DRAW, WALL_BASE_DRAW)),
            (hologram, (hx, hz), (WALL_HOLO_DRAW, WALL_HOLO_DRAW)),
        ],
        HOLO_SIZE[0] / (2 * half),
        (-half, half),
        (z0, z0 + 2 * half),
    )


# --------------------------------------------------------------- validation
def texture_stats(image):
    alpha = image.getchannel("A")
    hist = alpha.histogram()
    levels = [i for i, count in enumerate(hist) if count]
    return {
        "size": list(image.size),
        "mode": image.mode,
        "bbox_alpha_gt0": list(alpha.getbbox()) if alpha.getbbox() else None,
        "bbox_alpha_ge32": list(alpha.point(lambda a: 255 if a >= 32 else 0).getbbox())
        if any(hist[32:])
        else None,
        "alpha_min": min(levels),
        "alpha_max": max(levels),
        "alpha_levels": len(levels),
        "transparent_pixels": hist[0],
        "semitransparent_pixels": sum(hist[1:255]),
        "opaque_pixels": hist[255],
        "coverage_percent": round(
            sum(i * n for i, n in enumerate(hist))
            / (255 * image.width * image.height)
            * 100,
            3,
        ),
    }


def checker(size, cell=20, light=False):
    w, h = size
    tile = Image.new("RGBA", size, (0, 0, 0, 255))
    d = ImageDraw.Draw(tile)
    c0 = (50, 57, 53, 255) if not light else (223, 229, 218, 255)
    c1 = (59, 68, 62, 255) if not light else (237, 242, 232, 255)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            d.rectangle(
                (x, y, min(x + cell, w) - 1, min(y + cell, h) - 1),
                fill=c0 if (x // cell + y // cell) % 2 else c1,
            )
    return tile


def checker_thumbnail(image, bounds, cell=20, light=False):
    w, h = bounds
    tile = checker(bounds, cell, light)
    fitted = image.copy()
    fitted.thumbnail((w - 30, h - 34), RESAMPLE)
    tile.alpha_composite(
        fitted, ((w - fitted.width) // 2, (h - fitted.height) // 2 + 5)
    )
    return tile


def floor_canvas(ppu, x_range, z_range):
    """Dark RimWorld-ish floor tiles with a one-cell grid for scale."""
    width = round((x_range[1] - x_range[0]) * ppu)
    height = round((z_range[1] - z_range[0]) * ppu)
    out = Image.new("RGBA", (width, height), (54, 50, 44, 255))
    d = ImageDraw.Draw(out)
    gx = math.floor(x_range[0] - 0.5) + 0.5
    while gx <= x_range[1]:
        x = (gx - x_range[0]) * ppu
        d.line([(x, 0), (x, height)], (70, 66, 58, 255), 1)
        gx += 1
    gz = math.floor(z_range[0] - 0.5) + 0.5
    while gz <= z_range[1]:
        y = (z_range[1] - gz) * ppu
        d.line([(0, y), (width, y)], (70, 66, 58, 255), 1)
        gz += 1
    return out


def draw_wall_cell(out, ppu, x_range, z_range, cell):
    cx, cz = cell
    x0 = (cx - 0.5 - x_range[0]) * ppu
    y0 = (z_range[1] - (cz + 0.5)) * ppu
    d = ImageDraw.Draw(out)
    d.rectangle(
        (x0, y0, x0 + ppu, y0 + ppu),
        fill=(118, 112, 104, 255),
        outline=(30, 28, 26, 255),
        width=3,
    )
    d.rectangle(
        (x0 + 6, y0 + 6, x0 + ppu - 6, y0 + ppu * 0.55), fill=(140, 134, 124, 255)
    )


def make_standing_verification(base, hologram):
    """World-scale composite: base at (0,0) 2.4x1.6, hologram at (0,0.73) 3.8."""
    ppu = 300
    xr, zr = (-1.6, 1.6), (-1.0, 2.35)
    out = floor_canvas(ppu, xr, zr)
    out.alpha_composite(
        world_composite(
            [
                (base, (0.0, 0.0), STAND_BASE_DRAW),
                (
                    hologram,
                    (0.0, STAND_HOLO_OFFSET),
                    (STAND_HOLO_DRAW, STAND_HOLO_DRAW),
                ),
            ],
            ppu,
            xr,
            zr,
        )
    )
    zoom_box = (
        round((-0.85 - xr[0]) * ppu),
        round((zr[1] - 0.32) * ppu),
        round((0.85 - xr[0]) * ppu),
        round((zr[1] + 0.32) * ppu),
    )
    zoom = out.crop(zoom_box)
    zoom = zoom.resize((zoom.width * 2, zoom.height * 2), Image.Resampling.LANCZOS)
    # Also show the slot without the hologram for a direct comparison.
    bare = floor_canvas(ppu, xr, zr)
    bare.alpha_composite(
        world_composite([(base, (0.0, 0.0), STAND_BASE_DRAW)], ppu, xr, zr)
    )
    bare_zoom = bare.crop(zoom_box).resize(
        (zoom.width, zoom.height), Image.Resampling.LANCZOS
    )
    sheet = Image.new(
        "RGBA",
        (out.width + zoom.width + 40, max(out.height, zoom.height * 2 + 70)),
        (26, 34, 30, 255),
    )
    sheet.alpha_composite(out, (0, 0))
    d = ImageDraw.Draw(sheet)
    font = get_font(str(FONT_LATIN), 20)
    d.text(
        (out.width + 20, 8),
        "BASE ONLY (slot rows 174-211)",
        font=font,
        fill=(255, 213, 114, 255),
    )
    sheet.alpha_composite(bare_zoom, (out.width + 20, 34))
    d.text(
        (out.width + 20, zoom.height + 44),
        "BASE + HOLOGRAM @ (0,0,0.73)",
        font=font,
        fill=(255, 213, 114, 255),
    )
    sheet.alpha_composite(zoom, (out.width + 20, zoom.height + 70))
    sheet.convert("RGB").save(VERIFY_STANDING, optimize=True)


def wall_world_view(rot, base, hologram, ppu=220):
    xr, zr = (-1.6, 1.6), (-1.9, 2.5)
    out = floor_canvas(ppu, xr, zr)
    draw_wall_cell(out, ppu, xr, zr, WALL_CELL[rot])
    # Mark the cell the sign occupies.
    d = ImageDraw.Draw(out)
    x0 = (-0.5 - xr[0]) * ppu
    y0 = (zr[1] - 0.5) * ppu
    d.rectangle((x0, y0, x0 + ppu, y0 + ppu), outline=(255, 213, 114, 160), width=2)
    out.alpha_composite(
        world_composite(
            [
                (base, WALL_BASE_OFFSETS[rot], (WALL_BASE_DRAW, WALL_BASE_DRAW)),
                (hologram, WALL_HOLO_OFFSETS[rot], (WALL_HOLO_DRAW, WALL_HOLO_DRAW)),
            ],
            ppu,
            xr,
            zr,
        )
    )
    return out


def make_wall_preview(wall_images):
    views = []
    for rot in ("north", "south", "east", "west"):
        views.append(
            (
                rot,
                wall_world_view(
                    rot,
                    wall_images[f"WallHoloSignboardBase_{rot}.png"],
                    wall_images[f"WallHoloSignboardHologram_{rot}.png"],
                ),
            )
        )
    vw, vh = views[0][1].size
    raw_h = 300
    width = 4 * vw + 5 * 20
    height = 70 + vh + 50 + raw_h + 40
    out = Image.new("RGBA", (width, height), (26, 34, 30, 255))
    d = ImageDraw.Draw(out)
    title_font = get_font(str(FONT_LATIN), 30)
    label_font = get_font(str(FONT_LATIN), 18)
    d.text(
        (20, 18),
        "ICCT  /  WALL HOLO SIGNBOARD  —  TOP-DOWN NARROW RIBBONS (base 1x1 + hologram 2.6 @ XML offsets)",
        font=title_font,
        fill=(222, 255, 181, 255),
    )
    labels = {
        "north": "ROT NORTH  · wall north · 1.00 x 0.22-cell ribbon / 0 deg",
        "south": "ROT SOUTH  · wall south · 1.00 x 0.22-cell ribbon / 180 deg",
        "east": "ROT EAST  · wall east · 1.00 x 0.22-cell ribbon / rigid rotation",
        "west": "ROT WEST  · wall west · 1.00 x 0.22-cell ribbon / rigid rotation",
    }
    for i, (rot, view) in enumerate(views):
        x = 20 + i * (vw + 20)
        d.text((x, 62), labels[rot], font=label_font, fill=(255, 213, 114, 255))
        out.alpha_composite(view, (x, 88))
        y = 88 + vh + 30
        base_thumb = checker_thumbnail(
            wall_images[f"WallHoloSignboardBase_{rot}.png"], (raw_h, raw_h), 16
        )
        holo_thumb = checker_thumbnail(
            wall_images[f"WallHoloSignboardHologram_{rot}.png"],
            (vw - raw_h - 10, raw_h),
            16,
        )
        out.alpha_composite(base_thumb, (x, y))
        out.alpha_composite(holo_thumb, (x + raw_h + 10, y))
    out.convert("RGB").save(PREVIEW_WALL, optimize=True)


def make_preview(images, wall_images):
    width, height = 2140, 1560
    out = Image.new("RGBA", (width, height), (26, 34, 30, 255))
    d = ImageDraw.Draw(out)
    title_font = get_font(str(FONT_LATIN), 32)
    label_font = get_font(str(FONT_LATIN), 18)
    d.text(
        (30, 18),
        "ICCT  /  HOLOGRAPHIC FRANCHISE SIGNBOARDS  (standing 2x1  +  wall 1x1)",
        font=title_font,
        fill=(222, 255, 181, 255),
    )
    entries = [
        ("STAND BASE S/N", images["HoloSignboardBase_south.png"], (30, 70), (420, 280)),
        ("STAND BASE W/E", images["HoloSignboardBase_west.png"], (470, 70), (240, 280)),
        (
            "STAND HOLO S/N",
            images["HoloSignboardHologram_south.png"],
            (30, 390),
            (470, 560),
        ),
        (
            "STAND HOLO W/E",
            images["HoloSignboardHologram_west.png"],
            (520, 390),
            (190, 560),
        ),
        ("STAND UI", images["HoloSignboard_UI.png"], (730, 70), (520, 520)),
        ("WALL UI", wall_images["WallHoloSignboard_UI.png"], (730, 630), (520, 520)),
    ]
    x = 1280
    for i, rot in enumerate(("north", "south", "east", "west")):
        entries.append(
            (
                f"WALL BASE {rot.upper()}",
                wall_images[f"WallHoloSignboardBase_{rot}.png"],
                (x + (i % 2) * 210, 70 + (i // 2) * 230),
                (200, 200),
            )
        )
    for i, rot in enumerate(("north", "south", "east", "west")):
        entries.append(
            (
                f"WALL HOLO {rot.upper()}",
                wall_images[f"WallHoloSignboardHologram_{rot}.png"],
                (x + (i % 2) * 420, 540 + (i // 2) * 470),
                (410, 420),
            )
        )
    for label, image, (ex, ey), bounds in entries:
        d.text((ex, ey), label, font=label_font, fill=(255, 213, 114, 255))
        out.alpha_composite(checker_thumbnail(image, bounds, 16), (ex, ey + 24))
    d.text(
        (30, 990),
        "NEON GREEN  x  SUNSET RED",
        font=title_font,
        fill=(255, 113, 66, 255),
    )
    for i, line in enumerate(
        (
            "Standing: tomato & egg rice / curry katsu rice; beam skirt seated in the base trough",
            "Wall: Sorrowful Rice (char siu, sunny egg, choy sum) on a rooster bowl",
            "Wall map ribbons follow vanilla Placeworker_AttachedToWall and top-down foreshortening",
            "Full wall menu is preserved in UI; map projections stay narrow at the base emitter",
        )
    ):
        d.text((30, 1040 + i * 30), line, font=label_font, fill=(215, 242, 194, 255))
    out.convert("RGB").save(PREVIEW, optimize=True)


def make_detail_previews(hologram, wall_front):
    """Nearest-neighbour crops make food and typography inspection repeatable."""
    crops = {
        "tomato_zoom.png": (hologram, (330, 310, 505, 478), 4),
        "curry_zoom.png": (hologram, (330, 483, 505, 650), 4),
        "title_zoom.png": (hologram, (320, 155, 710, 315), 4),
        "wall_bowl_zoom.png": (wall_front, (300, 248, 724, 476), 3),
        "wall_menu_zoom.png": (wall_front, (282, 470, 742, 640), 3),
    }
    for name, (image, box, k) in crops.items():
        crop = image.crop(box)
        bg = checker(crop.size, 8)
        bg.alpha_composite(crop)
        bg.resize((crop.width * k, crop.height * k), Image.Resampling.NEAREST).convert(
            "RGB"
        ).save(TOOL_DIR / name, optimize=True)


def anchor_report():
    """Numbers that tie each projection to its emitter slot."""
    slot_top, slot_bottom = 174, 211
    stand = {
        "base_slot_rows": [slot_top, slot_bottom],
        "base_slot_world_z": [
            round(stand_base_z(slot_top), 4),
            round(stand_base_z(slot_bottom), 4),
        ],
        "holo_rows_of_slot": [
            round(stand_holo_y(stand_base_z(slot_top)), 1),
            round(stand_holo_y(stand_base_z(slot_bottom)), 1),
        ],
        "holo_emission_row": STAND_EMIT_Y,
        "holo_clip": list(STAND_CLIP),
    }
    slot = wall_base_world("north", 128, 143)[1]
    wall = {
        "rotation_contract": "baked clockwise quarter turns; no UV mirror; quaternion identity",
        "north_slot_world": [0.0, round(slot, 4)],
        "east_slot_world": [round(slot, 4), 0.0],
        "south_slot_world": [0.0, -round(slot, 4)],
        "west_slot_world": [-round(slot, 4), 0.0],
        "panel_world_depth": 0.16,
        "beam_world_depth": round(slot - 0.78, 4),
        "panel_world_width": 1.0,
    }
    return {"standing": stand, "wall": wall}


def save_set(images, folder, report):
    folder.mkdir(parents=True, exist_ok=True)
    for name, image in images.items():
        path = folder / name
        image.save(path, optimize=True)
        stats = texture_stats(image)
        stats["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        report[f"{folder.name}/{name}"] = stats


def main():
    base_south = draw_base_south()
    base_west = draw_base_west()
    holo_south = draw_hologram_front()
    holo_west = draw_hologram_west()

    images = {
        "HoloSignboardBase_south.png": base_south,
        "HoloSignboardBase_north.png": base_south.copy(),
        "HoloSignboardBase_east.png": base_west.transpose(
            Image.Transpose.FLIP_LEFT_RIGHT
        ),
        "HoloSignboardBase_west.png": base_west,
        "HoloSignboardHologram_south.png": holo_south,
        "HoloSignboardHologram_north.png": holo_south.copy(),
        "HoloSignboardHologram_east.png": holo_west.transpose(
            Image.Transpose.FLIP_LEFT_RIGHT
        ),
        "HoloSignboardHologram_west.png": holo_west,
    }
    images["HoloSignboard_UI.png"] = make_ui(holo_south, base_south)

    panel_ss = draw_wall_panel_ss()
    # Keep the full frontal panel exclusively for the build icon and zooms.
    wall_ui_hologram = draw_wall_hologram_north(panel_ss)
    wall_base_north = draw_wall_base_north()
    map_holograms = cardinal_images(draw_wall_map_north(panel_ss))
    map_bases = cardinal_images(wall_base_north)
    wall_images = {
        "WallHoloSignboardBase_north.png": wall_base_north,
        "WallHoloSignboardBase_south.png": map_bases["south"],
        "WallHoloSignboardBase_east.png": map_bases["east"],
        "WallHoloSignboardBase_west.png": map_bases["west"],
        "WallHoloSignboardHologram_north.png": map_holograms["north"],
        "WallHoloSignboardHologram_south.png": map_holograms["south"],
        "WallHoloSignboardHologram_east.png": map_holograms["east"],
        "WallHoloSignboardHologram_west.png": map_holograms["west"],
    }
    wall_images["WallHoloSignboard_UI.png"] = make_wall_ui(
        wall_ui_hologram, wall_base_north
    )

    report = {"anchors": anchor_report()}
    save_set(images, OUT, report)
    save_set(wall_images, WALL_OUT, report)
    make_standing_verification(base_south, holo_south)
    make_wall_preview(wall_images)
    make_preview(images, wall_images)
    make_detail_previews(holo_south, wall_ui_hologram)
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report["anchors"], ensure_ascii=False, indent=2))
    print(f"\nWrote {len(images)} textures to {OUT}")
    print(f"Wrote {len(wall_images)} textures to {WALL_OUT}")
    print(f"Preview: {PREVIEW}, {PREVIEW_WALL}, {VERIFY_STANDING}")


if __name__ == "__main__":
    main()
