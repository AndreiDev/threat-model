#!/usr/bin/env python3
"""
paint_vanitas.py  --  "Memento expirare", a vanitas still life painted entirely by code.

    python3 tools/paint_vanitas.py            # renders out/vanitas.png + out/vanitas-timelapse.mp4

Options: --scale 1.25 (canvas = 2400x1600 * scale), --no-video, --ref-only, --seed N.
Needs Python 3.11, numpy and Pillow; ffmpeg on PATH for the timelapse. No image models.

Pipeline
  1. Scene. Every object is built procedurally in numpy: lathe (surface of revolution) solids
     for the candlestick, candle and hourglass, an inverse-mapped curled page surface for the
     open book, signed-distance heightfields for the key, seal, watch and fly, analytic petals.
     Shading is Lambert + Blinn specular, an environment lookup that contains the window (so
     glass and brass reflect a real leaded window), wrap lighting for wax and petals, refraction
     for the glass, and cast shadows projected from a single window light onto ledge and wall.
     The result is the underpainting reference.
  2. Painting. Hertzmann-style multi-pass painting: brush radii from large to small; each pass
     places strokes where the canvas still differs from a blurred reference, traces curved strokes
     perpendicular to the image gradient (structure tensor), and paints them in random order.
     Strokes are forward-splatted ribbons with bristle textures, dry-brush break-up, ragged edges,
     per-bristle colour jitter and per-channel Kubelka-Munk mixing with the wet paint below.
     Every stroke deposits paint thickness into a height map.
  3. Finish. Glazes (transparent K/S layers) deepen shadows; lead-white impasto dabs on highlights;
     the height map, a linen weave and a craquelure network are lit for relief; a light varnish
     yellows the result very slightly.
  4. Timelapse. Canvas snapshots taken between strokes are written as frames to a temporary
     directory, encoded with ffmpeg (H.264, 1620x1080), and the directory is deleted.
All randomness comes from seeded numpy Generators, so a render is reproducible.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "out")

DW, DH = 2400, 1600          # design space; everything below is laid out in these units
SINP = 0.30                  # view tilt: we look down on the ledge by asin(0.3) ~ 17.5 deg
COSP = math.sqrt(1 - SINP * SINP)
LEDGE_FRONT, LEDGE_BACK = 1290.0, 1130.0
WALL_ZB = (LEDGE_FRONT - LEDGE_BACK) / SINP


def nrm(v):
    v = np.asarray(v, np.float32)
    return v / np.linalg.norm(v)


LDIR = nrm([-0.50, 0.78, 0.42])     # toward the window (world: x right, y up, z toward viewer)
VDIR = nrm([0.0, SINP, COSP])       # toward the viewer
HDIR = nrm(LDIR + VDIR)
SUN = np.array([1.00, 0.985, 0.96], np.float32) * 1.25   # window light (slightly cool daylight)
AMB = np.array([0.050, 0.043, 0.036], np.float32)        # warm bounce in the room


# ----------------------------------------------------------------------------------------
# small numeric helpers
# ----------------------------------------------------------------------------------------
def s2l(c):
    """sRGB 0..255 (or 0..1 floats > 1 means 255 scale) to linear."""
    c = np.asarray(c, np.float32)
    if c.max() > 1.0:
        c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)


def l2s(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055).astype(np.float32)


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    return a + (b - a) * t


def _box(a, r, axis):
    if r < 1:
        return a
    n = a.shape[axis]
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    p = np.pad(a, pad, mode="edge")
    c = np.cumsum(p, axis=axis, dtype=np.float64)
    sl_hi = [slice(None)] * a.ndim
    sl_lo = [slice(None)] * a.ndim
    sl_hi[axis] = slice(2 * r + 1, 2 * r + 1 + n)
    sl_lo[axis] = slice(0, n)
    return ((c[tuple(sl_hi)] - c[tuple(sl_lo)]) / (2 * r + 1)).astype(np.float32)


def blur(a, sigma):
    """Gaussian blur: exact separable kernel for small sigma, three box passes (cumsum) otherwise."""
    a = np.asarray(a, np.float32)
    if sigma <= 0.05:
        return a
    if sigma < 2.0:
        rad = int(math.ceil(3 * sigma))
        xs = np.arange(-rad, rad + 1, dtype=np.float32)
        k = np.exp(-xs * xs / (2 * sigma * sigma))
        k /= k.sum()
        for ax in (0, 1):
            p = np.pad(a, [(rad, rad) if i == ax else (0, 0) for i in range(a.ndim)], mode="edge")
            n = a.shape[ax]
            acc = np.zeros_like(a)
            for i, w in enumerate(k):
                sl = [slice(None)] * a.ndim
                sl[ax] = slice(i, i + n)
                acc += w * p[tuple(sl)]
            a = acc
        return a
    r = int(round((math.sqrt(4 * sigma * sigma + 1) - 1) / 2))
    r = max(r, 1)
    for ax in (0, 1):
        for _ in range(3):
            a = _box(a, r, ax)
    return a


def resize_f(a, w, h, resample=Image.BILINEAR):
    """Resize a float32 2D or 3D array with Pillow (per channel, mode F)."""
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((w, h), resample), np.float32)
    return np.stack([resize_f(a[..., i], w, h, resample) for i in range(a.shape[2])], -1)


def noise(shape, cell, rng, aniso=(1.0, 1.0), octaves=1, gain=0.5):
    """Smooth value noise in [-1,1]-ish: random lattice upsampled bicubically. cell in pixels."""
    H, W = shape
    out = np.zeros((H, W), np.float32)
    amp, tot = 1.0, 0.0
    c = float(cell)
    for _ in range(octaves):
        gy = max(2, int(H / (c * aniso[0])) + 3)
        gx = max(2, int(W / (c * aniso[1])) + 3)
        g = rng.standard_normal((gy, gx)).astype(np.float32)
        up = resize_f(g, int(gx * c * aniso[1]), int(gy * c * aniso[0]), Image.BICUBIC)
        oy = rng.integers(0, max(1, up.shape[0] - H + 1))
        ox = rng.integers(0, max(1, up.shape[1] - W + 1))
        tile = up[oy:oy + H, ox:ox + W]
        if tile.shape != (H, W):
            tile = resize_f(up, W, H, Image.BICUBIC)
        out += amp * tile
        tot += amp
        amp *= gain
        c = max(1.0, c / 2)
    return out / tot


def sample(img, x, y):
    """Bilinear sample of img (H,W[,C]) at float pixel coords (arrays)."""
    H, W = img.shape[:2]
    x = np.clip(x, 0, W - 1.001)
    y = np.clip(y, 0, H - 1.001)
    x0 = x.astype(np.int32)
    y0 = y.astype(np.int32)
    fx = x - x0
    fy = y - y0
    if img.ndim == 3:
        fx = fx[..., None]
        fy = fy[..., None]
    a = img[y0, x0]
    b = img[y0, x0 + 1]
    c = img[y0 + 1, x0]
    d = img[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def dot3(n, v):
    return n[..., 0] * v[0] + n[..., 1] * v[1] + n[..., 2] * v[2]


def normalize3(n):
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)


def find_font(names, size):
    dirs = ["/System/Library/Fonts/Supplemental", "/System/Library/Fonts", "/Library/Fonts",
            os.path.expanduser("~/Library/Fonts"), "/usr/share/fonts/truetype/dejavu"]
    for n in names:
        for d in dirs:
            p = os.path.join(d, n)
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def text_mask(lines, font, size_wh, xy=(0, 0), spacing=1.25, anchor="la", align_center=False):
    """Render lines of text into a float mask (H,W)."""
    W, H = size_wh
    im = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(im)
    x, y = xy
    asc = font.getbbox("Hg")[3]
    for ln in lines:
        if align_center:
            w = dr.textlength(ln, font=font)
            dr.text((x - w / 2, y), ln, fill=255, font=font)
        else:
            dr.text((x, y), ln, fill=255, font=font)
        y += asc * spacing
    return np.asarray(im, np.float32) / 255.0


# ----------------------------------------------------------------------------------------
# environment: what shiny things reflect. A tall leaded window up-left, a dark warm room.
# ----------------------------------------------------------------------------------------
_e1 = nrm(np.cross([0, 1, 0], LDIR))
_e2 = nrm(np.cross(LDIR, _e1))


def env(R, rough=0.0, window=22.0):
    """Radiance seen along reflection directions R (...,3)."""
    u = dot3(R, _e1)
    v = dot3(R, _e2)
    w = dot3(R, LDIR)
    soft = 0.012 + rough
    win = sstep(0.17 + soft, 0.17 - soft, np.abs(u)) * sstep(0.25 + soft, 0.25 - soft, np.abs(v)) * (w > 0)
    # mullion cross and a few lead cames
    bars = np.minimum(sstep(0.008, 0.016 + rough, np.abs(u)), sstep(0.008, 0.016 + rough, np.abs(v)))
    if rough < 0.05:
        cames = sstep(0.0, 0.006, np.abs(((v + 0.25) % 0.083) - 0.0415) - 0.036)
        bars = bars * (0.55 + 0.45 * cames)
    win = win * bars
    glow = np.exp(-((u / 0.55) ** 2 + (v / 0.6) ** 2)) * (w > -0.2)
    room = np.where(R[..., 1] < 0, 0.05, 0.022)[..., None] * np.array([1.0, 0.82, 0.62], np.float32)
    sky = np.array([0.86, 0.93, 1.0], np.float32)
    return room + (window * win)[..., None] * sky + (0.35 * glow)[..., None] * sky


def reflect(N):
    d = dot3(N, VDIR)[..., None]
    return 2 * d * N - VDIR


def fresnel(N, f0=0.04):
    return f0 + (1 - f0) * (1 - np.clip(dot3(N, VDIR), 0, 1)) ** 5


# ----------------------------------------------------------------------------------------
# Scene container
# ----------------------------------------------------------------------------------------
class Scene:
    def __init__(self, scale, seed):
        self.S = scale
        self.W, self.H = int(round(DW * scale)), int(round(DH * scale))
        self.img = np.zeros((self.H, self.W, 3), np.float32)
        self.ids = np.zeros((self.H, self.W), np.uint8)
        self.detail = np.zeros((self.H, self.W), np.float32)   # 1 where small brushes are needed
        self.flow = np.full((self.H, self.W), np.nan, np.float32)  # optional stroke direction hint
        self.rng = np.random.default_rng(seed)
        self.boxes = {}

    # window helpers: design-space bbox -> pixel slice + design coordinate grids
    def win(self, x0, y0, x1, y1):
        S = self.S
        px0 = max(0, int(math.floor(x0 * S)))
        py0 = max(0, int(math.floor(y0 * S)))
        px1 = min(self.W, int(math.ceil(x1 * S)))
        py1 = min(self.H, int(math.ceil(y1 * S)))
        xs = (np.arange(px0, px1, dtype=np.float32) + 0.5) / S
        ys = (np.arange(py0, py1, dtype=np.float32) + 0.5) / S
        X, Y = np.meshgrid(xs, ys)
        return (slice(py0, py1), slice(px0, px1)), X, Y

    def put(self, sl, alpha, color, oid=None, detail=None, flow=None):
        a = np.clip(alpha, 0, 1)
        self.img[sl] = self.img[sl] * (1 - a[..., None]) + color * a[..., None]
        if oid is not None:
            self.ids[sl] = np.where(a > 0.5, oid, self.ids[sl])
        if detail is not None:
            self.detail[sl] = np.maximum(self.detail[sl], detail * (a > 0.3))
        if flow is not None:
            self.flow[sl] = np.where(a > 0.5, flow, self.flow[sl])

    def aa(self, sd):
        """signed distance (design units, negative inside) -> coverage."""
        return np.clip(0.5 - sd * self.S, 0, 1)


def light_falloff(X, Y):
    """The window light is a pool centred on the book and candle; it fades to the right."""
    d = ((X - 980) / 1350) ** 2 + ((Y - 1040) / 1100) ** 2
    return (0.16 + 0.84 * np.exp(-d * 1.9)).astype(np.float32)


# ----------------------------------------------------------------------------------------
# lathe solids: surfaces of revolution seen from slightly above
# ----------------------------------------------------------------------------------------
def profile(pts, n=600):
    """Catmull-Rom through (h, r) control points -> dense monotone-in-h tables."""
    P = np.asarray(pts, np.float32)
    P = np.vstack([P[0] * 2 - P[1], P, P[-1] * 2 - P[-2]])
    hs, rs = [], []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        t = np.linspace(0, 1, 24, endpoint=False)[:, None]
        q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                   + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
        hs.append(q[:, 0])
        rs.append(q[:, 1])
    h = np.concatenate(hs + [P[-2:-1, 0]])
    r = np.concatenate(rs + [P[-2:-1, 1]])
    order = np.argsort(h, kind="stable")
    h, r = h[order], np.maximum(r[order], 0)
    hd = np.linspace(h[0], h[-1], n).astype(np.float32)
    rd = np.interp(hd, h, r).astype(np.float32)
    return hd, rd


def lathe(X, Y, cx, yb, prof, S, iters=10):
    """Solve the visible front surface of a lathe solid. Returns coverage, h, normal, r, sin(theta)."""
    hd, rd = prof
    dx = X - cx
    h = (yb - Y) / COSP
    for _ in range(iters):
        r = np.interp(h, hd, rd)
        s = np.clip(dx / np.maximum(r, 1e-3), -1, 1)
        c = np.sqrt(1 - s * s)
        hn = (yb - Y + r * c * SINP) / COSP
        h = 0.5 * h + 0.5 * hn
    r = np.interp(h, hd, rd)
    dr = np.gradient(rd, hd)
    rp = np.interp(h, hd, dr)
    s = np.clip(dx / np.maximum(r, 1e-3), -1, 1)
    c = np.sqrt(np.clip(1 - s * s, 0, 1))
    cov = np.clip((r - np.abs(dx)) * S + 0.5, 0, 1)
    cov *= np.clip((h - hd[0]) * COSP * S + 0.5, 0, 1) * np.clip((hd[-1] - h) * COSP * S + 0.5, 0, 1)
    cov *= (r > 0.3)
    N = normalize3(np.stack([s, -rp, c], -1))
    # tilt into view frame: world y-up / z-toward-viewer already; viewer tilt handled via VDIR
    return cov, h, N, r, s


def ellipse_cap(X, Y, cx, yb, ht, rt, S):
    ey = yb - ht * COSP
    q = ((X - cx) / rt) ** 2 + ((Y - ey) / (rt * SINP)) ** 2
    sd = (np.sqrt(q) - 1) * rt * SINP  # approx distance
    return np.clip(0.5 - sd * S, 0, 1), q


# ----------------------------------------------------------------------------------------
# scene objects
# ----------------------------------------------------------------------------------------
OBJ = {"wall": 1, "ledge": 2, "candle": 3, "hourglass": 4, "book": 5, "key": 6, "tag": 7,
       "letter": 8, "watch": 9, "tulip": 10, "fly": 11, "smoke": 12}

CANDLE_X, CANDLE_YB = 1135.0, 1160.0
HG_X, HG_YB = 1505.0, 1214.0
BOOK = dict(x0=180.0, x1=1050.0, spine_top=1124.0, spine_bot=1246.0)
# open book: screen origin of the spine foot, page vectors (u: half spread, v: page height)
OB_O = np.array([615.0, 1106.0], np.float32)
OB_AU = np.array([405.0, -5.0], np.float32)
OB_AV = np.array([12.0, -272.0], np.float32)
OB_LEAN = math.radians(25.0)
WATCH = dict(cx=1772.0, cy=1170.0, r=68.0)
TAG = dict(cx=902.0, cy=1190.0, w=248.0, h=98.0, rot=-4.0)


def candlestick_profile():
    return profile([(0, 150), (6, 154), (14, 150), (22, 140), (30, 128), (36, 60), (44, 44), (70, 40),
                    (100, 52), (120, 58), (140, 50), (165, 26), (185, 22), (225, 30), (262, 36),
                    (295, 28), (325, 20), (345, 24), (360, 32), (368, 92), (378, 96), (386, 90),
                    (392, 44), (430, 42), (440, 46)])


CANDLE_H0, CANDLE_H1 = 432.0, 606.0


def candle_profile():
    return profile([(CANDLE_H0, 33), (CANDLE_H0 + 60, 33.5), (CANDLE_H1 - 40, 33), (CANDLE_H1, 32.5)])


def hg_glass_profile():
    return profile([(40, 52), (48, 74), (70, 98), (110, 112), (170, 115), (225, 104), (262, 78),
                    (290, 40), (304, 15), (315, 10), (326, 15), (340, 40), (368, 78), (405, 104),
                    (460, 115), (520, 112), (560, 98), (582, 74), (590, 52)])


HG_POST_R = 152.0
HG_POSTS = [(-58.0, "front"), (58.0, "front"), (180.0, "back")]


def hg_post_profile():
    return profile([(36, 16), (46, 16), (52, 11), (66, 14), (80, 9), (150, 8.5), (230, 11), (300, 13.5),
                    (370, 11), (450, 8.5), (520, 9), (534, 14), (548, 11), (556, 16), (594, 16)])


def hg_plate_profile(top=False):
    if top:
        return profile([(588, 170), (592, 182), (604, 182), (608, 177), (620, 179), (630, 172), (634, 160)])
    return profile([(0, 172), (8, 182), (20, 182), (24, 177), (32, 179), (40, 174), (44, 160)])


def silhouette_masks(sc):
    """Coarse silhouettes for cast shadows: list of (mask_full, yb, zb, strength)."""
    out = []
    S = sc.S
    # candle + candlestick
    sl, X, Y = sc.win(CANDLE_X - 170, 420, CANDLE_X + 170, CANDLE_YB + 60)
    m = np.zeros((sc.H, sc.W), np.float32)
    c1, *_ = lathe(X, Y, CANDLE_X, CANDLE_YB, candlestick_profile(), S)
    c2, *_ = lathe(X, Y, CANDLE_X, CANDLE_YB, candle_profile(), S)
    m[sl] = np.maximum(c1, c2)
    out.append((m, CANDLE_YB, (LEDGE_FRONT - CANDLE_YB) / SINP, 0.9))
    # hourglass (glass casts a lighter shadow)
    sl, X, Y = sc.win(HG_X - 200, 500, HG_X + 200, HG_YB + 70)
    m = np.zeros((sc.H, sc.W), np.float32)
    g, *_ = lathe(X, Y, HG_X, HG_YB, hg_glass_profile(), S)
    pl, *_ = lathe(X, Y, HG_X, HG_YB, hg_plate_profile(True), S)
    pb, *_ = lathe(X, Y, HG_X, HG_YB, hg_plate_profile(False), S)
    posts = np.zeros_like(g)
    for ang, _ in HG_POSTS:
        th = math.radians(ang)
        px = HG_X + HG_POST_R * math.sin(th)
        pyb = HG_YB + HG_POST_R * math.cos(th) * SINP
        cp, *_ = lathe(X, Y, px, pyb, hg_post_profile(), S)
        posts = np.maximum(posts, cp)
    m[sl] = np.maximum.reduce([g * 0.42, pl, pb, posts])
    out.append((m, HG_YB, (LEDGE_FRONT - HG_YB) / SINP, 0.92))
    # book stack: box + leaning open book (approximate silhouette)
    sl, X, Y = sc.win(BOOK["x0"] - 20, 760, BOOK["x1"] + 20, BOOK["spine_bot"] + 4)
    m = np.zeros((sc.H, sc.W), np.float32)
    u, v, _ = book_uv(X, Y)
    pages = (np.abs(u) < 1.03) & (v < 1.03)
    box = (X > BOOK["x0"]) & (X < BOOK["x1"]) & (Y > BOOK["spine_top"] - 40)
    m[sl] = (pages | box).astype(np.float32)
    out.append((m, BOOK["spine_bot"] - 30, (LEDGE_FRONT - BOOK["spine_bot"] + 30) / SINP, 0.9))
    # watch
    sl, X, Y = sc.win(1600, 1060, 1800, 1262)
    m = np.zeros((sc.H, sc.W), np.float32)
    q = ((X - WATCH["cx"]) / 80) ** 2 + ((Y - WATCH["cy"]) / 74) ** 2
    m[sl] = (q < 1).astype(np.float32)
    out.append((m, 1252.0, (LEDGE_FRONT - 1252.0) / SINP, 0.85))
    return out


def cast_shadows(sc, sils):
    """Project silhouettes along the light onto ledge top (shear) and wall (translation)."""
    S = sc.S
    lx, ly, lz = abs(float(LDIR[0])), float(LDIR[1]), float(LDIR[2])
    k1 = lx / ly / COSP
    k2 = lz * SINP / (ly * COSP)
    table = np.zeros((sc.H, sc.W), np.float32)
    wall = np.zeros((sc.H, sc.W), np.float32)
    for m, yb, zb, strength in sils:
        im = Image.fromarray(m, "F")
        ybp = yb * S
        coeffs = (1.0, k1 / k2, -k1 * ybp / k2, 0.0, 1.0 / k2, ybp - ybp / k2)
        t = np.asarray(im.transform((sc.W, sc.H), Image.AFFINE, coeffs, Image.BILINEAR), np.float32)
        table = np.maximum(table, blur(t, 3.0 * S) * strength)
        T = (WALL_ZB - zb) / lz
        dx = lx * T * S
        dy = (LEDGE_BACK - yb + ly * T * COSP) * S
        w = np.asarray(im.transform((sc.W, sc.H), Image.AFFINE, (1, 0, -dx, 0, 1, -dy), Image.BILINEAR), np.float32)
        wall = np.maximum(wall, blur(w, 22.0 * S) * strength * 0.62)
    return table, wall


def draw_background(sc, sh_table, sh_wall):
    S = sc.S
    rng = sc.rng
    sl, X, Y = sc.win(0, 0, DW, DH)
    fall = light_falloff(X, Y)
    # --- wall: rough plaster, window light falls in a diagonal band from the upper left
    mott = noise((sc.H, sc.W), 160 * S, rng, octaves=4)
    fine = noise((sc.H, sc.W), 6 * S, rng, octaves=2)
    alb = s2l([114, 101, 84]) * (1 + 0.18 * mott[..., None] + 0.04 * fine[..., None])
    beam = sstep(-220, 420, (X - 430) - 0.62 * Y)
    glow = np.exp(-(((X - 1430) / 880) ** 2 + ((Y - 820) / 620) ** 2))
    top_dark = sstep(-60, 760, Y)
    irr_w = 0.42 * beam * (0.10 + 1.05 * glow) * (0.45 + 0.55 * top_dark) * (1 - sh_wall)
    wall = alb * (SUN * irr_w[..., None] + AMB * 0.9)
    # --- ledge top: dark walnut, grain along x
    grain = noise((sc.H, sc.W), 40 * S, rng, aniso=(0.12, 6.0), octaves=4)
    rays = noise((sc.H, sc.W), 9 * S, rng, aniso=(0.25, 8.0), octaves=2)
    alb_t = s2l([104, 66, 40]) * (1 + 0.28 * grain[..., None] + 0.08 * rays[..., None])
    irr_t = 0.78 * fall * (1 - sh_table)
    # soft contact darkening where ledge meets wall
    ao_back = 0.55 + 0.45 * sstep(LEDGE_BACK, LEDGE_BACK + 40, Y)
    top = alb_t * (SUN * irr_t[..., None] + AMB) * ao_back[..., None]
    # faint sheen of the window on the polished top
    sheen = np.exp(-((Y - 1200) / 70) ** 2) * np.exp(-((X - 700) / 600) ** 2) * 0.05
    top += sheen[..., None] * np.array([0.8, 0.85, 0.9], np.float32)
    # --- bullnose front edge
    e0, e1 = LEDGE_FRONT, LEDGE_FRONT + 24
    t = np.clip((Y - e0) / (e1 - e0), 0, 1)
    ang = t * math.pi / 2
    Nb = np.stack([np.zeros_like(t), np.cos(ang), np.sin(ang)], -1)
    lam = np.clip(dot3(Nb, LDIR), 0, 1)
    spec = np.clip(dot3(Nb, HDIR), 0, 1) ** 60
    edge = alb_t * (SUN * (lam * fall)[..., None] + AMB) + (spec * fall * 0.5)[..., None] * np.array([0.9, 0.92, 0.95])
    # --- front face: darker plank with a moulding groove
    alb_f = s2l([78, 50, 32]) * (1 + 0.22 * grain[..., None])
    groove = 1 - 0.65 * np.exp(-((Y - 1352) / 4.0) ** 2) + 0.35 * np.exp(-((Y - 1345) / 2.2) ** 2)
    lowdark = 1 - 0.55 * sstep(1360, 1600, Y)
    front = alb_f * (SUN * (0.27 * fall * groove * lowdark)[..., None] + AMB * 0.5)
    img = np.where((Y < LEDGE_BACK)[..., None], wall,
                   np.where((Y < e0)[..., None], top, np.where((Y < e1)[..., None], edge, front)))
    # soften the wall/ledge junction a touch
    sc.img[sl] = img
    sc.ids[sl] = np.where(Y < LEDGE_BACK, OBJ["wall"], OBJ["ledge"])
    fl = np.where(Y < LEDGE_BACK, np.nan, 0.0).astype(np.float32)
    sc.flow[sl] = fl


# ----- candle and pewter candlestick ------------------------------------------------------
def draw_candle(sc):
    S = sc.S
    rng = sc.rng
    cx, yb = CANDLE_X, CANDLE_YB
    sl, X, Y = sc.win(cx - 170, 380, cx + 170, yb + 60)
    fall = light_falloff(X, Y)[..., None]
    # pewter candlestick
    cov, h, N, r, s = lathe(X, Y, cx, yb, candlestick_profile(), S)
    lam = np.clip(dot3(N, LDIR), 0, 1)[..., None]
    R = reflect(N)
    pew = s2l([96, 94, 90])
    col = pew * 0.62 * (SUN * lam * fall + AMB) + 0.5 * env(R, rough=0.07, window=8.0) * np.array([0.78, 0.8, 0.84]) * (0.3 + 0.7 * fall)
    tarnish = noise(X.shape, 14 * S, rng, octaves=3)
    col *= (0.85 + 0.15 * tarnish[..., None])
    sc.put(sl, cov, col, OBJ["candle"], flow=np.zeros_like(X))
    # flat tops: foot dish (h=30) and drip pan (h=386)
    for ht, rt, rin in [(30, 128, 42), (386, 90, 40)]:
        cap, q = ellipse_cap(X, Y, cx, yb, ht, rt, S)
        ring = np.sqrt(q)
        Nn = np.stack([-(X - cx) / rt * 0.25 * ring, np.ones_like(X), (Y - (yb - ht * COSP)) / (rt * SINP) * 0.12], -1)
        Nn = normalize3(Nn)
        lam2 = np.clip(dot3(Nn, LDIR), 0, 1)[..., None]
        c2 = pew * 0.45 * (SUN * lam2 * fall + AMB) + 0.35 * env(reflect(Nn), rough=0.08, window=6.0) * np.array([0.78, 0.8, 0.84])
        inner = sstep(rin / rt + 0.05, rin / rt - 0.05, ring)
        c2 = c2 * (1 - 0.45 * inner[..., None])
        sc.put(sl, cap, c2, OBJ["candle"])
    # wax candle with guttering drips
    hd, rd = candle_profile()
    dripn = noise((1, 400), 8, rng)[0]
    cov, h, N, r, s = lathe(X, Y, cx, yb, (hd, rd), S)
    theta = np.arcsin(np.clip(s, -1, 1))
    # drips: vertical runs from the rim downward; bulge the radius and the normal
    drips = np.zeros_like(X)
    for th0, length, w in [(-1.05, 168, 0.16), (-0.55, 70, 0.10), (-0.2, 130, 0.12), (0.25, 160, 0.15),
                           (0.62, 95, 0.11), (0.95, 150, 0.12), (1.25, 50, 0.09)]:
        hend = CANDLE_H1 - length
        bulb = 1 + 0.9 * np.exp(-((h - hend - 6) / 9.0) ** 2)
        prof = np.exp(-((theta - th0) / (w * bulb)) ** 2)
        run = sstep(hend - 4, hend + 8, h)
        drips = np.maximum(drips, prof * run)
    N2 = normalize3(N + np.stack([np.gradient(drips, axis=1) * 6, -np.gradient(drips, axis=0) * 6, np.zeros_like(X)], -1))
    wax = s2l([226, 212, 182])
    ndl = dot3(N2, LDIR)
    wrap = np.clip((ndl + 0.45) / 1.45, 0, 1)[..., None]
    scatter = np.clip(1 - np.abs(ndl), 0, 1)[..., None] ** 2 * np.array([0.22, 0.10, 0.04], np.float32)
    spec = (np.clip(dot3(N2, HDIR), 0, 1) ** 40)[..., None] * 0.18
    col = wax * (SUN * wrap * fall * 0.95 + AMB) + scatter * fall + spec * fall
    col *= (0.96 + 0.06 * drips[..., None])
    sc.put(sl, cov, col, OBJ["candle"], flow=np.full_like(X, math.pi / 2))
    # melted top: irregular rim, concave pool, a notch where the wax overflowed
    ey = yb - CANDLE_H1 * COSP
    ang = np.arctan2((Y - ey) / SINP, X - cx)
    rim = 33.5 * (1 + 0.05 * np.sin(3 * ang + 1.0) + 0.03 * np.sin(7 * ang))
    q = np.sqrt(((X - cx)) ** 2 + ((Y - ey) / SINP) ** 2) / rim
    capc = np.clip((1 - q) * rim * SINP * S + 0.5, 0, 1)
    pool = s2l([170, 150, 118]) * (SUN * 0.45 * fall + AMB) * (0.55 + 0.6 * sstep(0.55, 0.98, q))[..., None]
    sc.put(sl, capc, pool, OBJ["candle"], detail=capc * 0.5)
    # a stalactite of wax hanging from the drip pan, and a small irregular puddle
    pud_y = yb - 386 * COSP
    qq = ((X - cx + 16) / 46) ** 2 + ((Y - pud_y - 4) / 9) ** 2
    pud = np.clip((1 - qq) * 10 * S, 0, 1) * (Y > pud_y - 6)
    st = np.maximum(np.abs(X - (cx - 58)) - 6.5 * sstep(pud_y + 40, pud_y + 8, Y), np.maximum(pud_y + 4 - Y, Y - (pud_y + 40)))
    stc = sc.aa(st)
    pc = wax * (SUN * 0.5 * fall + AMB) * (0.85 + 0.1 * noise(X.shape, 6 * S, rng)[..., None])
    sc.put(sl, pud * 0.0, pc)
    # wick: short, bent, burnt
    t = np.linspace(0, 1, 40)
    wx = cx + 3 + 6 * t ** 1.6
    wy = ey - 4 - 30 * t
    d = np.full(X.shape, 1e9, np.float32)
    for i in range(len(t)):
        d = np.minimum(d, np.hypot(X - wx[i], Y - wy[i]))
    wick = np.clip((2.4 - d) * S + 0.5, 0, 1)
    sc.put(sl, wick, s2l([22, 18, 16]) * np.ones(3), OBJ["candle"], detail=np.ones_like(X))
    # last ember, dull and tiny: the session just timed out
    ember = np.exp(-(((X - wx[-1]) ** 2 + (Y - wy[-1]) ** 2) / 5.0))
    sc.img[sl] += (ember * 0.25)[..., None] * np.array([1.0, 0.35, 0.08], np.float32)
    return wx[-1], wy[-1]


def draw_smoke(sc, x0, y0):
    S = sc.S
    rng = sc.rng
    sl, X, Y = sc.win(x0 - 420, 40, x0 + 300, y0 + 4)
    smoke = np.zeros_like(X)
    for k, (amp, ph, wid, a0) in enumerate([(1.0, 0.0, 1.0, 0.55), (0.75, 1.9, 0.7, 0.35), (1.25, 3.7, 0.55, 0.22)]):
        rise = np.clip((y0 - Y) / (y0 - 60), 0, 1)
        cxs = (x0 - 160 * rise ** 1.3 * amp
               + 26 * amp * rise * np.sin(Y / 52 + ph)
               + 60 * amp * rise ** 2 * np.sin(Y / 115 + ph * 1.7)
               + 18 * rise ** 1.5 * np.sin(Y / 23 + ph * 3))
        w = (1.4 + 22 * rise ** 1.6 * wid)
        d = np.abs(X - cxs) / w
        a = np.exp(-d * d * 2.2) * a0 * (1 - rise) ** 0.8 * sstep(0, 0.03, rise)
        smoke = np.maximum(smoke, a)
    br = 0.6 + 0.4 * noise(X.shape, 26 * S, rng, aniso=(2.5, 0.6), octaves=2)
    smoke = np.clip(smoke * br, 0, 1)
    col = np.array([0.20, 0.215, 0.24], np.float32)
    sc.img[sl] = sc.img[sl] * (1 - smoke[..., None] * 0.75) + col * smoke[..., None]
    sc.ids[sl] = np.where(smoke > 0.18, OBJ["smoke"], sc.ids[sl])
    sc.flow[sl] = np.where(smoke > 0.06, math.pi / 2, sc.flow[sl])


# ----- hourglass --------------------------------------------------------------------------
def wood_shade(N, X, Y, fall, rng, S, base=(70, 42, 24)):
    lam = np.clip(dot3(N, LDIR), 0, 1)[..., None]
    spec = (np.clip(dot3(N, HDIR), 0, 1) ** 30)[..., None] * 0.22
    g = noise(X.shape, 10 * S, rng, aniso=(4.0, 0.3), octaves=2)
    alb = s2l(base) * (1 + 0.22 * g[..., None])
    return alb * (SUN * lam * fall + AMB) + spec * fall * np.array([0.85, 0.9, 1.0])


def draw_hourglass(sc):
    S = sc.S
    rng = sc.rng
    cx, yb = HG_X, HG_YB
    sl, X, Y = sc.win(cx - 200, 500, cx + 200, yb + 70)
    fall = light_falloff(X, Y)[..., None]
    def post(ang):
        th = math.radians(ang)
        px = cx + HG_POST_R * math.sin(th)
        pyb = yb + HG_POST_R * math.cos(th) * SINP
        cov, h, N, r, s = lathe(X, Y, px, pyb, hg_post_profile(), S)
        col = wood_shade(N, X, Y, fall, rng, S)
        sc.put(sl, cov, col, OBJ["hourglass"], flow=np.full_like(X, math.pi / 2))
    # bottom plate
    cov, h, N, r, s = lathe(X, Y, cx, yb, hg_plate_profile(False), S)
    sc.put(sl, cov, wood_shade(N, X, Y, fall, rng, S), OBJ["hourglass"], flow=np.zeros_like(X))
    cap, q = ellipse_cap(X, Y, cx, yb, 44, 160, S)
    Nc = np.broadcast_to(np.array([0, 1, 0], np.float32), X.shape + (3,))
    sc.put(sl, cap, wood_shade(Nc, X, Y, fall, rng, S) * 0.9, OBJ["hourglass"], flow=np.zeros_like(X))
    # back post (seen through glass)
    post(180.0)
    # sand (inside the glass, drawn before the glass so it is refracted and tinted)
    gp = hg_glass_profile()
    covg, hg, Ng, rg, sg = lathe(X, Y, cx, yb, gp, S)
    inner = np.clip((rg - 5 - np.abs(X - cx)) * S + 0.5, 0, 1) * covg
    dxn = np.abs(X - cx) / 108.0
    lvl_low = 140 + 70 * np.clip(1 - dxn * 1.15, 0, 1) ** 1.3       # mound in the lower bulb
    ylow = yb - lvl_low * COSP - 0 * SINP
    lowsand = inner * sstep(ylow - 1.5, ylow + 1.5, Y) * (hg < 300)
    lvl_up = 333 + 26 * np.clip(dxn * 1.4, 0, 1) ** 1.6              # a little left above, draining
    yup = yb - lvl_up * COSP
    upsand = inner * sstep(yup - 1.5, yup + 1.5, Y) * (hg > 318) * (hg < 380)
    sand_alb = s2l([196, 170, 128])
    grain = noise(X.shape, 2.0 * S, rng, octaves=1)
    slope = np.clip((X - cx) / 108.0, -1, 1)
    Ns = normalize3(np.stack([slope * 0.9, np.ones_like(X) * 0.9, np.ones_like(X) * 0.6], -1))
    Ns = np.where((np.abs(Y - ylow) < 26)[..., None] | (np.abs(Y - yup) < 18)[..., None], Ns, Ng)
    lam = np.clip(dot3(Ns, LDIR), 0, 1)[..., None]
    sand = sand_alb * (1 + 0.12 * grain[..., None]) * (SUN * lam * fall * 0.9 + AMB)
    sc.put(sl, np.maximum(lowsand, upsand), sand, OBJ["hourglass"], flow=np.zeros_like(X))
    # falling thread of sand
    thread = np.exp(-((X - cx - 0.5) / 1.3) ** 2) * (Y > yb - 316 * COSP) * (Y < yb - 208 * COSP)
    sc.put(sl, thread * 0.9, sand_alb * (SUN * 0.7 * fall + AMB) * 1.1, OBJ["hourglass"], detail=thread)
    # glass: refraction of what is behind, absorption at grazing angles, window reflections
    ndv = np.clip(dot3(Ng, VDIR), 0.02, 1)
    F = fresnel(Ng)[..., None]
    behind = sc.img[sl].copy()
    off = (-Ng[..., 0] * 9 * (1 - ndv) ** 1.5) * S
    offy = (Ng[..., 1] * 5 * (1 - ndv) ** 1.5) * S
    yy, xx = np.mgrid[0:X.shape[0], 0:X.shape[1]].astype(np.float32)
    trans = sample(behind, xx + off, yy + offy)
    tint = np.array([0.93, 0.955, 0.945], np.float32)
    absorb = tint ** (1.0 / ndv[..., None])
    refl = env(reflect(Ng), rough=0.0, window=24.0)
    Nb = normalize3(np.stack([-Ng[..., 0] * 0.9, -Ng[..., 1] * 0.9, Ng[..., 2]], -1))
    refl2 = env(reflect(Nb), rough=0.04, window=9.0) * 0.35
    glass = trans * absorb * (1 - F) + (refl * F + refl2 * 0.06) * (0.45 + 0.55 * fall)
    # rim: dark at the very edge, a thin bright line just inside on the lit side
    edge = np.clip((rg - np.abs(X - cx)), 0, 99)
    glass *= (1 - 0.55 * np.exp(-edge / 1.6))[..., None]
    rimlit = np.exp(-((edge - 4.0) / 1.6) ** 2) * (X < cx) * 0.10
    glass += rimlit[..., None] * np.array([0.9, 0.95, 1.0])
    sc.put(sl, covg, glass, OBJ["hourglass"], detail=sstep(6, 0, edge) * 0.6)
    # front posts
    post(-58.0)
    post(58.0)
    # top plate and its top face
    cov, h, N, r, s = lathe(X, Y, cx, yb, hg_plate_profile(True), S)
    sc.put(sl, cov, wood_shade(N, X, Y, fall, rng, S), OBJ["hourglass"], flow=np.zeros_like(X))
    cap, q = ellipse_cap(X, Y, cx, yb, 634, 160, S)
    sc.put(sl, cap, wood_shade(Nc, X, Y, fall, rng, S) * 1.05, OBJ["hourglass"], flow=np.zeros_like(X))


# ----- books ------------------------------------------------------------------------------
def page_curl(u):
    a = np.abs(u)
    return 44 * (1 - np.exp(-a / 0.10)) - 20 * a * a + 7 * sstep(0.86, 1.0, a)


def page_curl_d(u):
    e = 1e-3
    return (page_curl(u + e) - page_curl(u - e)) / (2 * e)


LAU = float(np.hypot(*OB_AU))
LAV = float(np.hypot(*OB_AV))
PAGE_TRUE_H = LAV / math.sin(OB_LEAN + math.asin(SINP))
N0_PAGE = np.array([0.0, math.cos(OB_LEAN), math.sin(OB_LEAN)], np.float32)
EV_PAGE = np.array([0.0, math.sin(OB_LEAN), -math.cos(OB_LEAN)], np.float32)
EX = np.array([1.0, 0.0, 0.0], np.float32)


def book_uv(X, Y):
    px = X - OB_O[0]
    py = Y - OB_O[1]
    det = OB_AU[0] * OB_AV[1] - OB_AU[1] * OB_AV[0]
    u = (px * OB_AV[1] - py * OB_AV[0]) / det
    w = (OB_AU[0] * py - OB_AU[1] * px) / det
    v = w - page_curl(u) / LAV
    return u, v, w


def book_xy(u, v):
    p = OB_O + u * OB_AU + v * OB_AV + page_curl(np.float32(u)) * OB_AV / LAV
    return float(p[0]), float(p[1])


def leather(X, rng, S, base):
    n1 = noise(X.shape, 30 * S, rng, octaves=3)
    n2 = noise(X.shape, 3 * S, rng, octaves=1)
    return s2l(base) * (1 + 0.18 * n1[..., None] + 0.06 * n2[..., None])


def metal(N, fall, tint, rough=0.02, window=16.0, diffuse=0.25, cold=0.35):
    lam = np.clip(dot3(N, LDIR), 0, 1)[..., None]
    spec_tint = np.asarray(tint, np.float32) * (1 - cold) + np.array([0.9, 0.95, 1.0], np.float32) * cold
    R = reflect(N)
    return (np.asarray(tint, np.float32) * diffuse * (SUN * lam * fall + AMB)
            + env(R, rough=rough, window=window) * spec_tint * (0.35 + 0.65 * fall))


def draw_closed_book(sc):
    S, rng = sc.S, sc.rng
    x0, x1, yt, ybt = BOOK["x0"], BOOK["x1"], BOOK["spine_top"], BOOK["spine_bot"]
    sl, X, Y = sc.win(x0 - 8, yt - 100, x1 + 8, ybt + 6)
    fall = light_falloff(X, Y)[..., None]
    # top board, seen from above (mostly covered by the open book)
    topcov = sc.aa(np.maximum.reduce([x0 + 6 - X, X - (x1 - 6), (yt - 92) - Y, Y - yt]))
    Nt = np.broadcast_to(N0_PAGE * 0 + np.array([0, 1, 0], np.float32), X.shape + (3,))
    alb = leather(X, rng, S, [74, 40, 27])
    sc.put(sl, topcov, alb * (SUN * 0.76 * fall + AMB), OBJ["book"], flow=np.zeros_like(X))
    # rounded spine with raised bands
    t = (Y - (yt + ybt) / 2) / ((ybt - yt) / 2)
    rx = np.maximum(np.maximum(x0 - X, X - x1), 0)
    sd = np.maximum(np.maximum(x0 - X, X - x1), np.abs(Y - (yt + ybt) / 2) - (ybt - yt) / 2)
    cov = sc.aa(sd)
    bxs = np.linspace(x0 + 120, x1 - 120, 5)
    bands = sum(np.exp(-((X - b) / 9.0) ** 2) for b in bxs)
    dbx = np.gradient(bands, axis=1) * S
    tt = np.clip(t, -0.98, 0.98)
    N = normalize3(np.stack([-dbx * 10, -tt * 0.85, np.sqrt(1 - 0.72 * tt * tt)], -1))
    alb = leather(X, rng, S, [86, 44, 28]) * (1 + 0.35 * bands[..., None])
    wear = sstep(0.55, 1.0, np.abs(t)) * 0.25
    alb = alb * (1 + wear[..., None])
    lam = np.clip(dot3(N, LDIR), 0, 1)[..., None]
    spec = (np.clip(dot3(N, HDIR), 0, 1) ** 18)[..., None] * 0.10
    col = alb * (SUN * lam * fall + AMB) + spec * fall
    # gilt fillets either side of each band and along the edges, worn in places
    gl = np.zeros_like(X)
    for b in bxs:
        gl = np.maximum(gl, np.exp(-((np.abs(X - b) - 17) / 1.1) ** 2))
    gl = np.maximum(gl, np.exp(-((np.abs(t) - 0.80) * (ybt - yt) / 2 / 1.1) ** 2) * (X > x0 + 20) * (X < x1 - 20))
    gl *= sstep(-0.4, 0.2, noise(X.shape, 6 * S, rng))
    gold = metal(N, fall, s2l([190, 150, 80]), rough=0.12, window=6.0, diffuse=0.5)
    col = col * (1 - gl[..., None] * 0.8) + gold * gl[..., None] * 0.8
    sc.put(sl, cov, col, OBJ["book"], flow=np.zeros_like(X))


def make_page_texture(rng, TW=700, TH=700):
    """Two pages side by side: parchment, foxing, text, and the README heading."""
    W, H = 2 * TW, TH
    base = s2l([228, 216, 190])
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    stain = noise((H, W), 60, rng, octaves=4)
    edge = np.minimum.reduce([xx, W - xx, yy, H - yy, np.abs(xx - TW) * 3])
    age = 1 - 0.18 * np.exp(-edge / 40.0)
    tex = base * ((1 + 0.06 * stain) * age)[..., None]
    for _ in range(14):
        fx, fy = rng.uniform(0, W), rng.uniform(0, H)
        r = rng.uniform(2, 7)
        spot = np.exp(-(((xx - fx) ** 2 + (yy - fy) ** 2) / (r * r)))
        tex *= 1 - spot[..., None] * np.array([0.06, 0.12, 0.22], np.float32)
    ink = np.zeros((H, W), np.float32)
    body = find_font(["Iowan Old Style.ttc", "Hoefler Text.ttc", "Georgia.ttf", "DejaVuSerif.ttf"], 21)
    head = find_font(["BigCaslon.ttf", "Baskerville.ttc", "Georgia.ttf", "DejaVuSerif.ttf"], 92)
    small = find_font(["Iowan Old Style.ttc", "Hoefler Text.ttc", "Georgia.ttf"], 24)
    left = ["Installation", "",
            "Clone the repository, then install the",
            "dependencies with the package manager",
            "named in the lockfile. Pin every version;",
            "an unpinned dependency is a promise",
            "made by a stranger.", "",
            "Configuration", "",
            "Copy the example environment file and",
            "fill in your own values. Credentials",
            "belong in the secret store, never in the",
            "repository, and never in this file.", "",
            "Rotation", "",
            "Every key here expires. Rotate on a",
            "schedule, and at once if a key is seen",
            "where it should not be. Short-lived",
            "tokens are kinder than long ones."]
    ink += text_mask(left, body, (W, H), xy=(70, 70), spacing=1.32)
    ink += text_mask(["README"], head, (W, H), xy=(TW + TW / 2, 64), align_center=True)
    ink += text_mask(["A guide for those who come after"], small, (W, H), xy=(TW + TW / 2, 182), align_center=True)
    rule = ((np.abs(yy - 226) < 1.2) & (np.abs(xx - (TW + TW / 2)) < 120)).astype(np.float32)
    ink += rule
    right = ["Quick start", "",
             "Run the tests before you ship. Sign the",
             "release, publish the checksum, and keep",
             "the signing key off every laptop.", "",
             "Secrets", "",
             "If you can read a key on this page, it",
             "is already compromised. Revoke it,",
             "rotate it, and search the history for",
             "every copy.", "",
             "Memento expirare."]
    ink += text_mask(right, body, (W, H), xy=(TW + 70, 262), spacing=1.32)
    ink = np.clip(ink, 0, 1)
    ink = blur(ink, 0.7)
    inkcol = s2l([44, 30, 22])
    tex = tex * (1 - ink[..., None] * 0.92) + inkcol * ink[..., None] * 0.92
    head_ink = np.zeros((H, W), np.float32)
    head_ink[:240] = ink[:240]
    head_ink[:, :TW] = 0
    head_mask = np.clip(blur(head_ink, 4.0) * 4, 0, 1)
    body_mask = np.clip(blur(ink, 4.0) * 3, 0, 1) * 0.45
    return tex.astype(np.float32), np.maximum(head_mask, body_mask)


def draw_open_book(sc):
    S, rng = sc.S, sc.rng
    sl, X, Y = sc.win(OB_O[0] - 460, 760, OB_O[0] + 470, OB_O[1] + 26)
    fall = light_falloff(X, Y)[..., None]
    u, v, w = book_uv(X, Y)
    tau0 = 11.0
    curl = page_curl(u)
    # cover boards: flat leather, slightly larger than the page block
    bu = 1.035
    sd_b = np.maximum((np.abs(u) - bu) * LAU, np.maximum((-(tau0 + 8) / LAV - w) * LAV, (w - 1.035) * LAV))
    covb = sc.aa(sd_b)
    front_face = w < -tau0 / LAV
    alb = leather(X, rng, S, [80, 42, 28])
    Nf = np.where(front_face[..., None], np.array([0, -0.2, 0.98], np.float32), N0_PAGE)
    lam = np.clip(dot3(Nf, LDIR), 0, 1)[..., None]
    sc.put(sl, covb, alb * (SUN * lam * fall + AMB), OBJ["book"], flow=np.zeros_like(X))
    # page block front edge: from board up to the curled bottom page
    f = (w * LAV + tau0) / (curl + tau0)
    sd_e = np.maximum((np.abs(u) - 1.0) * LAU, np.maximum(-(w * LAV + tau0), w * LAV - curl))
    cove = sc.aa(sd_e)
    stripes = 0.86 + 0.14 * np.sin(f * 70 + 2 * noise(X.shape, 20 * S, rng))
    ecol = s2l([214, 198, 164]) * stripes[..., None]
    Ne = normalize3(np.stack([-page_curl_d(u) / LAU * 0.5, 0.15 + 0 * u, np.ones_like(u)], -1))
    lam = np.clip(dot3(Ne, LDIR), 0, 1)[..., None]
    gut = 0.55 + 0.45 * sstep(0, 0.08, np.abs(u))
    ecol = ecol * (SUN * lam * fall + AMB) * gut[..., None]
    sc.put(sl, cove, ecol, OBJ["book"], flow=np.zeros_like(X))
    # pages
    tex, head_mask = make_page_texture(rng)
    TH, TW2 = tex.shape[:2]
    tx = (u + 1) / 2 * (TW2 - 1)
    ty = (1 - v) * (TH - 1)
    paper = sample(tex, tx, ty)
    hm = sample(head_mask, tx, ty)
    dh = page_curl_d(u) / LAU
    N = normalize3(N0_PAGE[None, None, :] - dh[..., None] * EX[None, None, :] * 0.9)
    lam = np.clip(dot3(N, LDIR), 0, 1)[..., None]
    gutter = (0.42 + 0.58 * sstep(0.0, 0.16, np.abs(u)))[..., None]
    col = paper * (SUN * lam * fall + AMB) * gutter
    sd_p = np.maximum((np.abs(u) - 1.0) * LAU, np.maximum(-v * LAV, (v - 1.0) * LAV))
    covp = sc.aa(sd_p)
    flow = np.zeros_like(X)
    sc.put(sl, covp, col, OBJ["book"], detail=hm, flow=flow)
    sc._page_win = (sl, covp)


KEY = dict(u0=0.50, v0=0.30, beta=math.radians(-20.0))


def key_local(X, Y):
    u, v, w = book_uv(X, Y)
    pu = (u - KEY["u0"]) * LAU
    pv = (v - KEY["v0"]) * PAGE_TRUE_H
    cb, sb = math.cos(KEY["beta"]), math.sin(KEY["beta"])
    a = pu * cb + pv * sb
    b = -pu * sb + pv * cb
    return a, b


def key_xy(a, b):
    cb, sb = math.cos(KEY["beta"]), math.sin(KEY["beta"])
    pu = a * cb - b * sb
    pv = a * sb + b * cb
    return book_xy(KEY["u0"] + pu / LAU, KEY["v0"] + pv / PAGE_TRUE_H)


def key_sdf(a, b):
    """Signed distance + height of the key in its own frame (true px)."""
    def cap(a, b, a0, a1, r):
        q = np.clip(a, a0, a1)
        d = np.hypot(a - q, b)
        return d - r, r
    parts = []
    parts.append(cap(a, b, -118, 40, 6.5))
    parts.append((np.hypot((a - 46) / 6.5, b / 9.5) * 6.5 - 6.5, 8.0))
    ac, rc = 84.0, 28.0
    phi = np.arctan2(b, a - ac)
    rho = np.hypot(a - ac, b)
    ring_r = rc * (1 + 0.08 * np.cos(3 * phi))
    parts.append((np.abs(rho - ring_r) - 7.0, 7.0))
    bit = np.maximum(np.abs(a + 97) - 15, np.abs(b + 22) - 17)
    for (na, nb, wa, wb) in [(-103, -30, 2.6, 9), (-91, -33, 2.6, 6), (-97, -12, 9, 2.2)]:
        bit = np.maximum(bit, -np.maximum(np.abs(a - na) - wa, np.abs(b - nb) - wb))
    parts.append((bit, 4.5))
    sd = np.minimum.reduce([p[0] for p in parts])
    hgt = np.zeros_like(a)
    for d, r in parts:
        if r == 4.5:
            hh = np.minimum(4.5, np.maximum(-d, 0) * 1.3)
        else:
            hh = np.sqrt(np.maximum(0, -d * (2 * r + d)))
        hgt = np.maximum(hgt, hh)
    return sd, hgt


def draw_key_and_tag(sc):
    S, rng = sc.S, sc.rng
    # --- key lying on the right-hand page
    pts = [key_xy(a, b) for a, b in [(-125, -45), (-125, 45), (120, -45), (120, 45)]]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    sl, X, Y = sc.win(min(xs) - 20, min(ys) - 20, max(xs) + 30, max(ys) + 30)
    fall = light_falloff(X, Y)[..., None]
    a, b = key_local(X, Y)
    sd, hgt = key_sdf(a, b)
    cov = sc.aa(sd * 0.85)
    # shadow on the page
    sh = np.zeros_like(cov)
    off = int(round(6 * S)), int(round(6 * S))
    sh[off[1]:, off[0]:] = cov[:-off[1] or None, :-off[0] or None]
    sh = blur(sh, 2.5 * S)
    sc.img[sl] *= (1 - 0.55 * sh)[..., None]
    gy, gx = np.gradient(hgt * S)
    N = normalize3(N0_PAGE[None, None, :] - gx[..., None] * EX * 1.0 + (gy * 0.7)[..., None] * EV_PAGE)
    brass = s2l([222, 172, 80])
    col = metal(N, fall, brass, rough=0.02, window=22.0, diffuse=0.5, cold=0.45)
    crev = sstep(0.0, 2.5, hgt)[..., None]
    col *= (0.55 + 0.45 * crev)
    tarn = noise(X.shape, 5 * S, rng, octaves=2)
    col *= (0.9 + 0.1 * tarn[..., None])
    sc.put(sl, cov, col, OBJ["key"], detail=np.ones_like(X))
    # --- string from the bow, over the edge of the page block, down to the tag
    bx, by = key_xy(84 + 20, -20)
    ex_, ey_ = book_xy(0.84, -0.02)
    tg = TAG
    th = math.radians(tg["rot"])
    eyx = tg["cx"] + (-(tg["h"] / 2 - 15)) * -math.sin(th)
    eyy = tg["cy"] - (tg["h"] / 2 - 15) * math.cos(th)
    P = np.array([[bx, by], [ex_ + 6, ey_ - 6], [ex_ - 14, ey_ + 16], [eyx, eyy]], np.float32)
    tt = np.linspace(0, 1, 160)[:, None]
    curve = ((1 - tt) ** 3 * P[0] + 3 * (1 - tt) ** 2 * tt * P[1] + 3 * (1 - tt) * tt ** 2 * P[2] + tt ** 3 * P[3])
    sl2, X2, Y2 = sc.win(min(curve[:, 0]) - 8, min(curve[:, 1]) - 8, max(curve[:, 0]) + 8, max(curve[:, 1]) + 8)
    d = np.full(X2.shape, 1e9, np.float32)
    for cxy in curve:
        d = np.minimum(d, np.hypot(X2 - cxy[0], Y2 - cxy[1]))
    scov = np.clip((1.5 - d) * S + 0.5, 0, 1)
    shade = 0.75 + 0.25 * np.clip(1 - d / 1.5, 0, 1)
    twine = s2l([206, 192, 158]) * (SUN * 0.65 + AMB) * shade[..., None]
    # --- tag hanging in front of the closed book
    sl3, X3, Y3 = sc.win(tg["cx"] - 140, tg["cy"] - 80, tg["cx"] + 150, tg["cy"] + 80)
    fall3 = light_falloff(X3, Y3)[..., None]
    dx, dy = X3 - tg["cx"], Y3 - tg["cy"]
    lx = dx * math.cos(th) + dy * math.sin(th)
    ly = -dx * math.sin(th) + dy * math.cos(th)
    hw, hh = tg["w"] / 2, tg["h"] / 2
    sdt = np.maximum(np.abs(lx) - hw, np.abs(ly) - hh)
    sdt = np.maximum(sdt, (np.abs(lx) * 0.7071 + (-ly) * 0.7071) - (hw + hh - 22) * 0.7071)
    sdt = np.maximum(sdt, -(np.hypot(lx, ly + hh - 15) - 4.6))
    covt = sc.aa(sdt)
    # its shadow on the leather spine
    sh = np.zeros_like(covt)
    o = int(round(10 * S)), int(round(8 * S))
    sh[o[1]:, o[0]:] = covt[:-o[1], :-o[0]]
    sc.img[sl3] *= (1 - 0.6 * blur(sh, 4 * S))[..., None]
    sc.put(sl2, scov, twine, OBJ["tag"], detail=scov)
    nx = (lx / hw) * 0.20 - 0.18
    ny = 0.32 - 0.08 * (ly / hh)
    Nt = normalize3(np.stack([nx, ny, np.ones_like(nx) * 0.92], -1))
    lam = np.clip(dot3(Nt, LDIR), 0, 1)[..., None]
    fib = noise(X3.shape, 1.6 * S, rng, aniso=(1.0, 3.0), octaves=2)
    mott = noise(X3.shape, 18 * S, rng, octaves=2)
    paper = s2l([238, 82, 36]) * (1 + 0.07 * fib[..., None] + 0.10 * mott[..., None])
    # a soft vertical fold and worn, paler edges
    fold = np.exp(-((lx - 38) / 3.0) ** 2) * 0.10 - np.exp(-((lx - 42) / 4.0) ** 2) * 0.12
    paper = paper * (1 + fold[..., None])
    wear = sstep(5.0, 0.0, -sdt) * (0.5 + 0.5 * noise(X3.shape, 2.0 * S, rng))
    paper = paper * (1 - wear[..., None] * 0.35) + s2l([240, 170, 130]) * wear[..., None] * 0.35
    # reinforcing ring around the eyelet
    ring = sstep(12.5, 11.0, np.hypot(lx, ly + hh - 15)) * sstep(4.0, 5.5, np.hypot(lx, ly + hh - 15))
    paper = paper * (1 - ring[..., None]) + s2l([236, 150, 108]) * ring[..., None]
    # the leaked key, written by hand
    font = find_font(["Bradley Hand Bold.ttf", "Noteworthy.ttc", "MarkerFelt.ttc", "Georgia Italic.ttf"], 106)
    TWt, THt = int(tg["w"] * 4), int(tg["h"] * 4)
    # "AKIA", an ellipsis of three round dots (painted as separate dabs so none gets lost), "EXAMPLE"
    im = Image.new("L", (TWt, THt), 0)
    dr = ImageDraw.Draw(im)
    wa, wb = dr.textlength("AKIA", font=font), dr.textlength("EXAMPLE", font=font)
    dot_r, gap = 7.5, 26.0
    total = wa + wb + gap * 4
    x0 = (TWt - total) / 2
    ty0 = THt * 0.40
    dr.text((x0, ty0), "AKIA", fill=255, font=font)
    base_y = ty0 + font.getbbox("A")[3] - dot_r - 1
    for k in range(3):
        cxd = x0 + wa + gap * (k + 0.9)
        dr.ellipse([cxd - dot_r, base_y - dot_r, cxd + dot_r, base_y + dot_r], fill=255)
    dr.text((x0 + wa + gap * 4, ty0), "EXAMPLE", fill=255, font=font)
    m = np.asarray(im, np.float32) / 255.0
    ink = sample(blur(m, 1.2), (lx + hw) * 4, (ly + hh) * 4)
    ink *= (0.85 + 0.15 * noise(X3.shape, 3 * S, rng))
    paper = paper * (1 - ink[..., None] * 0.93) + s2l([38, 16, 12]) * ink[..., None] * 0.93
    col = paper * (SUN * lam * fall3 * 1.05 + AMB)
    inkd = np.clip(blur(ink, 2.0 * S) * 4, 0, 1)
    edge_band = sstep(5.0, 1.0, np.abs(sdt)) * 0.45
    sc.put(sl3, covt, col, OBJ["tag"], detail=np.maximum(np.maximum(inkd, edge_band), 0.12))
    sc.detail[sl3] = np.maximum(sc.detail[sl3], edge_band)
    sc.tag_box = (tg["cx"] - hw, tg["cy"] - hh, tg["cx"] + hw, tg["cy"] + hh)


# ----- letter with a wax seal -------------------------------------------------------------
def draw_letter(sc):
    """A letter patent: a parchment roll on the ledge, its sheet hanging over the edge,
    a blue wax seal hanging from it on silk ribbons."""
    S, rng = sc.S, sc.rng
    sl, X, Y = sc.win(270, 1225, 640, 1500)
    fall = light_falloff(X, Y)[..., None]
    parch = s2l([222, 208, 178])
    # --- hanging sheet (drawn first; the roll sits on top of its upper end)
    xl = np.interp(Y, [1270, 1290, 1312, 1398], [338, 334, 333, 326])
    xr = np.interp(Y, [1270, 1290, 1312, 1404], [552, 556, 557, 563])
    ybot = np.interp(X, [326, 563], [1398, 1404]) + 1.5 * np.sin(X / 19.0)
    deckle = 0.8 * noise(X.shape, 2.5 * S, rng)
    sd = np.maximum.reduce([xl - X, X - xr, Y - ybot, 1268 - Y]) + deckle
    cov = sc.aa(sd)
    tb = np.clip((Y - LEDGE_FRONT) / 22.0, 0, 1)
    ang = tb * math.pi / 2
    wav = 0.10 * np.sin((X - 330) / 38.0)                      # the sheet is not quite flat
    curl = sstep(1378, 1402, Y) * 0.55                         # bottom edge curls toward us
    N = np.stack([wav, np.cos(ang) - 0.06 * tb + curl, np.sin(ang)], -1)
    crease = (Y > 1314) * (np.exp(-((Y - 1350) / 2.0) ** 2) * 0.10 - np.exp(-((Y - 1354) / 2.5) ** 2) * 0.12)
    N = normalize3(N + np.stack([np.zeros_like(X), crease * 3, np.zeros_like(X)], -1))
    lam = np.clip(dot3(N, LDIR), 0, 1)[..., None]
    alb = parch * (1 + 0.06 * noise(X.shape, 22 * S, rng, octaves=3)[..., None])
    edge_age = sstep(8, 0, -sd)[..., None] * 0.18
    alb = alb * (1 - edge_age)
    font = find_font(["Apple Chancery.ttf", "Zapfino.ttf", "Georgia Italic.ttf"], 56)
    TWl, THl = 1000, 480
    m = text_mask(["Release 1.0, signed", "and sealed for all", "who come after."], font, (TWl, THl), xy=(30, 20), spacing=1.0)
    ink = sample(blur(m, 1.0), (X - 342) * 4.2, (Y - 1316) * 4.2) * (Y > 1314) * (Y < 1392)
    alb = alb * (1 - ink[..., None] * 0.9) + s2l([58, 34, 20]) * ink[..., None] * 0.9
    col = alb * (SUN * lam * fall + AMB)
    shm = np.zeros_like(cov)
    o = int(round(8 * S)), int(round(9 * S))
    shm[o[1]:, o[0]:] = (cov * (Y > 1314))[:-o[1], :-o[0]]
    sc.img[sl] *= (1 - 0.55 * blur(shm, 5 * S) * (Y > 1312))[..., None]
    inkd = np.clip(blur(ink, 1.5 * S) * 3, 0, 1)
    sc.put(sl, cov, col, OBJ["letter"], flow=np.zeros_like(X), detail=inkd * 0.8)
    # --- the roll: a horizontal cylinder of parchment lying on the ledge
    ax0, ay0, ax1, ay1, rr = 300.0, 1262.0, 596.0, 1257.0, 21.0
    t_ax = np.clip((X - ax0) / (ax1 - ax0), 0, 1)
    acy = ay0 + (ay1 - ay0) * t_ax
    tt = (Y - acy) / rr
    sdr = np.maximum(np.abs(Y - acy) - rr, np.maximum(ax0 + 4 - X, X - ax1))
    covr = sc.aa(sdr)
    tcl = np.clip(tt, -0.99, 0.99)
    Nr = normalize3(np.stack([np.zeros_like(X), -tcl, np.sqrt(1 - tcl * tcl)], -1))
    lam = np.clip(dot3(Nr, LDIR), 0, 1)[..., None]
    spec = (np.clip(dot3(Nr, HDIR), 0, 1) ** 24)[..., None] * 0.08
    layers = 0.94 + 0.06 * np.sin((Y - acy) * 0.0 + X * 0.0)
    rcol = parch * (1 + 0.05 * noise(X.shape, 18 * S, rng, aniso=(0.4, 3.0), octaves=2)[..., None]) * (SUN * lam * fall + AMB) + spec * fall
    rcol *= (0.8 + 0.2 * np.sqrt(1 - tcl * tcl))[..., None]
    sc.put(sl, covr, rcol, OBJ["letter"], flow=np.zeros_like(X))
    # left end of the roll: a narrow ellipse showing the spiral of the rolled sheet
    ex_ = ax0 + 4
    q = np.hypot((X - ex_) / 7.0, (Y - ay0) / rr)
    cove = sc.aa((q - 1) * 7.0)
    spiral = 0.75 + 0.25 * np.sin(q * 22 + np.arctan2(Y - ay0, (X - ex_) * 3) * 0.5)
    ecol = parch * (SUN * 0.30 * fall + AMB) * spiral[..., None]
    ecol *= (1 - 0.6 * sstep(0.35, 0.0, q))[..., None]
    sc.put(sl, cove, ecol, OBJ["letter"], detail=cove * 0.5)
    # --- silk ribbons and the pendant seal
    sx, sy = 446.0, 1446.0
    for (x0r, x1r, wv) in [(436, 438, -1), (456, 452, 1)]:
        tt2 = np.clip((Y - 1396) / (sy - 1396), 0, 1)
        cxr = x0r + (x1r - x0r) * tt2 + wv * 2.5 * np.sin(tt2 * 4)
        sdr2 = np.maximum(np.abs(X - cxr) - 4.5, np.maximum(1394 - Y, Y - sy))
        covr2 = sc.aa(sdr2)
        tw = 0.75 + 0.25 * np.sin(tt2 * 7 + wv)
        rc = s2l([70, 92, 132]) * (SUN * 0.4 * fall * tw[..., None] + AMB)
        sc.put(sl, covr2, rc, OBJ["letter"], detail=covr2 * 0.5)
    for (x1r, y1r, wv) in [(434, 1490, -1), (462, 1494, 1)]:
        tt2 = np.clip((Y - sy) / (y1r - sy), 0, 1)
        cxr = sx + (x1r - sx) * tt2 + wv * 3 * np.sin(tt2 * 5)
        sdr2 = np.maximum(np.abs(X - cxr) - 4.5, np.maximum(sy - Y, Y - y1r))
        sdr2 = np.maximum(sdr2, (Y - y1r) + np.abs(X - cxr) * 0.8 - 2)
        covr2 = sc.aa(sdr2)
        tw = 0.75 + 0.25 * np.sin(tt2 * 9 + wv)
        rc = s2l([70, 92, 132]) * (SUN * 0.36 * fall * tw[..., None] + AMB)
        sc.put(sl, covr2, rc, OBJ["letter"], detail=covr2 * 0.5)
    dx, dy = X - sx, Y - sy
    rho = np.hypot(dx, dy)
    phi = np.arctan2(dy, dx)
    nphi = np.interp(phi, np.linspace(-math.pi, math.pi, 64), rng.standard_normal(64) * 0.5)
    edge_r = 30 * (1 + 0.05 * np.sin(5 * phi + 1) + 0.035 * nphi)
    sds = rho - edge_r
    covs = sc.aa(sds)
    shs = np.zeros_like(covs)
    o = int(round(9 * S)), int(round(8 * S))
    shs[o[1]:, o[0]:] = covs[:-o[1], :-o[0]]
    sc.img[sl] *= (1 - 0.55 * blur(shs, 4 * S))[..., None]
    hgt = np.clip(-sds / 7.0, 0, 1) ** 0.6 * 5
    hgt -= 1.6 * sstep(21.5, 19.5, rho)
    hgt += 1.1 * np.exp(-((rho - 18.0) / 1.3) ** 2)
    fs = find_font(["BigCaslon.ttf", "Baskerville.ttc", "Georgia.ttf"], 160)
    gm = text_mask(["S"], fs, (200, 200), xy=(100, 8), align_center=True)
    glyph = sample(blur(gm, 3.0), dx * 5.4 + 100, dy * 5.4 + 100)
    hgt += glyph * 1.4 * (rho < 18.5)
    gy, gx = np.gradient(hgt * S)
    Ns = normalize3(np.stack([-gx, gy, np.ones_like(gx)], -1))
    lam = np.clip(dot3(Ns, LDIR), 0, 1)[..., None]
    wax = s2l([30, 50, 98])
    R = reflect(Ns)
    scol = wax * (SUN * lam * fall + AMB) + env(R, rough=0.03, window=10.0) * 0.06 * fall
    scol += (np.clip(dot3(Ns, HDIR), 0, 1) ** 40)[..., None] * 0.6 * np.array([0.85, 0.92, 1.0])
    scol *= (0.75 + 0.5 * np.clip(dot3(Ns, LDIR), 0, 1))[..., None]
    sc.put(sl, covs, scol, OBJ["letter"], detail=covs)


# ----- pocket watch -----------------------------------------------------------------------
N0_W = nrm([0.0, math.sin(math.radians(25)), math.cos(math.radians(25))])
EY_W = nrm([0.0, math.cos(math.radians(25)), -math.sin(math.radians(25))])


def dial_texture(size=640):
    """Enamel dial: Roman numerals set radially, minute track, seconds sub-dial."""
    im = Image.new("L", (size, size), 0)
    dr = ImageDraw.Draw(im)
    c = size / 2
    R = size / 2
    for k in range(60):
        a = math.radians(k * 6)
        r0 = R * (0.86 if k % 5 else 0.82)
        w = 2 if k % 5 else 4
        dr.line([(c + R * 0.92 * math.sin(a), c - R * 0.92 * math.cos(a)),
                 (c + r0 * math.sin(a), c - r0 * math.cos(a))], fill=255, width=w)
    dr.ellipse([c - R * 0.93, c - R * 0.93, c + R * 0.93, c + R * 0.93], outline=255, width=3)
    dr.ellipse([c - R * 0.86, c - R * 0.86, c + R * 0.86, c + R * 0.86], outline=255, width=2)
    font = find_font(["BigCaslon.ttf", "Baskerville.ttc", "Georgia.ttf"], int(size * 0.105))
    numer = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
    for k, s in enumerate(numer):
        a = math.radians(k * 30)
        tile = Image.new("L", (int(size * 0.3), int(size * 0.16)), 0)
        td = ImageDraw.Draw(tile)
        tw = td.textlength(s, font=font)
        td.text(((tile.width - tw) / 2, 0), s, fill=255, font=font)
        rot = tile.rotate(-k * 30, resample=Image.BICUBIC, expand=True)
        r = R * 0.66
        px = c + r * math.sin(a) - rot.width / 2
        py = c - r * math.cos(a) - rot.height / 2 + size * 0.02
        im.paste(255, (int(px), int(py)), rot)
    # seconds sub-dial at six
    sx, sy, sr = c, c + R * 0.40, R * 0.15
    dr.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], outline=255, width=2)
    for k in range(12):
        a = math.radians(k * 30)
        dr.line([(sx + sr * math.sin(a), sy - sr * math.cos(a)), (sx + sr * 0.8 * math.sin(a), sy - sr * 0.8 * math.cos(a))], fill=255, width=2)
    return np.asarray(im, np.float32) / 255.0


def draw_watch(sc):
    S, rng = sc.S, sc.rng
    cx, cy, r = WATCH["cx"], WATCH["cy"], WATCH["r"]
    gold = s2l([214, 172, 96])
    # open hunter lid standing behind, concave gold interior facing us
    lcx, lcy = cx + 40, cy - 70
    sl, X, Y = sc.win(cx - 130, cy - 160, cx + 130, cy + 100)
    fall = light_falloff(X, Y)[..., None]
    dx, dy = (X - lcx) / 74, (Y - lcy) / 70
    q = np.hypot(dx, dy)
    covl = sc.aa((q - 1) * 70)
    Nl = normalize3(np.stack([-dx * 0.45, dy * 0.45 + 0.1, np.ones_like(dx)], -1))
    rim = sstep(0.90, 0.97, q)
    Nl = normalize3(Nl + np.stack([dx, -dy, np.zeros_like(dx)], -1) * rim[..., None] * 1.5)
    lidc = metal(Nl, fall, gold, rough=0.10, window=7.0, diffuse=0.45, cold=0.3)
    engr = 0.9 + 0.1 * np.sin(q * 60)
    lidc *= engr[..., None] * 0.8
    sc.put(sl, covl, lidc, OBJ["watch"])
    # bow and pendant at twelve
    for (ox, oy, rx, ry, wdt) in [(0, -96, 13, 10, 3.4)]:
        qq = np.hypot((X - cx - ox) / rx, (Y - cy - oy) / ry)
        sdb = np.abs(qq - 1) * min(rx, ry) - wdt
        covb = sc.aa(sdb)
        tb = np.clip((qq - 1) * min(rx, ry) / wdt, -1, 1)
        Nb = normalize3(np.stack([(X - cx - ox) / rx * tb, -(Y - cy - oy) / ry * tb, np.sqrt(1 - tb * tb) + 0.2], -1))
        sc.put(sl, covb, metal(Nb, fall, gold, rough=0.02, window=14.0), OBJ["watch"], detail=covb)
    sdp = np.maximum(np.abs(X - cx) - 7, np.abs(Y - (cy - 79)) - 9)
    covp = sc.aa(sdp)
    kn = 0.85 + 0.15 * np.sin(X * 3.0)
    Np = normalize3(np.stack([(X - cx) / 7, np.zeros_like(X), np.ones_like(X)], -1))
    sc.put(sl, covp, metal(Np, fall, gold, rough=0.03, window=12.0) * kn[..., None], OBJ["watch"], detail=covp)
    # case ring (torus) + bezel
    dx, dy = X - cx, Y - cy
    rho = np.hypot(dx, dy / 0.97)
    covc = sc.aa(rho - (r + 10))
    tt = np.clip((rho - (r + 5)) / 5.0, -1, 1)
    radial = np.stack([dx / np.maximum(rho, 1e-3), -dy / np.maximum(rho, 1e-3), np.zeros_like(dx)], -1)
    radial = radial[..., 0:1] * EX + radial[..., 1:2] * EY_W
    Nc = normalize3(N0_W * np.sqrt(1 - tt * tt)[..., None] + radial * tt[..., None])
    cc = metal(Nc, fall, gold, rough=0.02, window=16.0, diffuse=0.3)
    sc.put(sl, covc, cc, OBJ["watch"], detail=np.ones_like(X) * 0.6)
    # dial
    covd = sc.aa(rho - r)
    dt = dial_texture()
    ds = dt.shape[0]
    ux = dx / r * (ds / 2) + ds / 2
    uy = dy / (r * 0.97) * (ds / 2) + ds / 2
    marks = sample(blur(dt, 0.8), ux, uy)
    enamel = s2l([236, 228, 208]) * (1 + 0.03 * noise(X.shape, 12 * S, rng)[..., None])
    Nd = normalize3(N0_W + (dx / r)[..., None] * EX * 0.12 - (dy / r)[..., None] * EY_W * 0.12)
    lam = np.clip(dot3(Nd, LDIR), 0, 1)[..., None]
    dcol = enamel * (1 - marks[..., None] * 0.9) + s2l([30, 26, 24]) * marks[..., None] * 0.9
    dcol = dcol * (SUN * lam * fall + AMB)
    # hands at 11:58, blued steel: two minutes to expiry
    def hand(angle_deg, length, width, tail):
        a = math.radians(angle_deg)
        ax, ay = math.sin(a), -math.cos(a)
        along = dx * ax + (dy / 0.97) * ay
        across = -dx * ay + (dy / 0.97) * ax
        wprof = width * (1 - 0.6 * np.clip(along / length, 0, 1))
        sdh = np.maximum(np.abs(across) - wprof, np.maximum(-tail - along, along - length))
        return sdh
    sdm = hand(348, 56, 2.0, 10)
    sdhh = hand(-1.0, 34, 3.4, 8)
    spade = np.hypot(dx - 34 * math.sin(math.radians(-1)) * 0.82, dy + 34 * 0.82) - 6
    sdhh = np.minimum(sdhh, np.maximum(spade, -(np.hypot(dx - 34 * math.sin(math.radians(-1)) * 0.82, dy + 34 * 0.82) - 2.6)))
    hc = np.minimum(np.minimum(sdm, sdhh), np.hypot(dx, dy) - 4.2)
    covh = sc.aa(hc)
    blued = metal(normalize3(N0_W + (dx / 60)[..., None] * EX * 0.3), fall, s2l([40, 60, 140]), rough=0.05, window=5.0, diffuse=0.4, cold=0.6)
    dcol = dcol * (1 - covh[..., None]) + blued * covh[..., None]
    # seconds hand on the sub-dial
    sdsx = hand(200, 11, 0.9, 3)
    # crystal: domed glass with the window caught in it
    Ng = normalize3(N0_W + (dx / r)[..., None] * EX * 0.45 - (dy / r)[..., None] * EY_W * 0.45)
    crys = env(reflect(Ng), rough=0.0, window=20.0) * fresnel(Ng, 0.05)[..., None]
    dcol = dcol + crys * (0.5 + 0.5 * fall)
    md = np.clip(blur(np.maximum(marks, covh), 2.0 * S) * 4, 0, 1)
    sc.put(sl, covd, dcol, OBJ["watch"], detail=np.maximum(md, 0.3))
    sc.watch_box = (cx - r - 10, cy - r - 40, cx + r + 10, cy + r + 10)


def draw_chain(sc):
    S, rng = sc.S, sc.rng
    cx, cy = WATCH["cx"], WATCH["cy"]
    P = np.array([[cx - 4, cy - 104], [cx - 60, cy - 98], [cx - 105, cy - 40], [cx - 108, cy + 40],
                  [cx - 92, cy + 92], [cx - 30, cy + 108], [cx + 60, cy + 104], [cx + 130, cy + 96],
                  [cx + 160, cy + 84]], np.float32)
    # Catmull-Rom densify
    pts = []
    for i in range(len(P) - 1):
        p0 = P[max(i - 1, 0)]
        p1, p2 = P[i], P[i + 1]
        p3 = P[min(i + 2, len(P) - 1)]
        for t in np.linspace(0, 1, 30, endpoint=False):
            pts.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    pts = np.array(pts)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    sacc = np.concatenate([[0], np.cumsum(seg)])
    L = sacc[-1]
    step = 6.4
    ss = np.arange(0, L, step)
    lx = np.interp(ss, sacc, pts[:, 0])
    ly = np.interp(ss, sacc, pts[:, 1])
    sl, X, Y = sc.win(lx.min() - 12, ly.min() - 12, lx.max() + 20, ly.max() + 14)
    fall = light_falloff(X, Y)[..., None]
    gold = s2l([214, 172, 96])
    # shadow of the chain where it lies on the ledge
    for i in range(len(ss)):
        x, y = lx[i], ly[i]
        j = min(i + 1, len(ss) - 1)
        k = max(i - 1, 0)
        tx, ty = lx[j] - lx[k], ly[j] - ly[k]
        tn = math.hypot(tx, ty) or 1
        tx, ty = tx / tn, ty / tn
        a = (X - x) * tx + (Y - y) * ty
        b = -(X - x) * ty + (Y - y) * tx
        if i % 2 == 0:
            q = np.hypot(a / 4.6, b / 3.4)
            sd = np.abs(q - 1) * 3.4 - 1.3
            t = np.clip((q - 1) * 3.4 / 1.3, -1, 1)
            N = normalize3(np.stack([a / 4.6 * t * 0.8, -b / 3.4 * t * 0.8, np.sqrt(1 - t * t) + 0.3], -1))
        else:
            sd = np.maximum(np.abs(a) - 4.4, np.abs(b) - 1.3)
            t = np.clip(b / 1.3, -1, 1)
            N = normalize3(np.stack([np.zeros_like(t) - t * ty * 0.9, -t * tx * 0.9 + 0 * t, np.sqrt(1 - t * t) + 0.3], -1))
        cov = sc.aa(sd)
        if not cov.any():
            continue
        if y > LEDGE_BACK + 100:
            shd = blur(np.roll(np.roll(cov, int(3 * S), 1), int(2 * S), 0), 1.5 * S)
            sc.img[sl] *= (1 - 0.35 * shd)[..., None]
        sc.put(sl, cov, metal(N, fall, gold, rough=0.03, window=14.0, diffuse=0.35), OBJ["watch"], detail=cov)


# ----- wilting tulip ----------------------------------------------------------------------
def petal(sc, X, Y, B, T, W, fall, rng, inside=False, wither=0.3, flame_seed=0, alpha=1.0):
    B = np.asarray(B, np.float32)
    T = np.asarray(T, np.float32)
    axis = T - B
    Lp = float(np.hypot(*axis))
    ax = axis / Lp
    dx, dy = X - B[0], Y - B[1]
    s = (dx * ax[0] + dy * ax[1]) / Lp
    t = (-dx * ax[1] + dy * ax[0])
    sc_ = np.clip(s, 0, 1)
    width = W * np.sqrt(np.clip(np.sin(np.pi * sc_ ** 0.8), 0, 1)) * (1 - 0.45 * sstep(0.7, 1.0, sc_)) + 1e-3
    tn = t / width
    sd = np.maximum((np.abs(tn) - 1) * width, np.maximum(-s * Lp, (s - 1) * Lp))
    cov = sc.aa(sd) * alpha
    tt = np.clip(tn, -0.99, 0.99)
    bulge = np.sqrt(1 - tt * tt)
    nx_l = tt * (0.9 if not inside else -0.6)
    N = normalize3(np.stack([nx_l * -ax[1] + (0.3 - 0.6 * s) * ax[0] * 0.5,
                             -(nx_l * ax[0]) + 0.35 + 0 * s, bulge * 0.9 + 0.2], -1))
    ndl = dot3(N, LDIR)
    wrap = np.clip((ndl + 0.6) / 1.6, 0, 1)[..., None]
    rng2 = np.random.default_rng(flame_seed)
    fl = np.zeros_like(X)
    for k in range(7):
        c0 = rng2.uniform(-0.8, 0.8)
        f = np.exp(-((tn - c0 - 0.12 * np.sin(s * 9 + k)) / rng2.uniform(0.04, 0.12)) ** 2)
        fl = np.maximum(fl, f * sstep(0.05, 0.4, s) * sstep(1.0, 0.55, s + rng2.uniform(-0.2, 0.2)))
    base = s2l([234, 222, 226])
    flame = s2l([96, 30, 84])
    alb = base * (1 - fl[..., None] * 0.85) + flame * fl[..., None] * 0.85
    if inside:
        blotch = sstep(0.28, 0.05, s)
        alb = alb * (1 - blotch[..., None]) + s2l([40, 28, 48]) * blotch[..., None]
    wit = sstep(1 - wither, 1.1, np.maximum(np.abs(tn), s)) * (0.6 + 0.4 * noise(X.shape, 6 * sc.S, rng))
    alb = alb * (1 - wit[..., None]) + s2l([150, 112, 78]) * wit[..., None]
    scatter = (np.clip(1 - np.abs(ndl), 0, 1) ** 2)[..., None] * np.array([0.10, 0.04, 0.08], np.float32)
    col = alb * (SUN * wrap * fall + AMB) + scatter * fall
    col *= (0.75 + 0.25 * bulge[..., None])
    return cov, col


def draw_tulip(sc):
    S, rng = sc.S, sc.rng
    sl, X, Y = sc.win(1850, 1080, DW, 1300)
    fall = light_falloff(X, Y)[..., None]
    def tube(P, r0, r1, col_base, wither_from=1.0):
        pts = np.array(P, np.float32)
        tt = np.linspace(0, 1, 120)[:, None]
        n = len(pts) - 1
        # quadratic/cubic Bezier through control points
        cur = np.zeros((120, 2), np.float32)
        for i, p in enumerate(pts):
            cur += math.comb(n, i) * (1 - tt) ** (n - i) * tt ** i * p
        d = np.full(X.shape, 1e9, np.float32)
        ti = np.zeros(X.shape, np.float32)
        for i, c in enumerate(cur):
            di = np.hypot(X - c[0], Y - c[1])
            m = di < d
            d = np.where(m, di, d)
            ti = np.where(m, i / 119, ti)
        rr = r0 + (r1 - r0) * ti
        cov = sc.aa(d - rr)
        tcy = np.clip(d / rr, 0, 0.99)
        # light side: normal toward up-left using signed side estimate
        gy, gx = np.gradient(d)
        side = np.sign(-gy - gx * 0.3)
        N = normalize3(np.stack([-side * tcy * 0.5, side * tcy * 0.8, np.sqrt(1 - tcy * tcy)], -1))
        lam = np.clip(dot3(N, LDIR) + 0.2, 0, 1)[..., None]
        alb = s2l(col_base) * np.ones_like(X)[..., None]
        brown = sstep(wither_from, 1.0, ti)[..., None]
        alb = alb * (1 - brown) + s2l([120, 96, 60]) * brown
        return cov, alb * (SUN * lam * fall + AMB) * (0.8 + 0.2 * np.sqrt(1 - tcy * tcy))[..., None]
    # leaf lying on the ledge, curling, its tip gone yellow
    Lb, Lt = np.array([2330.0, 1176.0]), np.array([2180.0, 1262.0])
    cov, col = petal(sc, X, Y, Lb, Lt, 30, fall, rng, wither=0.45, flame_seed=99)
    leafc = col * 0 + s2l([92, 106, 64]) * (SUN * 0.7 * fall + AMB)
    ax = (Lt - Lb) / np.hypot(*(Lt - Lb))
    s = ((X - Lb[0]) * ax[0] + (Y - Lb[1]) * ax[1]) / np.hypot(*(Lt - Lb))
    t = (-(X - Lb[0]) * ax[1] + (Y - Lb[1]) * ax[0])
    vein = np.exp(-(t / 1.2) ** 2) * 0.25
    lshade = (0.75 + 0.25 * np.tanh(-t / 8))[..., None]
    yel = sstep(0.6, 1.0, s)[..., None]
    leafc = leafc * lshade * (1 + vein[..., None]) * (1 - yel) + s2l([150, 130, 70]) * (SUN * 0.6 * fall + AMB) * yel
    # shadow under the leaf and flower on the ledge
    sh = np.zeros_like(X)
    sh = np.maximum(sh, np.exp(-(((X - 2080) / 90) ** 2 + ((Y - 1238) / 16) ** 2)) * 0.7)
    sh = np.maximum(sh, np.exp(-(((X - 2250) / 140) ** 2 + ((Y - 1222) / 10) ** 2)) * 0.5)
    sc.img[sl] *= (1 - 0.5 * sh)[..., None]
    sc.put(sl, cov, leafc, OBJ["tulip"])
    # stem
    cov, col = tube([[2112, 1206], [2190, 1188], [2300, 1196], [2440, 1160]], 7.0, 8.5, [98, 110, 62], wither_from=0.0 + 2)
    sc.put(sl, cov, col, OBJ["tulip"])
    # petals: back ones show their inside, front ones their outside
    # receptacle where stem meets flower
    q = np.hypot((X - 2146) / 13, (Y - 1206) / 11)
    sc.put(sl, sc.aa((q - 1) * 11), s2l([96, 108, 60]) * (SUN * 0.55 * fall + AMB), OBJ["tulip"])
    order = [
        dict(B=(2134, 1200), T=(1996, 1166), W=46, inside=True, wither=0.35, seed=1),
    ]
    for p in order:
        cov, col = petal(sc, X, Y, p["B"], p["T"], p["W"], fall, rng, inside=p["inside"], wither=p["wither"], flame_seed=p["seed"])
        sc.put(sl, cov, col * 0.42, OBJ["tulip"], detail=cov * 0.15)
    # stamens: six dark anthers in the open cup
    for k in range(6):
        ax0, ay0 = 2110, 1203
        ang = math.radians(180 + (k - 2.5) * 11)
        L = 62 + 8 * math.sin(k * 2.1)
        ex, ey = ax0 + L * math.cos(ang), ay0 + L * math.sin(ang) * 0.7
        tt = np.clip(((X - ax0) * (ex - ax0) + (Y - ay0) * (ey - ay0)) / (L * L), 0, 1)
        d = np.hypot(X - (ax0 + tt * (ex - ax0)), Y - (ay0 + tt * (ey - ay0)))
        sc.put(sl, sc.aa(d - 1.2), s2l([150, 140, 100]) * (SUN * 0.4 * fall + AMB), OBJ["tulip"], detail=np.ones_like(X))
        da = np.hypot((X - ex) / 2.4, (Y - ey) / 5.0) - 1
        sc.put(sl, sc.aa(da * 2.4), s2l([24, 20, 26]) * np.ones(3), OBJ["tulip"], detail=np.ones_like(X))
    front = [
        dict(B=(2138, 1213), T=(2010, 1262), W=40, wither=0.55, seed=4),
        dict(B=(2138, 1197), T=(2004, 1150), W=44, wither=0.35, seed=3),
        dict(B=(2142, 1206), T=(2026, 1214), W=38, wither=0.3, seed=5),
    ]
    for p in front:
        cov, col = petal(sc, X, Y, p["B"], p["T"], p["W"], fall, rng, inside=False, wither=p["wither"], flame_seed=p["seed"])
        shp = np.zeros_like(cov)
        o = max(1, int(round(3 * S)))
        shp[o:, o:] = cov[:-o, :-o]
        sc.img[sl] *= (1 - 0.6 * blur(shp, 3 * S) * (1 - cov) * (sc.ids[sl] == OBJ["tulip"]))[..., None]
        sc.put(sl, cov, col, OBJ["tulip"], detail=cov * 0.15)
    # fallen petal on the ledge, curled and browning
    sl2, X2, Y2 = sc.win(1860, 1235, 2000, 1295)
    fall2 = light_falloff(X2, Y2)[..., None]
    sh = np.exp(-(((X2 - 1935) / 40) ** 2 + ((Y2 - 1278) / 7) ** 2))
    sc.img[sl2] *= (1 - 0.45 * sh)[..., None]
    cov, col = petal(sc, X2, Y2, (1972, 1262), (1890, 1280), 20, fall2, rng, inside=True, wither=0.6, flame_seed=7)
    sc.put(sl2, cov, col * 0.95, OBJ["tulip"], detail=cov * 0.15)
    sc.tulip_box = (1985, 1125, 2160, 1265)


# ----- the fly ----------------------------------------------------------------------------
FLY = dict(x=1196.0, y=1271.0, ang=math.radians(196), sq=0.62, scale=1.6)


def draw_fly(sc):
    S, rng = sc.S, sc.rng
    fx, fy = FLY["x"], FLY["y"]
    sl, X, Y = sc.win(fx - 50, fy - 34, fx + 50, fy + 30)
    fall = light_falloff(X, Y)[..., None]
    # local frame: x forward (toward the head), y to the fly's left
    dx, dy = (X - fx) / FLY["scale"], (Y - fy) / FLY["sq"] / FLY["scale"]
    ca, sa = math.cos(FLY["ang"]), math.sin(FLY["ang"])
    lx = dx * ca + dy * sa
    ly = -dx * sa + dy * ca
    # soft shadow
    sh = np.exp(-(((X - fx - 9) / 22) ** 2 + ((Y - fy + 1) / 7) ** 2))
    sc.img[sl] *= (1 - 0.55 * sh)[..., None]
    # legs: thin dark jointed lines down to the ledge
    legs = [((5, 3), (12, 10), (17, 13)), ((5, -3), (12, -10), (17, -12)),
            ((2, 4), (2, 13), (-1, 17)), ((2, -4), (2, -13), (-2, -16)),
            ((-1, 3), (-9, 11), (-17, 14)), ((-1, -3), (-9, -11), (-17, -13))]
    legd = np.full(X.shape, 1e9, np.float32)
    for pts in legs:
        for (a0, b0), (a1, b1) in zip(pts[:-1], pts[1:]):
            t = np.clip(((lx - a0) * (a1 - a0) + (ly - b0) * (b1 - b0)) / ((a1 - a0) ** 2 + (b1 - b0) ** 2), 0, 1)
            legd = np.minimum(legd, np.hypot(lx - (a0 + t * (a1 - a0)), ly - (b0 + t * (b1 - b0))))
    sc.put(sl, sc.aa(legd * FLY["sq"] * FLY["scale"] - 0.7), s2l([20, 18, 18]) * np.ones(3), OBJ["fly"], detail=np.ones_like(X))
    def blob(cx_, cy_, rx, ry):
        q = np.hypot((lx - cx_) / rx, (ly - cy_) / ry)
        cov = sc.aa((q - 1) * min(rx, ry) * FLY["sq"] * FLY["scale"])
        z = np.sqrt(np.clip(1 - q * q, 0, 1))
        nxl, nyl = (lx - cx_) / rx, (ly - cy_) / ry
        # back to screen orientation
        nsx = nxl * ca - nyl * sa
        nsy = nxl * sa + nyl * ca
        N = normalize3(np.stack([nsx * 0.8, -nsy * 0.5 + z * 0.5, z * 0.8 + 0.1], -1))
        return cov, N, z
    # abdomen: dark metallic blue-green
    cov, N, z = blob(-9, 0, 10.5, 8.0)
    lam = np.clip(dot3(N, LDIR), 0, 1)[..., None]
    seg = 0.85 + 0.15 * np.cos(lx * 1.1)
    col = s2l([34, 58, 54]) * (SUN * lam * fall + AMB) * seg[..., None] + env(reflect(N), rough=0.05, window=8.0) * 0.06
    sc.put(sl, cov, col, OBJ["fly"], detail=np.ones_like(X))
    # thorax with darker stripes
    cov, N, z = blob(4, 0, 7.5, 7.0)
    lam = np.clip(dot3(N, LDIR), 0, 1)[..., None]
    stripes = 1 - 0.35 * (np.abs(np.sin(ly * 0.9)) > 0.6)
    col = s2l([70, 68, 64]) * stripes[..., None] * (SUN * lam * fall + AMB) + env(reflect(N), rough=0.06, window=6.0) * 0.04
    sc.put(sl, cov, col, OBJ["fly"], detail=np.ones_like(X))
    # head and the big red eyes
    cov, N, z = blob(13, 0, 4.5, 6.5)
    lam = np.clip(dot3(N, LDIR), 0, 1)[..., None]
    sc.put(sl, cov, s2l([46, 40, 36]) * (SUN * lam * fall + AMB), OBJ["fly"], detail=np.ones_like(X))
    for side in (1, -1):
        cov, N, z = blob(14, side * 4.2, 4.0, 3.8)
        lam = np.clip(dot3(N, LDIR), 0, 1)[..., None]
        col = s2l([120, 34, 26]) * (SUN * lam * fall + AMB) + (np.clip(dot3(N, HDIR), 0, 1) ** 80)[..., None] * 0.9
        sc.put(sl, cov, col, OBJ["fly"], detail=np.ones_like(X))
    # wings: smoky, translucent, with veins and a thin-film sheen
    for side in (1, -1):
        wa = math.radians(18 * side)
        cwx, cwy = -9.0, 7.0 * side
        ux = (lx - cwx) * math.cos(wa) + (ly - cwy) * math.sin(wa)
        uy = -(lx - cwx) * math.sin(wa) + (ly - cwy) * math.cos(wa)
        q = np.hypot(ux / 13.5, uy / 5.2)
        cov = sc.aa((q - 1) * 5.2 * FLY["sq"] * FLY["scale"]) * 0.42
        vein = np.maximum(np.exp(-((uy - 0.25 * ux * 0.3) / 0.35) ** 2), np.exp(-((uy + 2.4 - 0.1 * ux) / 0.3) ** 2)) * (q < 1)
        film = 0.5 + 0.5 * np.sin(ux * 0.7 + uy * 1.3)
        wc = (s2l([150, 150, 160]) * (SUN * 0.5 * fall + AMB) + np.stack([film * 0.03, (1 - film) * 0.04, film * 0.05], -1))
        sc.put(sl, cov, wc, OBJ["fly"], detail=np.ones_like(X))
        sc.put(sl, vein * 0.5 * (q < 1), s2l([30, 26, 24]) * np.ones(3))
    # glints on the abdomen and thorax: the window, very small
    for (gx_, gy_) in [(-7, 3.5), (5, 3)]:
        g = np.exp(-(((lx - gx_) ** 2 + (ly - gy_) ** 2) / 1.2))
        sc.img[sl] += (g * 0.35)[..., None] * np.array([0.85, 0.92, 1.0], np.float32)


def contact_ao(sc):
    """Soft occlusion where objects touch the ledge."""
    sl, X, Y = sc.win(0, LEDGE_BACK, DW, LEDGE_FRONT + 4)
    ao = np.zeros_like(X)
    for (x0, x1, y, h, k) in [(BOOK["x0"] - 10, BOOK["x1"] + 10, BOOK["spine_bot"], 8, 0.75),
                              (CANDLE_X - 150, CANDLE_X + 150, CANDLE_YB + 154 * SINP * 0.0, 30, 0.0),
                              (HG_X - 180, HG_X + 180, HG_YB + 182 * SINP, 7, 0.7),
                              (WATCH["cx"] - 70, WATCH["cx"] + 70, WATCH["cy"] + WATCH["r"] + 9, 5, 0.7)]:
        if k <= 0:
            continue
        m = sstep(x0 - 10, x0 + 30, X) * sstep(x1 + 10, x1 - 30, X) * np.exp(-np.maximum(Y - y, 0) / h) * (Y > y - 30)
        ao = np.maximum(ao, m * k)
    # candle foot ellipse
    q = ((X - CANDLE_X) / 160) ** 2 + ((Y - CANDLE_YB) / (160 * SINP)) ** 2
    ao = np.maximum(ao, np.exp(-np.maximum(q - 1, 0) * 6) * (q > 0.8) * 0.6)
    q = ((X - HG_X) / 186) ** 2 + ((Y - HG_YB) / (186 * SINP)) ** 2
    ao = np.maximum(ao, np.exp(-np.maximum(q - 1, 0) * 6) * (q > 0.8) * 0.6)
    sc.img[sl] *= (1 - 0.6 * ao)[..., None]


def build_scene(scale, seed):
    t0 = time.time()
    sc = Scene(scale, seed)
    sils = silhouette_masks(sc)
    sh_t, sh_w = cast_shadows(sc, sils)
    draw_background(sc, sh_t, sh_w)
    contact_ao(sc)
    wx, wy = draw_candle(sc)
    draw_smoke(sc, wx, wy)
    draw_hourglass(sc)
    draw_letter(sc)
    draw_closed_book(sc)
    draw_open_book(sc)
    draw_key_and_tag(sc)
    draw_chain(sc)
    draw_watch(sc)
    draw_tulip(sc)
    draw_fly(sc)
    sc.img = np.clip(sc.img, 0, 4).astype(np.float32)
    print(f"scene built in {time.time() - t0:.1f}s ({sc.W}x{sc.H})", flush=True)
    return sc



# ========================================================================================
# 2. PAINTING: Hertzmann-style layered strokes with bristles, K/S mixing and impasto
# ========================================================================================
def ks(R):
    R = np.clip(R, 0.002, 0.998)
    return (1 - R) ** 2 / (2 * R)


def r_from_ks(k):
    return 1 + k - np.sqrt(k * k + 2 * k)


def km_mix(c1, c2, t):
    """Per-channel Kubelka-Munk mix of two opaque paints (linear reflectances)."""
    t = t[..., None] if np.ndim(t) == np.ndim(c1) - 1 else t
    return r_from_ks(ks(c1) * (1 - t) + ks(c2) * t).astype(np.float32)


def luma(c):
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def make_bristles(rng, K=8, TS=1024, TV=128):
    """Bristle textures: each row of the texture is one bristle's paint streak along the stroke."""
    out = []
    for _ in range(K):
        gain = rng.normal(0, 1, (TV, 1)).astype(np.float32)
        gain = blur(np.repeat(gain, 4, 1), 0.6)[:, :1]
        along = rng.normal(0, 1, (TV, TS // 48)).astype(np.float32)
        along = resize_f(along, TS, TV, Image.BICUBIC)
        fine = rng.normal(0, 1, (TV, TS // 6)).astype(np.float32)
        fine = resize_f(fine, TS, TV, Image.BILINEAR)
        t = 0.9 * gain + 0.55 * along + 0.25 * fine
        t = blur(t, 0.5)
        out.append((0.5 + 0.5 * np.tanh(1.3 * t)).astype(np.float32))
    return np.stack(out)


def chaikin(P, it=2):
    for _ in range(it):
        if len(P) < 3:
            break
        Q = 0.75 * P[:-1] + 0.25 * P[1:]
        Rr = 0.25 * P[:-1] + 0.75 * P[1:]
        P = np.vstack([P[:1], np.stack([Q, Rr], 1).reshape(-1, 2), P[-1:]])
    return P


def tangent_field(lum, sigma_g, sigma_t, hint, force=None):
    """Stroke direction = perpendicular to the smoothed gradient (structure tensor).
    Where the image is flat, fall back to the scene hint or a slow noise field."""
    g = blur(lum, sigma_g)
    gy, gx = np.gradient(g)
    jxx = blur(gx * gx, sigma_t)
    jxy = blur(gx * gy, sigma_t)
    jyy = blur(gy * gy, sigma_t)
    tr = jxx + jyy
    disc = np.sqrt((jxx - jyy) ** 2 + 4 * jxy * jxy)
    coh = disc / (tr + 1e-9)
    mag = np.sqrt(tr)
    # doubled-angle representation of the edge tangent
    c2 = -(jxx - jyy) / (disc + 1e-12)
    s2 = -2 * jxy / (disc + 1e-12)
    w = np.clip(coh * sstep(0.0005, 0.004, mag), 0, 1)
    if force is not None:
        w = w * (1 - force * (1 - sstep(0.02, 0.08, mag)))
    hc = np.cos(2 * hint)
    hs = np.sin(2 * hint)
    C = w * c2 + (1 - w) * hc
    Sx = w * s2 + (1 - w) * hs
    ang = 0.5 * np.arctan2(Sx, C)
    return np.cos(ang).astype(np.float32), np.sin(ang).astype(np.float32), mag


class Painter:
    def __init__(self, ref, detail, hint, S, seed, snap=None, force=None):
        self.ref = ref.astype(np.float32)
        self.H, self.W = ref.shape[:2]
        self.S = S
        self.rng = np.random.default_rng(seed + 7)
        self.detail = detail
        self.hint = hint
        self.force = force
        ground = s2l([150, 118, 84])
        nz = noise((self.H, self.W), 90 * S, self.rng, octaves=3)
        self.col = (ground * (1 + 0.06 * nz[..., None])).astype(np.float32)
        self.hgt = np.zeros((self.H, self.W), np.float32)
        self.wet = np.zeros((self.H, self.W), np.float32)
        self.tex = make_bristles(self.rng)
        self.snap = snap
        self.count = 0

    # -------------------------------------------------------------------------------------
    def stroke(self, pts, R, color, opacity=0.96, dry=0.35, thick=1.0, pick=(0.08, 0.38),
               cj=0.10, bristle_px=None):
        rng = self.rng
        P = np.asarray(pts, np.float32)
        if len(P) == 1:
            P = np.vstack([P, P + np.array([R * 0.6, 0.0], np.float32)])
        P = chaikin(P, 2)
        d = np.diff(P, axis=0)
        seg = np.hypot(d[:, 0], d[:, 1])
        keep = np.concatenate([[True], seg > 1e-3])
        P = P[keep]
        if len(P) < 2:
            return
        d = np.diff(P, axis=0)
        seg = np.hypot(d[:, 0], d[:, 1])
        sacc = np.concatenate([[0.0], np.cumsum(seg)]).astype(np.float32)
        L = float(sacc[-1])
        q = max(1.0, R / 22.0)
        ds = 0.62 * q
        small = float(np.clip((4.0 - R) / 2.5, 0, 1))          # fine sable brushes: crisp, opaque
        c0, c1 = (0.85 - 0.45 * small) * R, (0.9 - 0.45 * small) * R
        s = np.arange(-c0, L + c1, ds, dtype=np.float32)
        sc_ = np.clip(s, 0, L)
        cx = np.interp(sc_, sacc, P[:, 0])
        cy = np.interp(sc_, sacc, P[:, 1])
        tx = np.interp(sc_, sacc[1:] - seg / 2, d[:, 0] / seg) if len(seg) > 1 else np.full_like(s, d[0, 0] / seg[0])
        ty = np.interp(sc_, sacc[1:] - seg / 2, d[:, 1] / seg) if len(seg) > 1 else np.full_like(s, d[0, 1] / seg[0])
        tn = np.hypot(tx, ty) + 1e-6
        tx, ty = tx / tn, ty / tn
        ext = s - sc_
        cx = cx + ext * tx
        cy = cy + ext * ty
        nx, ny = -ty, tx
        v = np.arange(-R - 1.0, R + 1.0 + 1e-3, ds, dtype=np.float32)
        PX = cx[:, None] + v[None, :] * nx[:, None]
        PY = cy[:, None] + v[None, :] * ny[:, None]
        # half-width: round start, tapered tail
        u0 = np.clip(-s / c0, 0, 1)
        u1 = np.clip((s - L) / c1, 0, 1)
        wS = R * np.sqrt(1 - u0 * u0) * (1 - u1 ** 1.4)
        tid = rng.integers(0, self.tex.shape[0])
        TS, TV = self.tex.shape[1], self.tex.shape[2]
        bpx = bristle_px or float(np.clip(R / 11.0, 0.85, 4.0))
        spx = max(1.0, R / 7.0)
        tvi = (((v + R) / bpx).astype(np.int32) + rng.integers(0, TV)) % TV
        tsi = (((s + c0) / spx).astype(np.int32) + rng.integers(0, TS)) % TS
        T = self.tex[tid][tsi[:, None], tvi[None, :]]
        av = np.abs(v)[None, :]
        feather = max(0.7, 0.14 * R) * (1 - small) + 0.4 * small
        a_edge = sstep(wS[:, None] + 0.3 + 0.3 * small, wS[:, None] - feather, av + (T - 0.5) * feather * 1.6 * (1 - small))
        sn = np.clip(s / max(L, 1e-3), 0, 1)
        th = 0.10 - 0.25 * small + dry * sn ** 1.7
        a = a_edge * sstep(th[:, None] - 0.16, th[:, None] + 0.16, T) * opacity
        film = float(np.clip(R / (10.0 * self.S), 0.12, 1.0))   # small brushes lay thin paint
        tk = a * (0.3 + 0.7 * T) * thick * film * (1 + 0.55 * sstep(0.55, 0.98, av / R)) * (1 - 0.4 * sn[:, None])
        jit = (T - 0.5) * cj
        # forward splat (bilinear) into a patch, optionally at reduced resolution
        x0 = int(math.floor(PX.min())) - 2
        y0 = int(math.floor(PY.min())) - 2
        pw = int(math.ceil((PX.max() - x0) / q)) + 3
        ph = int(math.ceil((PY.max() - y0) / q)) + 3
        fx = ((PX - x0) / q).ravel()
        fy = ((PY - y0) / q).ravel()
        ix = fx.astype(np.int32)
        iy = fy.astype(np.int32)
        wx = fx - ix
        wy = fy - iy
        base = iy * pw + ix
        idx = np.concatenate([base, base + 1, base + pw, base + pw + 1])
        wts = np.concatenate([(1 - wx) * (1 - wy), wx * (1 - wy), (1 - wx) * wy, wx * wy])
        n = pw * ph
        af = np.tile(a.ravel(), 4) * wts
        wsum = np.bincount(idx, wts, n)
        asum = np.bincount(idx, af, n)
        tsum = np.bincount(idx, np.tile(tk.ravel(), 4) * wts, n)
        jsum = np.bincount(idx, np.tile(jit.ravel(), 4) * af, n)
        ssum = np.bincount(idx, np.tile(np.broadcast_to(sn[:, None], a.shape).ravel(), 4) * af, n)
        dens = 1.0 / (ds / q) ** 2
        cov = np.clip(wsum / (0.45 * dens), 0, 1)
        inv = 1.0 / np.maximum(wsum, 1e-6)
        A = (asum * inv * cov).reshape(ph, pw)
        Tk = (tsum * inv * cov).reshape(ph, pw)
        ia = 1.0 / np.maximum(asum, 1e-6)
        J = (jsum * ia).reshape(ph, pw)
        SN = (ssum * ia).reshape(ph, pw)
        if q > 1:
            W2, H2 = int(round(pw * q)), int(round(ph * q))
            A = resize_f(A.astype(np.float32), W2, H2)
            Tk = resize_f(Tk.astype(np.float32), W2, H2)
            J = resize_f(J.astype(np.float32), W2, H2)
            SN = resize_f(SN.astype(np.float32), W2, H2)
        ph2, pw2 = A.shape
        # clip to canvas
        X0, Y0 = max(0, x0), max(0, y0)
        X1, Y1 = min(self.W, x0 + pw2), min(self.H, y0 + ph2)
        if X1 <= X0 or Y1 <= Y0:
            return
        sy = slice(Y0 - y0, Y1 - y0)
        sx = slice(X0 - x0, X1 - x0)
        A = A[sy, sx].astype(np.float32)
        Tk = Tk[sy, sx].astype(np.float32)
        J = J[sy, sx].astype(np.float32)
        SN = SN[sy, sx].astype(np.float32)
        win = (slice(Y0, Y1), slice(X0, X1))
        under = self.col[win]
        wet = self.wet[win]
        brush = np.clip(color[None, None, :] * (1 + J[..., None]), 0.0005, 0.999)
        m = wet * (pick[0] + pick[1] * SN)
        dep = km_mix(brush, under, m)
        A3 = A[..., None]
        self.col[win] = under * (1 - A3) + dep * A3
        self.hgt[win] = self.hgt[win] * (1 - 0.55 * A) + Tk
        self.wet[win] = np.maximum(wet, A)
        self.count += 1

    # -------------------------------------------------------------------------------------
    def trace(self, starts, R, refb, tanx, tany, max_len, min_len, fc, rough=0.0):
        """Trace all strokes of a layer in parallel (Hertzmann: stop when colour diverges)."""
        rng = self.rng
        N = len(starts)
        P = np.zeros((N, max_len + 1, 2), np.float32)
        P[:, 0] = starts
        col = sample(refb, starts[:, 0], starts[:, 1])
        alive = np.ones(N, bool)
        nlen = np.ones(N, np.int32)
        dprev = np.zeros((N, 2), np.float32)
        sign0 = np.where(rng.random(N) < 0.5, -1.0, 1.0).astype(np.float32)
        for k in range(1, max_len + 1):
            x, y = P[:, k - 1, 0], P[:, k - 1, 1]
            tx = sample(tanx, x, y)
            ty = sample(tany, x, y)
            if rough > 0:
                a = rng.normal(0, rough, N).astype(np.float32)
                tx, ty = tx * np.cos(a) - ty * np.sin(a), tx * np.sin(a) + ty * np.cos(a)
            if k == 1:
                tx, ty = tx * sign0, ty * sign0
            else:
                flip = tx * dprev[:, 0] + ty * dprev[:, 1] < 0
                tx = np.where(flip, -tx, tx)
                ty = np.where(flip, -ty, ty)
                tx = fc * tx + (1 - fc) * dprev[:, 0]
                ty = fc * ty + (1 - fc) * dprev[:, 1]
            nn = np.hypot(tx, ty) + 1e-6
            tx, ty = tx / nn, ty / nn
            nxp = x + R * tx
            nyp = y + R * ty
            out = (nxp < 0) | (nyp < 0) | (nxp >= self.W - 1) | (nyp >= self.H - 1)
            rc = sample(refb, nxp, nyp)
            cc = sample(self.col_g_ref, nxp, nyp)
            d_canvas = np.linalg.norm(l2s(rc) - cc, axis=1)
            d_stroke = np.linalg.norm(l2s(rc) - l2s(col), axis=1)
            stop = out | ((k > min_len) & (d_canvas < d_stroke)) | (d_stroke > self.diverge)
            go = alive & ~out
            P[go, k, 0] = nxp[go]
            P[go, k, 1] = nyp[go]
            nlen[go] += 1
            alive &= ~stop
            dprev = np.stack([tx, ty], 1)
            if not alive.any():
                break
        return P, nlen, col

    # -------------------------------------------------------------------------------------
    def layer(self, R_design, T, max_len, min_len=2, fc=0.8, fs=0.5, fg=1.0, detail_only=False,
              dry=0.3, thick=1.0, opacity=0.96, jitter=0.038, rough=0.08, frames=0, label="",
              det_min=0.2, pick=(0.08, 0.38), diverge=9.0):
        S = self.S
        R = R_design * S
        t0 = time.time()
        refb = blur(self.ref, fs * R)
        refg = l2s(refb)
        self.col_g_ref = l2s(self.col)
        diff = np.linalg.norm(refg - self.col_g_ref, axis=2)
        g = max(2, int(round(fg * R)))
        Hc, Wc = self.H // g, self.W // g
        D = diff[:Hc * g, :Wc * g].reshape(Hc, g, Wc, g).transpose(0, 2, 1, 3).reshape(Hc, Wc, g * g)
        err = D.mean(axis=2)
        am = D.argmax(axis=2)
        det = self.detail[:Hc * g, :Wc * g].reshape(Hc, g, Wc, g).mean(axis=(1, 3))
        Teff = T * (1 - 0.65 * det)
        sel = err > Teff
        if detail_only:
            sel &= det > det_min
        cy, cx = np.nonzero(sel)
        oy, ox = am[cy, cx] // g, am[cy, cx] % g
        starts = np.stack([cx * g + ox, cy * g + oy], 1).astype(np.float32)
        starts += self.rng.uniform(-0.5, 0.5, starts.shape).astype(np.float32) * g * 0.5
        starts[:, 0] = np.clip(starts[:, 0], 0, self.W - 2)
        starts[:, 1] = np.clip(starts[:, 1], 0, self.H - 2)
        tanx, tany, _ = tangent_field(luma(refg), max(1.0, R * 0.5), max(2.0, R * 1.2), self.hint, self.force)
        self.diverge = diverge
        P, nlen, col = self.trace(starts, R, refb, tanx, tany, max_len, min_len, fc, rough)
        # colour jitter: value, a little hue, cooler lights and warmer darks
        N = len(starts)
        lum = luma(col)[:, None]
        val = 1 + self.rng.normal(0, jitter, (N, 1)).astype(np.float32)
        hue = 1 + self.rng.normal(0, jitter * 0.5, (N, 3)).astype(np.float32)
        temp = np.where(lum > 0.25, np.array([[0.985, 1.0, 1.02]]), np.array([[1.02, 1.0, 0.975]])).astype(np.float32)
        col = np.clip(col * val * hue * temp, 0.0005, 0.999).astype(np.float32)
        order = self.rng.permutation(N)
        thick_c = thick * (0.5 + 0.6 * np.clip(lum[:, 0] * 1.6, 0, 1))
        print(f"  layer {label or R_design}: R={R:.1f}px strokes={N} trace={time.time() - t0:.1f}s", flush=True)
        t1 = time.time()
        fr_marks = set()
        if frames and self.snap:
            fr_marks = {int(round(N * (f + 1) / frames)) for f in range(frames)}
        for i, j in enumerate(order):
            self.stroke(P[j, :nlen[j]], R, col[j], opacity=opacity, dry=dry, thick=thick_c[j], pick=pick)
            if (i + 1) in fr_marks:
                self.snap(self)
        if frames and self.snap and N == 0:
            for _ in range(frames):
                self.snap(self)
        self.wet *= 0.35
        print(f"    painted in {time.time() - t1:.1f}s", flush=True)
        return N

    def underdrawing(self, frames=0):
        """Brush drawing in thinned umber along the strongest edges, as a painter would start."""
        S = self.S
        refg = l2s(blur(self.ref, 2.5 * S))
        lum = luma(refg)
        tanx, tany, mag = tangent_field(lum, 2.0 * S, 5.0 * S, self.hint)
        g = int(round(16 * S))
        Hc, Wc = self.H // g, self.W // g
        M = mag[:Hc * g, :Wc * g].reshape(Hc, g, Wc, g).transpose(0, 2, 1, 3).reshape(Hc, Wc, g * g)
        mx = M.max(axis=2)
        am = M.argmax(axis=2)
        thr = np.percentile(mx, 70)
        cy, cx = np.nonzero(mx > thr)
        starts = np.stack([cx * g + am[cy, cx] % g, cy * g + am[cy, cx] // g], 1).astype(np.float32)
        self.col_g_ref = l2s(self.col)
        self.diverge = 9.0
        R = 2.7 * S
        P, nlen, _ = self.trace(starts, 4.0 * S, blur(self.ref, 2 * S), tanx, tany, 7, 7, 0.9)
        umber = s2l([58, 36, 22])
        order = self.rng.permutation(len(starts))
        fr = {int(round(len(order) * (f + 1) / frames)) for f in range(frames)} if frames else set()
        for i, j in enumerate(order):
            self.stroke(P[j, :nlen[j]], R, umber * self.rng.uniform(0.85, 1.15), opacity=0.8, dry=0.5, thick=0.25, pick=(0, 0))
            if (i + 1) in fr and self.snap:
                self.snap(self)
        self.wet *= 0.0
        print(f"  underdrawing: {len(order)} strokes", flush=True)

    def highlights(self, frames=0):
        """Lead-white impasto: short loaded dabs on the brightest local maxima."""
        S = self.S
        lumr = luma(self.ref)
        g = int(round(10 * S))
        Hc, Wc = self.H // g, self.W // g
        M = lumr[:Hc * g, :Wc * g].reshape(Hc, g, Wc, g).transpose(0, 2, 1, 3).reshape(Hc, Wc, g * g)
        mx = M.max(axis=2)
        am = M.argmax(axis=2)
        cy, cx = np.nonzero(mx > 0.62)
        starts = np.stack([cx * g + am[cy, cx] % g, cy * g + am[cy, cx] // g], 1).astype(np.float32)
        refb = blur(self.ref, 1.0 * S)
        tanx, tany, _ = tangent_field(luma(l2s(refb)), 1.5 * S, 3.0 * S, self.hint)
        self.col_g_ref = l2s(self.col)
        self.diverge = 0.25
        P, nlen, col = self.trace(starts, 3.0 * S, refb, tanx, tany, 3, 1, 0.9)
        order = self.rng.permutation(len(starts))
        fr = {int(round(len(order) * (f + 1) / frames)) for f in range(frames)} if frames else set()
        for i, j in enumerate(order):
            c = np.clip(col[j] * 1.06, 0, 0.995)
            self.stroke(P[j, :nlen[j]], self.rng.uniform(1.6, 2.8) * S, c, opacity=0.9, dry=0.5, thick=3.2, pick=(0.05, 0.1))
            if (i + 1) in fr and self.snap:
                self.snap(self)
        print(f"  impasto highlights: {len(order)} dabs", flush=True)


# ========================================================================================
# 3. FINISH: glaze, weave, craquelure, relief lighting, varnish
# ========================================================================================
def weave_map(H, W, S, rng):
    p = 5.2 * S
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    wob = noise((H, W), 120 * S, rng) * 1.5 * S
    u = (xx + wob) / p
    v = (yy - wob * 0.7) / p
    slub_x = 1 + 0.25 * noise((H, W), 300 * S, rng, aniso=(0.02, 1.0))
    slub_y = 1 + 0.25 * noise((H, W), 300 * S, rng, aniso=(1.0, 0.02))
    warp = np.abs(np.sin(np.pi * u)) ** 0.8 * slub_x
    weft = np.abs(np.sin(np.pi * v)) ** 0.8 * slub_y
    over = (np.floor(u) + np.floor(v)) % 2
    bump_w = np.abs(np.sin(np.pi * v * 1.0 + np.pi / 2)) ** 0.5
    h = np.where(over > 0.5, weft * (0.6 + 0.4 * bump_w), warp * (0.6 + 0.4 * np.abs(np.cos(np.pi * u)) ** 0.5))
    return (h - h.mean()).astype(np.float32)


def craquelure(H, W, S, rng, cell=46.0):
    """Crack network: Voronoi F2-F1 edges on noise-warped coordinates, two scales."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    total = np.zeros((H, W), np.float32)
    for csz, width, k in [(cell * S, 0.6 * S, 1.0), (cell * 0.45 * S, 0.45 * S, 0.45)]:
        wx = xx + noise((H, W), csz * 0.9, rng, octaves=2) * csz * 0.12
        wy = yy + noise((H, W), csz * 0.9, rng, octaves=2) * csz * 0.12
        gx = (wx / csz).astype(np.int32)
        gy = (wy / csz).astype(np.int32)
        ncx, ncy = int(W / csz) + 4, int(H / csz) + 4
        jx = rng.random((ncy + 2, ncx + 2)).astype(np.float32)
        jy = rng.random((ncy + 2, ncx + 2)).astype(np.float32)
        F1 = np.full((H, W), 1e9, np.float32)
        F2 = np.full((H, W), 1e9, np.float32)
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                cxi = np.clip(gx + ox + 1, 0, ncx + 1)
                cyi = np.clip(gy + oy + 1, 0, ncy + 1)
                px = (gx + ox + jx[cyi, cxi]) * csz
                py = (gy + oy + jy[cyi, cxi]) * csz
                d = np.hypot(wx - px, wy - py)
                F2 = np.where(d < F1, F1, np.minimum(F2, d))
                F1 = np.minimum(F1, d)
        e = F2 - F1
        crack = sstep(width * 2.0, width * 0.4, e)
        # cracks fade in and out along their length
        crack *= sstep(-0.3, 0.4, noise((H, W), csz * 1.5, rng, octaves=2))
        total = np.maximum(total, crack * k)
    return total


def finish(col, hgt, S, rng, ref_lum, timelapse_weave=None):
    H, W = hgt.shape
    weave = timelapse_weave if timelapse_weave is not None else weave_map(H, W, S, rng)
    crack = craquelure(H, W, S, rng)
    # relief: paint thickness + weave where paint is thin + cupped crack grooves
    Ht = hgt * 0.7 + weave * 0.5 * (0.3 + 0.7 * np.exp(-hgt / 1.0)) - crack * 0.45
    col = shade_relief(col, Ht, S, strength=0.4, gloss=0.05)
    lum = luma(col)
    dark_line = 1 - 0.15 * crack * sstep(0.02, 0.2, lum)
    light_line = 0.0025 * crack * sstep(0.05, 0.0, lum)
    col = col * dark_line[..., None] + light_line[..., None]
    # varnish: slightly yellowed, very slightly lifted blacks
    varn = np.array([1.0, 0.972, 0.895], np.float32)
    col = col * (0.35 + 0.65 * varn) + np.array([0.0035, 0.0028, 0.0015], np.float32)
    return np.clip(col, 0, 1)


def shade_relief(col, Ht, S, strength=0.5, gloss=0.04):
    gy, gx = np.gradient(Ht)
    k = 1.0 / max(S, 0.5)
    nx, ny, nz = -gx * k, -gy * k, np.ones_like(gx)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + 1)
    ls = nrm([-0.55, -0.65, 0.95])  # screen space: light from the upper left
    ndl = (nx * ls[0] + ny * ls[1] + nz * ls[2]) * inv
    rel = ndl / ls[2]
    out = col * (1 + strength * (rel - 1))[..., None]
    hs = nrm(ls + np.array([0, 0, 1.0]))
    spec = np.clip((nx * hs[0] + ny * hs[1] + nz * hs[2]) * inv, 0, 1) ** 60
    out += (spec * gloss * sstep(0.25, 1.5, Ht))[..., None] * np.array([0.92, 0.95, 1.0], np.float32)
    return out


def glaze(col, ref, detail, ids, S, amount=1.0):
    """Transparent umber glaze over darks (K/S absorption, applied twice: light goes in and out)."""
    lum = luma(ref)
    g = (1 - sstep(0.02, 0.35, lum)) * 0.85
    g *= (1 - 0.9 * (ids == OBJ["tag"]))
    g = blur(g, 6 * S) * amount
    Tg = np.array([0.90, 0.82, 0.68], np.float32)
    trans = Tg[None, None, :] ** (2 * g[..., None])
    # a cool scumble over the glass and smoke keeps them silvery
    cool = blur(((ids == OBJ["smoke"]) | (ids == OBJ["hourglass"])).astype(np.float32), 4 * S) * 0.25 * amount
    out = col * trans
    out = out * (1 - cool[..., None] * 0.12) + cool[..., None] * 0.12 * out * np.array([0.92, 1.0, 1.12])
    return out.astype(np.float32)


def save_srgb(img, path):
    Image.fromarray((l2s(img) * 255 + 0.5).astype(np.uint8)).save(path)


# ========================================================================================
# 4. TIMELAPSE
# ========================================================================================
class Timelapse:
    """Frames are canvas snapshots seen through a slow, deterministic camera (centre + zoom)."""
    VW, VH, FPS = 1620, 1080, 30

    def __init__(self, enabled, S, W, H, rng):
        self.enabled = enabled
        self.dir = tempfile.mkdtemp(prefix="vanitas-frames-") if enabled else None
        self.n = 0
        self.S, self.W, self.H = S, W, H
        self.marks = []
        self.cam_from = np.array([W / 2, H / 2, 1.0])
        self.cam_to = self.cam_from.copy()
        self.cam_k, self.cam_n = 0, 1
        if enabled:
            self.weave = weave_map(H, W, S, rng)

    def mark(self, label):
        self.marks.append((round(self.n / self.FPS, 2), label))

    def move(self, cx, cy, zoom, frames=36):
        """Ease the camera to a design-space centre and zoom over `frames` frames."""
        self.cam_from = self.camera()
        self.cam_to = np.array([cx * self.S, cy * self.S, zoom])
        self.cam_k, self.cam_n = 0, frames

    def camera(self):
        a = ease(min(1.0, self.cam_k / max(1, self.cam_n)))
        return self.cam_from + (self.cam_to - self.cam_from) * a

    def box(self):
        cx, cy, z = self.camera()
        w = self.W / z
        h = w * self.VH / self.VW
        x0 = min(max(cx - w / 2, 0), self.W - w)
        y0 = min(max(cy - h / 2, 0), self.H - h)
        return (x0, y0, x0 + w, y0 + h)

    def _crop(self, a, box):
        rs = Image.BOX if (box[2] - box[0]) > self.VW * 1.05 else Image.BICUBIC
        if a.ndim == 2:
            return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((self.VW, self.VH), rs, box=box), np.float32)
        return np.stack([self._crop(a[..., i], box) for i in range(a.shape[2])], -1)

    def frame_from(self, col, hgt):
        if not self.enabled:
            return
        box = self.box()
        c = self._crop(col, box)
        h = self._crop(hgt, box)
        wv = self._crop(self.weave, box)
        Ht = h * 0.9 + wv * 0.5 * (0.3 + 0.7 * np.exp(-h / 1.0))
        s_eff = self.S * (box[2] - box[0]) / self.VW
        c = shade_relief(c, Ht, max(s_eff * 0.6, 0.35), strength=0.45, gloss=0.04)
        self.write(l2s(c))
        self.cam_k += 1

    def write(self, srgb):
        Image.fromarray((np.clip(srgb, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
            os.path.join(self.dir, f"f{self.n:05d}.jpg"), quality=94)
        self.n += 1

    def hold(self, frames):
        if not self.enabled or self.n == 0:
            return
        last = os.path.join(self.dir, f"f{self.n - 1:05d}.jpg")
        for _ in range(frames):
            shutil.copyfile(last, os.path.join(self.dir, f"f{self.n:05d}.jpg"))
            self.n += 1

    def encode(self, path):
        if not self.enabled:
            return
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(self.FPS), "-i",
               os.path.join(self.dir, "f%05d.jpg"), "-vf", "scale=in_range=pc:out_range=tv,format=yuv420p",
               "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-color_range", "tv",
               "-movflags", "+faststart", path]
        subprocess.run(cmd, check=True)
        shutil.rmtree(self.dir, ignore_errors=True)


def ease(t):
    return t * t * (3 - 2 * t)


def object_boxes(sc):
    out = {}
    for name, oid in OBJ.items():
        ys, xs = np.nonzero(sc.ids == oid)
        if len(xs) < 20:
            continue
        out[name] = [round(float(np.percentile(xs, 2)) / sc.W * 100, 2), round(float(np.percentile(ys, 2)) / sc.H * 100, 2),
                     round(float(np.percentile(xs, 98)) / sc.W * 100, 2), round(float(np.percentile(ys, 98)) / sc.H * 100, 2)]
    return out


LAYERS = [
    # R (design px), threshold, max/min stroke length, frames in the timelapse, dryness, label
    dict(R=64, T=0.0, max_len=9, min_len=3, frames=150, dry=0.55, rough=0.12, label="Dead colouring, 64 px brush"),
    dict(R=34, T=0.075, max_len=11, min_len=3, frames=135, dry=0.5, rough=0.10, label="Blocking in, 34 px"),
    dict(R=17, T=0.065, max_len=13, min_len=3, frames=135, dry=0.42, rough=0.08, label="Forms, 17 px"),
    dict(R=8.5, T=0.055, max_len=14, min_len=2, frames=135, dry=0.35, rough=0.07, diverge=0.6, label="Edges, 8.5 px"),
    dict(R=4.2, T=0.05, max_len=14, min_len=2, frames=120, dry=0.3, rough=0.06, diverge=0.45, label="Detail, 4 px"),
    dict(R=2.1, T=0.045, max_len=8, min_len=1, frames=90, dry=0.2, rough=0.05, detail_only=True, det_min=0.2,
         pick=(0.03, 0.15), diverge=0.3, label="Fine detail, 2 px"),
    dict(R=1.1, T=0.035, max_len=4, min_len=0, frames=36, dry=0.1, rough=0.03, detail_only=True, det_min=0.6,
         pick=(0.0, 0.05), diverge=0.2, label="Lettering with a liner"),
    dict(R=1.1, T=0.035, max_len=4, min_len=0, frames=24, dry=0.1, rough=0.03, detail_only=True, det_min=0.6,
         pick=(0.0, 0.05), diverge=0.2, label=None),
    dict(R=0.8, T=0.035, max_len=2, min_len=0, frames=24, dry=0.1, rough=0.03, detail_only=True, det_min=0.6,
         pick=(0.0, 0.05), diverge=0.15, label=None),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.25)
    ap.add_argument("--seed", type=int, default=1642)
    ap.add_argument("--ref-only", default="")
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--out", default=os.path.join(OUT, "vanitas.png"))
    ap.add_argument("--video", default=os.path.join(OUT, "vanitas-timelapse.mp4"))
    args = ap.parse_args()
    T0 = time.time()
    sc = build_scene(args.scale, args.seed)
    if args.ref_only:
        save_srgb(sc.img, args.ref_only)
        save_srgb(np.repeat(sc.detail[..., None], 3, -1), args.ref_only.replace(".png", "_detail.png"))
        return
    os.makedirs(OUT, exist_ok=True)
    ref = np.clip(sc.img, 0, 1)
    S = sc.S
    hint = np.where(np.isnan(sc.flow), 0.0, sc.flow).astype(np.float32)
    # the wall gets loose, crossing diagonal strokes; the ledge follows its grain
    nz = noise((sc.H, sc.W), 260 * S, np.random.default_rng(args.seed + 3), octaves=2)
    wallflow = (math.pi * 0.28 + 1.1 * nz).astype(np.float32)
    hint = np.where(np.isnan(sc.flow), wallflow, hint)
    tl = Timelapse(not args.no_video, S, sc.W, sc.H, np.random.default_rng(args.seed + 5))
    force = blur(((sc.ids == OBJ["wall"]) | (sc.ids == OBJ["ledge"])).astype(np.float32), 8 * S) * 0.85
    painter = Painter(ref, sc.detail, hint, S, args.seed, snap=lambda p: tl.frame_from(p.col, p.hgt), force=force)
    tl.mark("Toned ground")
    tl.frame_from(painter.col, painter.hgt)
    tl.hold(5)
    tl.mark("Underdrawing in umber")
    painter.underdrawing(frames=66)
    # camera: full frame while the big brushes work, then in on the book, the key, and the tag
    cams = {4: (1010, 1000, 1.55), 5: (780, 1030, 2.3), 6: (905, 1172, 3.4)}
    for li, L in enumerate(LAYERS):
        if li in cams:
            tl.move(*cams[li])
        if L["label"]:
            tl.mark(L["label"])
        painter.layer(L["R"], L["T"], L["max_len"], L["min_len"], dry=L["dry"], rough=L["rough"],
                      detail_only=L.get("detail_only", False), frames=L["frames"], label=L["label"],
                      det_min=L.get("det_min", 0.2), pick=L.get("pick", (0.08, 0.38)), diverge=L.get("diverge", 9.0))
    tl.mark("Lead-white impasto")
    tl.move(1260, 960, 1.6, frames=30)
    painter.highlights(frames=36)
    # glaze (shown as a gradual change)
    tl.mark("Umber glaze")
    tl.move(DW / 2, DH / 2, 1.0, frames=40)
    base = painter.col.copy()
    glazed = glaze(base, ref, sc.detail, sc.ids, S)
    for f in range(45):
        a = ease((f + 1) / 45)
        tl.frame_from(base * (1 - a) + glazed * a, painter.hgt)
    painter.col = glazed
    # finish: relief, weave, craquelure, varnish
    rng = np.random.default_rng(args.seed + 11)
    final = finish(painter.col, painter.hgt, S, rng, luma(ref))
    srgb = l2s(final)
    Image.fromarray((srgb * 255 + 0.5).astype(np.uint8)).save(args.out, optimize=False, compress_level=6)
    print(f"painting saved: {args.out} ({sc.W}x{sc.H}), {painter.count} strokes, {time.time() - T0:.0f}s", flush=True)
    if tl.enabled:
        tl.mark("Varnish and craquelure")
        last = resize_f(srgb, tl.VW, tl.VH, Image.LANCZOS)
        box = (0, 0, sc.W, sc.H)
        hh = tl._crop(painter.hgt, box)
        prev = l2s(shade_relief(tl._crop(painter.col, box), hh * 0.9 + tl._crop(tl.weave, box) * 0.5 * (0.3 + 0.7 * np.exp(-hh)),
                                max(S * sc.W / tl.VW * 0.6, 0.35), strength=0.45, gloss=0.04))
        for f in range(40):
            a = ease((f + 1) / 40)
            tl.write(prev * (1 - a) + last * a)
        tl.hold(30)
        # push in to the leaked key's tag on the finished painting
        tl.mark("Close look at the tag")
        im = Image.fromarray((srgb * 255 + 0.5).astype(np.uint8))
        tx0, ty0, tx1, ty1 = sc.tag_box
        cxp, cyp = (tx0 + tx1) / 2 * S, (ty0 + ty1) / 2 * S - 30 * S
        zw = sc.W / 3.2
        nzf = 135
        for f in range(nzf):
            a = ease(f / (nzf - 1))
            w = sc.W + (zw - sc.W) * a
            h = w * tl.VH / tl.VW
            x0 = (sc.W / 2) * (1 - a) + cxp * a - w / 2
            y0 = (sc.H / 2) * (1 - a) + cyp * a - h / 2
            x0 = min(max(x0, 0), sc.W - w)
            y0 = min(max(y0, 0), sc.H - h)
            fr = im.resize((tl.VW, tl.VH), Image.LANCZOS, box=(x0, y0, x0 + w, y0 + h))
            tl.write(np.asarray(fr, np.float32) / 255.0)
        tl.hold(45)
        tl.encode(args.video)
        print(f"timelapse saved: {args.video} ({tl.n} frames, {tl.n / tl.FPS:.1f}s)", flush=True)
        print("chapters:", json.dumps(tl.marks))
    print("hotspot boxes (% of canvas):", json.dumps(object_boxes(sc)))
    print(f"total {time.time() - T0:.0f}s")


if __name__ == "__main__":
    main()
