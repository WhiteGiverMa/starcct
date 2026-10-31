# -*- coding: utf-8 -*-
"""
gen_textures.py — 程序化生成 RimWorld mod「食品级塑料粒 / 食品级塑料片」物品贴图
================================================================================
产出（运行本脚本即可无交互全量重新生成，随机性来自固定 SEED）：
  assets/PlasticGranule_a.png  散落的少量塑料粒      (~12-18% 覆盖)
  assets/PlasticGranule_b.png  聚成小堆的塑料粒      (~38-47%)
  assets/PlasticGranule_c.png  敞口方盒装满塑料粒    (~53-64%)
  assets/PlasticSheet_a.png    零散几片片材          (~12-18%)
  assets/PlasticSheet_b.png    摞成有厚度的片堆      (~38-47%)
  assets/PlasticSheet_c.png    水平躺放的片材卷      (~50-63%)
  preview.png                  3×2 预览合集（4x 最近邻放大 + 棋盘格 + 标签条）

风格对标原版（依据 rw-texture-probe 对 Steel/WoodLog/Cloth 的程序化分析）：
  * 64×64 RGBA，alpha 二值（Cutout shader 在 alpha<0.5 硬切）
  * 主体纯黑 #000000 描边：整体轮廓约 2px（256 画布上 6-8px），小颗粒约 1.5px
  * 左上 45° 主光：左上亮、右下暗，cel 分层着色（离散色阶而非渐变）
  * 全透明像素 RGB=(0,0,0)（防 BC7 压缩白边）
  * 阴影=不透明区域内部 RGB 变暗，不用低 alpha（会被硬切）
  * 覆盖率对标原版：Steel_a 18.7% / Steel_b 45.8% / Steel_c 64%

管线：256×256 超采样绘制 → LANCZOS 缩到 64 → alpha 阈值化(>=128)
      → 去孤岛(<12px 连通域删除) → 填破洞(封闭透明区填黑当缝隙)
      → QA（覆盖率/边距/二值alpha/孤岛残留/描边连续性）

用法： py -3.15 gen_textures.py   （需 Pillow）
"""

import math
import random
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont

# ---------------------------------------------------------------- 基本常量
SIZE = 64  # 最终尺寸
SS = 256  # 超采样尺寸
SEED = 20261031  # 固定随机种子，保证可复现
ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"

# ---------------------------------------------------------------- 色板
# 食品级塑料（PET/PP）：干净微透的乳白 / 淡青白，低饱和
OUTLINE = (0, 0, 0, 255)  # 纯黑描边（原版实证）
HL = (250, 253, 254, 255)  # 高光
LIGHT = (238, 244, 246, 255)  # 亮面
BASE = (222, 232, 235, 255)  # 基准面
COOL = (203, 218, 224, 255)  # 冷调中间面（半透明感）
SHADE = (178, 197, 206, 255)  # 暗面
DEEP = (148, 169, 181, 255)  # 最暗面
EDGE = (161, 183, 193, 255)  # 薄片侧棱
# 包装盒（比内容物稍暗稍蓝，读作“容器”）
B_FRONT = (190, 206, 215, 255)
B_LIGHT = (212, 226, 232, 255)
B_SHADE = (154, 175, 187, 255)
B_DEEP = (122, 143, 156, 255)
B_IN = (108, 128, 140, 255)  # 盒腔内部阴影


# ---------------------------------------------------------------- 几何工具
def ell_pts(cx, cy, rx, ry, rot=0.0, n=18):
    """旋转椭圆的多边形顶点"""
    c, s = math.cos(rot), math.sin(rot)
    pts = []
    for i in range(n):
        t = 2.0 * math.pi * i / n
        x, y = math.cos(t) * rx, math.sin(t) * ry
        pts.append((cx + x * c - y * s, cy + x * s + y * c))
    return pts


def quad(cx, cy, w, h, rot=0.0):
    """中心/宽高/旋转角 → 矩形四角（顺时针）"""
    c, s = math.cos(rot), math.sin(rot)
    u = (c * w / 2, s * w / 2)  # 长轴方向半宽
    v = (-s * h / 2, c * h / 2)  # 短轴方向半高
    return [
        (cx - u[0] - v[0], cy - u[1] - v[1]),
        (cx + u[0] - v[0], cy + u[1] - v[1]),
        (cx + u[0] + v[0], cy + u[1] + v[1]),
        (cx - u[0] + v[0], cy - u[1] + v[1]),
    ]


def lerp_pts(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


# ---------------------------------------------------------------- 描边工具
def outline_silhouette(layer, o):
    """对整层不透明轮廓向外扩 o px 的纯黑描边（画在轮廓外侧，不吞内部细节）。"""
    m = layer.getchannel("A")
    dil = m.filter(ImageFilter.MaxFilter(2 * o + 1))
    ring = ImageChops.subtract(dil, m).point(lambda v: 255 if v > 10 else 0)
    black = Image.new("RGBA", layer.size, OUTLINE)
    black.putalpha(ring)
    return Image.alpha_composite(black, layer)


# ---------------------------------------------------------------- 基础图元
def draw_granule(dr, cx, cy, rx, ry, rot, tone, o=6, hl=True):
    """单颗塑料粒：黑描边 + 主体 + 右下残月暗面 + 左上高光点"""
    dr.polygon(ell_pts(cx, cy, rx + o, ry + o, rot), fill=OUTLINE)
    dr.polygon(ell_pts(cx, cy, rx, ry, rot), fill=tone)
    dr.polygon(ell_pts(cx + 2.2, cy + 2.2, rx, ry, rot), fill=SHADE)
    dr.polygon(ell_pts(cx, cy, rx, ry, rot), fill=tone)
    if hl:
        hrx, hry = max(2.0, rx * 0.24), max(1.6, ry * 0.26)
        dr.polygon(ell_pts(cx - rx * 0.38, cy - ry * 0.40, hrx, hry, rot), fill=HL)


def draw_sheet(dr, cx, cy, w, h, rot, o=6, face=LIGHT, band=BASE, side=EDGE):
    """单片片材：黑描边 + 下侧厚度面 + 上表面（上亮下暗两段）。
    边角略翘：远端角顶点沿短轴外推一点，形成微弯翘角。"""
    q = quad(cx, cy, w, h, rot)
    v = (-math.sin(rot), math.cos(rot))
    lift = h * 0.16
    q[2] = (q[2][0] + v[0] * lift, q[2][1] + v[1] * lift)
    q[3] = (q[3][0] + v[0] * lift * 0.4, q[3][1] + v[1] * lift * 0.4)
    # 描边（顶点整体外扩近似）
    cxq = sum(p[0] for p in q) / 4.0
    cyq = sum(p[1] for p in q) / 4.0
    oq = []
    for p in q:
        dx, dy = p[0] - cxq, p[1] - cyq
        d = math.hypot(dx, dy) or 1.0
        oq.append((p[0] + dx / d * o, p[1] + dy / d * o))
    dr.polygon(oq, fill=OUTLINE)
    # 厚度侧面（向右下偏移）
    t = max(3.0, o * 0.8)
    off = (
        -math.sin(rot) * t + math.cos(rot) * t * 0.5,
        math.cos(rot) * t + math.sin(rot) * t * 0.5,
    )
    dr.polygon([(p[0] + off[0], p[1] + off[1]) for p in q], fill=side)
    # 上表面：上 60% face 色、下 40% band 色
    A, B, C, D = q
    m1, m2 = lerp_pts(B, C, 0.62), lerp_pts(A, D, 0.62)
    dr.polygon([A, B, m1, m2], fill=face)
    dr.polygon([m2, m1, C, D], fill=band)
    dr.line([A, B], fill=HL, width=2)  # 顶边高光线


# ---------------------------------------------------------------- 后处理
def finalize(ss_img):
    """256 超采样 → 64：LANCZOS 缩小 → alpha 二值化 → 去孤岛 → 填破洞"""
    img = ss_img.convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
    px = img.load()
    w = h = SIZE
    opaque = [[px[x, y][3] >= 128 for x in range(w)] for y in range(h)]

    def components(sel):
        seen = [[False] * w for _ in range(h)]
        comps = []
        for y in range(h):
            for x in range(w):
                if sel[y][x] and not seen[y][x]:
                    comp = []
                    dq = deque([(x, y)])
                    seen[y][x] = True
                    while dq:
                        cx, cy = dq.popleft()
                        comp.append((cx, cy))
                        for nx, ny in (
                            (cx + 1, cy),
                            (cx - 1, cy),
                            (cx, cy + 1),
                            (cx, cy - 1),
                        ):
                            if (
                                0 <= nx < w
                                and 0 <= ny < h
                                and sel[ny][nx]
                                and not seen[ny][nx]
                            ):
                                seen[ny][nx] = True
                                dq.append((nx, ny))
                    comps.append(comp)
        return comps

    # 1) 去孤岛：<12px 的不透明连通域视为 AA 残渣删除
    for comp in components(opaque):
        if len(comp) < 12:
            for x, y in comp:
                opaque[y][x] = False

    # 2) 填破洞：不接触画布边缘的透明连通域 → 填黑（读作缝隙/内阴影）
    trans = [[not opaque[y][x] for x in range(w)] for y in range(h)]
    for comp in components(trans):
        touches = any(x == 0 or x == w - 1 or y == 0 or y == h - 1 for x, y in comp)
        if not touches:
            for x, y in comp:
                opaque[y][x] = True
                px[x, y] = (0, 0, 0, 255)

    # 3) 写回：不透明保留颜色，透明统一 (0,0,0,0)
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    op = out.load()
    for y in range(h):
        for x in range(w):
            if opaque[y][x]:
                r, g, b, _ = px[x, y]
                op[x, y] = (r, g, b, 255)
    return out


# ---------------------------------------------------------------- QA
def qa(img, name, cov_win):
    px = img.load()
    opaque = [(x, y) for y in range(SIZE) for x in range(SIZE) if px[x, y][3] == 255]
    cov = len(opaque) / (SIZE * SIZE)
    xs = [p[0] for p in opaque]
    ys = [p[1] for p in opaque]
    bbox = (min(xs), min(ys), max(xs), max(ys))
    margin = (bbox[0], bbox[1], SIZE - 1 - bbox[2], SIZE - 1 - bbox[3])
    mid = sum(1 for y in range(SIZE) for x in range(SIZE) if 0 < px[x, y][3] < 255)
    oset = set(opaque)
    bnd = [
        p
        for p in opaque
        if any(
            0 <= p[0] + dx < SIZE
            and 0 <= p[1] + dy < SIZE
            and (p[0] + dx, p[1] + dy) not in oset
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )
    ]
    blackb = sum(1 for p in bnd if sum(px[p[0], p[1]][:3]) < 150)
    ratio = blackb / len(bnd) if bnd else 1.0
    lo, hi = cov_win
    ok = (lo <= cov <= hi) and min(margin) >= 2 and mid == 0 and ratio >= 0.5
    print(
        f"  {name:<20} cov={cov * 100:5.1f}% (target {lo * 100:.0f}-{hi * 100:.0f}%)  "
        f"bbox={bbox} {bbox[2] - bbox[0] + 1}x{bbox[3] - bbox[1] + 1}  margin={margin}  "
        f"midAlpha={mid}  outline={ratio * 100:4.0f}%  {'OK' if ok else '** CHECK **'}"
    )
    return ok


def coverage(ss_layer):
    """粗测 256 层的覆盖率（按缩放后估算，直接用 alpha>0.5 计数/16）"""
    small = ss_layer.convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
    px = small.load()
    return sum(1 for y in range(SIZE) for x in range(SIZE) if px[x, y][3] >= 128) / (
        SIZE * SIZE
    )


# ================================================================ 各贴图
def gen_granule_a():
    """散落的少量塑料粒：十几颗小椭圆随意散布（互不重叠，无整体描边以免连成网）"""
    rng = random.Random(SEED + 1)
    tones = [BASE, LIGHT, COOL, BASE, LIGHT, COOL, BASE]
    cands = []
    tries = 0
    while len(cands) < 16 and tries < 800:
        tries += 1
        a = rng.uniform(0, 2 * math.pi)
        r = math.sqrt(rng.random())
        x = 128 + math.cos(a) * r * 72
        y = 130 + math.sin(a) * r * 52
        # 间距需大于两颗外扩描边之和，避免 MaxFilter 描边互相粘连
        if all((x - p[0]) ** 2 + (y - p[1]) ** 2 > 40**2 for p in cands):
            cands.append((x, y))
    layer = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    for i, (x, y) in enumerate(cands[:13]):
        rx = rng.uniform(10, 13.5)
        ry = rng.uniform(8, 10.5)
        rot = rng.uniform(-0.7, 0.7)
        draw_granule(dr, x, y, rx, ry, rot, tones[i % len(tones)], o=6, hl=(i % 3 != 1))
    return layer


def gen_granule_b():
    """较多的塑料粒：几十颗排成近梯形实堆（对标原版 Steel_b 的紧凑 bbox），
    行间距小于颗粒长轴 → 堆体基本无透空，行缘呈扇贝状"""
    rng = random.Random(SEED + 2)
    tones = [BASE, LIGHT, COOL, BASE, LIGHT, COOL, SHADE]
    layer = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    total = 0
    # 从最上行往下画：下行（前景）压住上行（远景），露出的是各行的下缘弧
    ys = [118, 130, 142, 154, 166, 178, 190]
    for row, y in enumerate(ys):
        hw = 78 + (y - 118) / (190 - 118) * 26  # 顶行半宽78 → 底行半宽104
        step = 21.5
        x = 128 - hw + rng.uniform(-3, 3)
        while x < 128 + hw:
            rx = rng.uniform(12, 15)
            ry = rng.uniform(9, 11)
            rot = rng.uniform(-0.55, 0.55)
            tone = tones[total % len(tones)]
            if row == 0:
                tone = COOL  # 堆顶稍冷（远）
            draw_granule(
                dr, x, y, rx, ry, rot, tone, o=6, hl=(row >= 2 and total % 2 == 0)
            )
            total += 1
            x += step + rng.uniform(-3, 3)
    print(f"  [granule_b] granules drawn = {total}")
    return outline_silhouette(layer, 6)


def _box_layer(L, R, BOT, RIM, BACK):
    """敞口方盒：前壁 + 后壁沿条（画在颗粒之上时前壁遮挡堆的下半）"""
    box = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    db = ImageDraw.Draw(box)
    # 前壁
    db.rectangle((L, RIM, R, BOT), fill=B_FRONT)
    db.rectangle((L, RIM, L + 12, BOT), fill=B_LIGHT)  # 左受光棱
    db.rectangle((R - 16, RIM, R, BOT), fill=B_SHADE)  # 右背光棱
    db.rectangle((L, BOT - 14, R, BOT), fill=B_DEEP)  # 底部暗带
    db.rectangle((L, RIM, R, RIM + 9), fill=B_LIGHT)  # 盒口前沿高光
    # 后壁沿条（内腔远端可见的外壁顶条）
    db.rectangle((L, BACK, R, BACK + 9), fill=B_SHADE)
    db.rectangle((L, BACK, L + 12, BACK + 9), fill=B_FRONT)
    db.rectangle((R - 16, BACK, R, BACK + 9), fill=B_DEEP)
    return box


def gen_granule_c():
    """装盒的塑料粒：浅色敞口方盒装满颗粒，盒口能看到颗粒堆顶面（冒出后沿）"""
    rng = random.Random(SEED + 3)
    L, R = 26, 230  # 盒外壁（256 坐标）→ 64 下约 51px 宽
    BOT, RIM, BACK = 230, 136, 92
    # --- 颗粒堆（画在盒腔上方，前壁稍后压住其下缘）---
    heap = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    dh = ImageDraw.Draw(heap)
    cands = []
    for _ in range(56):
        x = rng.uniform(L + 16, R - 16)
        dome = 24 * max(0.0, 1 - ((x - 128) / 96.0) ** 2)
        y = (BACK + 14) - dome * rng.uniform(0.25, 1.0) + rng.uniform(0, 24)
        cands.append((x, y))
    cands.sort(key=lambda p: (p[1], p[0]))  # 上（远）先画
    tones = [BASE, LIGHT, COOL, BASE, LIGHT]
    drawn = 0
    for i, (x, y) in enumerate(cands):
        rx = rng.uniform(10, 13)
        ry = rng.uniform(8, 10)
        rot = rng.uniform(-0.7, 0.7)
        tone = SHADE if i < 8 else tones[i % len(tones)]
        draw_granule(dh, x, y, rx, ry, rot, tone, o=6, hl=(i >= 10 and i % 2 == 0))
        drawn += 1
        if drawn >= 48:
            break
    print(f"  [granule_c] heap granules drawn = {drawn}")
    # 合成：描边盒体 → 颗粒堆（盖住后沿区域）→ 前壁再压住堆的下缘
    box = _box_layer(L, R, BOT, RIM, BACK)
    layer = Image.alpha_composite(outline_silhouette(box, 7), heap)
    layer = Image.alpha_composite(layer, box)
    return layer


def gen_sheet_a():
    """零散几片片材：3 片带角度叠放、边缘微翘"""
    layer = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    sheets = [
        ((-4, -14), 92, 56, -0.26, COOL, SHADE),
        ((8, 0), 100, 60, 0.14, LIGHT, BASE),
        ((-6, 14), 82, 52, -0.46, BASE, COOL),
    ]
    for i, (off, w, h, rot, face, band) in enumerate(sheets):
        draw_sheet(
            dr,
            128 + off[0],
            130 + off[1],
            w,
            h,
            rot,
            o=6,
            face=face,
            band=band,
            side=EDGE if i != 0 else SHADE,
        )
    # 最上层片材翘角处的小高光翻片
    qx = 128 - 6 + 40 * math.cos(-0.46)
    qy = 130 + 14 + 26 * math.sin(-0.46)
    q = quad(qx, qy, 24, 13, -0.46 - 0.5)
    dr.polygon([(p[0] + 3, p[1] + 3) for p in q], fill=OUTLINE)
    dr.polygon(q, fill=HL)
    return outline_silhouette(layer, 6)


def gen_sheet_b():
    """较多片材：10 片上下摞成有厚度的片堆 + 右侧斜靠一片（对标原木板堆构图）"""
    rng = random.Random(SEED + 5)
    layer = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    tones = [BASE, COOL, LIGHT, COOL, BASE, LIGHT]
    # 斜靠片（先画，被堆体遮挡根部）
    draw_sheet(dr, 182, 118, 62, 92, 0.55, o=5, face=COOL, band=SHADE, side=SHADE)
    # 堆体：从上往下逐片画（前片压后片），宽度/位置带抖动
    n = 0
    y = 34
    while y < 186:
        w = rng.uniform(150, 168)
        off = rng.uniform(-12, 12) + (5 if n % 2 == 0 else -5)
        tone = tones[n % len(tones)]
        draw_sheet(
            dr,
            124 + off * 0.5,
            y,
            w,
            17,
            rng.uniform(-0.04, 0.04),
            o=5,
            face=tone,
            band=SHADE if n else EDGE,
            side=EDGE,
        )
        n += 1
        y += 15.5
    # 顶片：露出完整上表面的单片
    draw_sheet(dr, 124, y - 12, 142, 30, -0.10, o=5, face=LIGHT, band=BASE, side=EDGE)
    print(f"  [sheet_b] sheets in stack = {n + 1}")
    return outline_silhouette(layer, 6)


def gen_sheet_c():
    """卷装片材：水平躺放的卷，右端面同心圆，筒身薄膜光泽，左下展开一段卷尾"""
    body = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    dr = ImageDraw.Draw(body)
    cx, cy, r = 148, 136, 86
    tube_l = cx - 42
    top, bot = cy - r, cy + r
    # --- 左下展开的片尾（先画，筒身压住其根部）---
    flap = [
        (tube_l + 8, bot - 24),
        (48, bot - 6),
        (62, bot + 14),
        (tube_l + 12, bot - 4),
    ]
    dr.polygon([(p[0] + 4, p[1] + 4) for p in flap], fill=OUTLINE)
    dr.polygon(flap, fill=LIGHT)
    dr.polygon(
        [
            lerp_pts(flap[0], flap[3], 0.7),
            lerp_pts(flap[1], flap[2], 0.7),
            flap[2],
            flap[3],
        ],
        fill=SHADE,
    )
    dr.ellipse((44, bot - 10, 76, bot + 16), fill=OUTLINE)  # 卷尾小卷筒
    dr.ellipse((48, bot - 6, 72, bot + 12), fill=BASE)
    dr.ellipse((56, bot - 1, 66, bot + 7), fill=COOL)
    # --- 筒身 ---
    dr.rectangle((tube_l, top, cx, bot), fill=BASE)
    dr.rectangle((tube_l, top, cx, top + 32), fill=LIGHT)  # 顶部受光带
    dr.rectangle((tube_l, bot - 28, cx, bot), fill=SHADE)  # 底部暗带
    dr.rectangle((tube_l, bot - 11, cx, bot), fill=DEEP)
    dr.rectangle(
        (tube_l + 10, top + 10, tube_l + 26, bot - 16), fill=HL
    )  # 薄膜高光竖条
    dr.rectangle((tube_l, top, tube_l + 6, bot), fill=EDGE)  # 左棱
    # --- 右端面：同心圆 ---
    dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=OUTLINE)
    rings = [
        (1.00, COOL),
        (0.86, BASE),
        (0.72, LIGHT),
        (0.59, COOL),
        (0.47, BASE),
        (0.36, LIGHT),
        (0.26, COOL),
        (0.16, BASE),
        (0.07, LIGHT),
    ]
    for f, col in rings:
        rr = r * f
        dr.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=col)
    # 卷材起始缝
    a = math.radians(38)
    dr.line(
        [(cx, cy), (cx + math.cos(a) * r * 0.9, cy + math.sin(a) * r * 0.9)],
        fill=DEEP,
        width=6,
    )
    # 左上弧形高光（薄膜反光）
    rr = r * 0.80
    dr.arc((cx - rr, cy - rr, cx + rr, cy + rr), 195, 258, fill=HL, width=7)
    rr = r * 0.55
    dr.arc((cx - rr, cy - rr, cx + rr, cy + rr), 200, 250, fill=LIGHT, width=5)
    # 端面外缘暗圈（与筒身的分界）
    rr = r - 5
    dr.arc((cx - rr, cy - rr, cx + rr, cy + rr), 90, 300, fill=SHADE, width=5)
    return outline_silhouette(body, 7)


# ================================================================ 预览
def make_preview(paths):
    names = [p.stem for p in paths]
    scale, gap, margin, label_h = 4, 10, 10, 26
    tile = SIZE * scale
    W = margin * 2 + tile * 3 + gap * 2
    H = margin * 2 + (tile + label_h) * 2 + gap
    cv = Image.new("RGBA", (W, H), (250, 250, 250, 255))
    dr = ImageDraw.Draw(cv)
    font = None
    for fp in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc"):
        try:
            font = ImageFont.truetype(fp, 15)
            break
        except OSError:
            continue
    for i, (p, name) in enumerate(zip(paths, names)):
        row, col = divmod(i, 3)
        x0 = margin + col * (tile + gap)
        y0 = margin + row * (tile + label_h + gap)
        check = 12
        for yy in range(0, tile, check):
            for xx in range(0, tile, check):
                c = (
                    (255, 255, 255, 255)
                    if (xx // check + yy // check) % 2 == 0
                    else (204, 204, 204, 255)
                )
                dr.rectangle(
                    (x0 + xx, y0 + yy, x0 + xx + check - 1, y0 + yy + check - 1), fill=c
                )
        big = Image.open(p).resize((tile, tile), Image.NEAREST)
        cv.paste(big, (x0, y0), big)
        dr.rectangle(
            (x0, y0 + tile, x0 + tile, y0 + tile + label_h), fill=(24, 26, 30, 255)
        )
        if font:
            tw = dr.textlength(name, font=font)
            dr.text(
                (x0 + (tile - tw) / 2, y0 + tile + 4),
                name,
                font=font,
                fill=(240, 240, 240, 255),
            )
    cv.save(ROOT / "preview.png")
    print(f"preview.png -> {ROOT / 'preview.png'}  ({W}x{H})")


# ================================================================ 主流程
def build_all():
    ASSETS.mkdir(parents=True, exist_ok=True)
    print("生成中 ...")
    results = [
        ("PlasticGranule_a.png", finalize(gen_granule_a()), (0.12, 0.18)),
        ("PlasticGranule_b.png", finalize(gen_granule_b()), (0.385, 0.47)),
        ("PlasticGranule_c.png", finalize(gen_granule_c()), (0.53, 0.645)),
        ("PlasticSheet_a.png", finalize(gen_sheet_a()), (0.12, 0.18)),
        ("PlasticSheet_b.png", finalize(gen_sheet_b()), (0.385, 0.47)),
        ("PlasticSheet_c.png", finalize(gen_sheet_c()), (0.50, 0.63)),
    ]
    print("\nQA：")
    all_ok = True
    paths = []
    for name, img, win in results:
        p = ASSETS / name
        img.save(p)
        paths.append(p)
        all_ok = qa(img, name, win) and all_ok
    make_preview(paths)
    print("\n结论：", "全部通过" if all_ok else "存在需人工复核项（见上 CHECK 行）")
    return all_ok


if __name__ == "__main__":
    build_all()
