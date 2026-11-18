#!/usr/bin/env python3
"""Stylised 3D medical animation: how polluted air travels from the lungs to the heart.

    python3 engine/bioanim.py videos/<slug>/bio_config.py

Everything is rendered procedurally (no stock, no AI video): lit sphere/disc sprites,
tunnel rings, an implicit-surface heart, glowing particles, depth blur and slow camera
moves, at 540x960 internally (then upscaled to 1080x1920). The config lists slides as
(scene, [statement lines], seconds); statements fade and rise slowly in the lower third.
"""
import math, os, runpy, subprocess, sys, wave
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ENGINE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(ENGINE)
CFG = os.path.abspath(sys.argv[1]); VDIR = os.path.dirname(CFG); C = runpy.run_path(CFG)
P = lambda p: p if os.path.isabs(p) else os.path.join(VDIR, p)
W, H, FPS = 1080, 1920, 30
w, h = 540, 960                                          # internal render size
ANTON = os.path.join(REPO, "assets", "fonts", "Anton-Regular.woff")
INTER = "/usr/share/fonts/opentype/inter/"
CREAM, WHITE, RED = (240, 214, 158), (255, 255, 255), (232, 64, 52)
TMP = os.path.join(VDIR, ".tmp"); os.makedirs(TMP, exist_ok=True)
LIGHT = np.array([-0.45, -0.55, 0.70]); LIGHT /= np.linalg.norm(LIGHT)

def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)

_f = {}
def font(kind, size):
    k = (kind, size)
    if k not in _f:
        _f[k] = ImageFont.truetype(ANTON if kind == "anton" else INTER + f"Inter-{kind}.otf", size)
    return _f[k]

# ------------------------------------------------------------------ sprites
@lru_cache(maxsize=512)
def sphere(r, col, spec=0.35, rim=0.30, blur=0, gloss=24):
    r = max(2, int(r)); n = 2 * r + 2
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    x, y = (xx - n / 2 + 0.5) / r, (yy - n / 2 + 0.5) / r
    d2 = x * x + y * y
    a = np.clip((1 - np.sqrt(d2)) * r * 0.9, 0, 1)
    z = np.sqrt(np.clip(1 - d2, 0, 1))
    lam = np.clip(x * LIGHT[0] + y * LIGHT[1] + z * LIGHT[2], 0, 1)
    refl = np.clip(2 * lam * z - LIGHT[2], 0, 1) ** gloss
    rimv = (1 - z) ** 2.2
    c = np.array(col, np.float32)
    rgb = c * (0.28 + 0.78 * lam)[..., None] + 255 * spec * refl[..., None] + c * rim * rimv[..., None] * 1.4
    out = np.dstack([np.clip(rgb, 0, 255), a * 255]).astype(np.uint8)
    im = Image.fromarray(out, "RGBA")
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(im).astype(np.float32) / 255

@lru_cache(maxsize=256)
def rbc(r, blur=0, squash=1.0):
    """Red blood cell: biconcave disc, seen at an angle (squash)."""
    r = max(3, int(r)); n = 2 * r + 2
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    x, y = (xx - n / 2 + 0.5) / r, (yy - n / 2 + 0.5) / (r * squash)
    d = np.sqrt(x * x + y * y)
    a = np.clip((1 - d) * r * 0.9, 0, 1)
    dent = np.exp(-(d / 0.45) ** 2)                    # central dimple
    zz = np.sqrt(np.clip(1 - d * d, 0, 1)) * (1 - 0.65 * dent)
    gx, gy = np.gradient(zz)
    nx, ny, nz = -gx * r * 0.6, -gy * r * 0.6, np.ones_like(zz)
    nn = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    lam = np.clip((nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) / nn, 0, 1)
    col = np.array([196, 28, 34], np.float32)
    rgb = col * (0.30 + 0.85 * lam)[..., None] + 60 * lam[..., None] ** 12
    im = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a * 255]).astype(np.uint8), "RGBA")
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(im).astype(np.float32) / 255

@lru_cache(maxsize=64)
def glow(r, col, strength=1.0):
    r = max(2, int(r)); n = 2 * r + 2
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    d = np.sqrt((xx - n / 2) ** 2 + (yy - n / 2) ** 2) / r
    a = np.clip(np.exp(-d * d * 3) * strength, 0, 1)
    return np.dstack([np.broadcast_to(np.array(col, np.float32) / 255, (n, n, 3)), a])

def paste(cv, spr, cx, cy, alpha=1.0, add=False):
    sh, sw = spr.shape[:2]
    x0, y0 = int(cx - sw / 2), int(cy - sh / 2)
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + sw, cv.shape[1]), min(y0 + sh, cv.shape[0])
    if xb <= xa or yb <= ya:
        return
    s = spr[ya - y0:yb - y0, xa - x0:xb - x0]
    a = s[..., 3:4] * alpha
    if add:
        cv[ya:yb, xa:xb] += s[..., :3] * 255 * a
    else:
        cv[ya:yb, xa:xb] = cv[ya:yb, xa:xb] * (1 - a) + s[..., :3] * 255 * a

def vgrad(top, bot):
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    return np.broadcast_to(np.array(top, np.float32) * (1 - y) + np.array(bot, np.float32) * y, (h, w, 3)).copy()

def rgrad(center, inner, outer, radius):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.clip(np.sqrt((xx - center[0]) ** 2 + (yy - center[1]) ** 2) / radius, 0, 1)[..., None]
    return np.array(inner, np.float32) * (1 - d) + np.array(outer, np.float32) * d

def blur(cv, r):
    im = Image.fromarray(np.clip(cv, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    return np.asarray(im).astype(np.float32)

def chip(cv_img, text, x, y, anchor=None, a=1.0):
    """Ref-style label chip (dark glass, thin border) with an optional pointer line. Works on a PIL RGBA overlay."""
    d = ImageDraw.Draw(cv_img)
    f = font("SemiBold", 30)
    tw = d.textlength(text, font=f)
    box = (x, y, x + tw + 36, y + 52)
    if anchor:
        d.line((box[0] if anchor[0] < x else box[2], y + 26, anchor[0], anchor[1]), fill=(255, 255, 255, int(200 * a)), width=3)
        d.ellipse((anchor[0] - 7, anchor[1] - 7, anchor[0] + 7, anchor[1] + 7), fill=(255, 255, 255, int(230 * a)))
    d.rounded_rectangle(box, 12, fill=(12, 16, 22, int(190 * a)), outline=(255, 255, 255, int(170 * a)), width=2)
    d.text((x + 18, y + 9), text, font=f, fill=(255, 255, 255, int(255 * a)))

R = np.random.default_rng(7)

# ------------------------------------------------------------------ scene 1 / 7: city smog, person inhaling
SKY = None
def city_bg(t, dusk=0.0):
    bg = vgrad((58 - 20 * dusk, 62 - 22 * dusk, 60 - 14 * dusk), (120 - 40 * dusk, 112 - 40 * dusk, 96 - 34 * dusk))
    img = Image.fromarray(bg.astype(np.uint8)).convert("RGBA"); d = ImageDraw.Draw(img)
    rr = np.random.default_rng(3)
    for base, col in ((520, (92, 92, 88)), (600, (70, 70, 68)), (690, (48, 50, 50))):
        x = -20
        while x < w:
            bw_ = rr.integers(30, 80); bh_ = rr.integers(80, 300)
            d.rectangle((x, base - bh_, x + bw_, h), fill=col + (255,))
            x += bw_ + rr.integers(2, 12)
    sun = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sx = 150 + 120 * dusk
    ImageDraw.Draw(sun).ellipse((sx - 45, 260 + 120 * dusk, sx + 45, 350 + 120 * dusk), fill=(255, 196, 130, 150))
    img.alpha_composite(sun.filter(ImageFilter.GaussianBlur(22)))
    return blur(np.asarray(img.convert("RGB")).astype(np.float32), 3)

PROFILE = [(540, 300), (470, 290), (430, 305), (408, 340), (400, 380), (392, 410), (378, 440), (392, 452), (398, 470),
           (390, 490), (398, 500), (396, 520), (404, 545), (420, 560), (440, 575), (446, 610), (440, 650),
           (420, 690), (400, 760), (380, 960), (540, 960)]
SMOKE = [(R.uniform(-60, 360), R.uniform(250, 760), R.uniform(10, 34), R.uniform(0, 6.28), R.uniform(0.6, 1.4)) for _ in range(140)]
PROFILE = [(540 + (x - 540) * 1.3 - 70, 960 + (y - 960) * 1.3) for x, y in PROFILE]
NOSE = (540 + (392 - 540) * 1.3 - 70, 960 + (470 - 960) * 1.3)

def scene_inhale(t, dur, xray=True, dusk=0.0):
    u = t / dur
    cv = city_bg(t, dusk)
    over = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(over)
    # person (side profile), rim-lit
    d.polygon(PROFILE, fill=(30, 34, 40, 255))
    rim = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(rim).line(PROFILE[:-2], fill=(255, 170, 110, 255), width=3)
    over.alpha_composite(rim.filter(ImageFilter.GaussianBlur(2)))
    o = np.asarray(over).astype(np.float32) / 255
    cv = cv * (1 - o[..., 3:4]) + o[..., :3] * 255 * o[..., 3:4]
    if xray:                                           # glowing lungs inside the chest
        lungs = Image.new("L", (w, h), 0); ld = ImageDraw.Draw(lungs)
        ld.ellipse((330, 650, 450, 880), fill=255); ld.ellipse((395, 640, 510, 885), fill=200)
        lmask = np.asarray(lungs.filter(ImageFilter.GaussianBlur(10))).astype(np.float32)[..., None] / 255
        pulse = 0.55 + 0.25 * math.sin(t * 2.4)
        cv = cv + lmask * np.array([220, 70, 50], np.float32) * pulse * ease(u * 2.5)
        tr = Image.new("L", (w, h), 0); td = ImageDraw.Draw(tr)
        td.line((385, 520, 400, 660), fill=255, width=8)
        for a_ in (-0.9, -0.4, 0.3, 0.8):
            td.line((400, 660, 400 + 70 * math.sin(a_), 660 + 80 * math.cos(a_)), fill=180, width=3)
        tm = np.asarray(tr.filter(ImageFilter.GaussianBlur(2))).astype(np.float32)[..., None] / 255
        cv = cv + tm * np.array([255, 150, 110], np.float32) * 0.8 * ease(u * 2.5)
    # smoke drawn toward the nose; inhaled particles stream down the windpipe
    for i, (x0, y0, r_, ph, sp) in enumerate(SMOKE):
        k = ((t * 0.18 * sp + i / len(SMOKE)) % 1.0)
        x = x0 + (NOSE[0] - x0) * k ** 1.6 + 18 * math.sin(t * 0.8 + ph)
        y = y0 + (NOSE[1] - y0) * k ** 1.6 + 10 * math.cos(t * 0.6 + ph)
        rr_ = r_ * (1 - 0.8 * k)
        paste(cv, glow(int(rr_), (150, 146, 138), 0.55), x, y, 0.55 * (1 - k ** 3))
    if xray:
        for i in range(26):
            k = (t * 0.35 + i / 26) % 1.0
            x = 385 + 15 * k + 40 * math.sin(i * 1.7) * max(0, k - 0.5)
            y = 520 + 300 * k
            paste(cv, glow(5, (40, 40, 40), 1.0), x, y, 0.9)
            paste(cv, glow(9, (255, 200, 150), 0.35), x, y, 0.5, add=True)
    return cv

# ------------------------------------------------------------------ scene 2: down the windpipe
AIR_P = [(R.uniform(-1, 1), R.uniform(-1, 1), R.uniform(0.2, 6.0)) for _ in range(220)]
def scene_airway(t, dur):
    u = t / dur
    cv = rgrad((w / 2, h * 0.45), (16, 4, 6), (120, 40, 44), 520)
    cx, cy = w / 2 + 20 * math.sin(t * 0.4), h * 0.45 + 14 * math.cos(t * 0.3)
    speed, spacing = 1.4, 0.55
    off = (t * speed) % spacing
    rings = []
    z = 6.0 - off
    while z > 0.25:
        rings.append(z); z -= spacing
    img = Image.fromarray(np.clip(cv, 0, 255).astype(np.uint8)).convert("RGBA")
    for z in rings:                                       # far to near
        Rr = 150 / z
        fog = math.exp(-z / 2.6)
        base = np.array([214, 132, 128]) * (0.25 + 0.75 * fog)
        lay = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        th = max(2, Rr * 0.16)
        d.ellipse((cx - Rr, cy - Rr * 0.92, cx + Rr, cy + Rr * 0.92), outline=tuple(int(c) for c in base) + (255,), width=int(th))
        hl = tuple(int(min(255, c * 1.35)) for c in base)
        d.arc((cx - Rr, cy - Rr * 0.92, cx + Rr, cy + Rr * 0.92), 200, 320, fill=hl + (255,), width=max(1, int(th * 0.45)))
        img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(max(0.6, 1.2 / z))))
    # the airway divides at the end: two dark openings
    d = ImageDraw.Draw(img)
    for dx in (-26, 26):
        d.ellipse((cx + dx - 18, cy - 24, cx + dx + 18, cy + 24), fill=(10, 2, 4, 230))
    cv = np.asarray(img.convert("RGB")).astype(np.float32)
    for (px, py, pz0) in AIR_P:                           # particles drifting deeper with us
        pz = (pz0 - t * 0.9) % 6.0 + 0.3
        sx, sy = cx + px * 0.8 * 150 / pz, cy + py * 0.8 * 150 / pz
        r_ = max(1, int(5 / pz * 2.2))
        paste(cv, sphere(r_, (60, 58, 56), 0.2, 0.2), sx, sy, min(1, 0.4 + 1.2 / pz))
    return cv

# ------------------------------------------------------------------ scene 3: alveoli, deposits, cancer risk
ALV = []
for cxk, cyk, n_ in ((170, 330, 14), (360, 300, 13), (250, 560, 16), (420, 600, 12), (150, 760, 12), (380, 820, 11)):
    for k in range(n_):
        a_ = R.uniform(0, 6.28); rad = R.uniform(10, 70)
        ALV.append((cxk + rad * math.cos(a_), cyk + rad * math.sin(a_) * 1.1, R.uniform(26, 40), R.uniform(0.6, 1.0)))
ALV.sort(key=lambda s: s[3])
STEMS = [((270, -40), (270, 200)), ((270, 200), (170, 330)), ((270, 200), (360, 300)), ((270, 200), (270, 420)),
         ((270, 420), (250, 560)), ((270, 420), (420, 600)), ((250, 560), (150, 760)), ((420, 600), (380, 820))]
SPOTS = [(R.integers(0, len(ALV)), R.uniform(-0.5, 0.5), R.uniform(-0.5, 0.5), R.uniform(0, 1)) for _ in range(90)]
DUST = [(R.uniform(0, w), R.uniform(-200, 0), R.uniform(0.6, 1.4)) for _ in range(120)]

def scene_alveoli(t, dur):
    u = t / dur
    cv = rgrad((w / 2, h / 2), (70, 22, 30), (18, 6, 10), 620)
    s = 1.0 + 0.12 * u
    T = lambda x, y: (w / 2 + (x - w / 2) * s, h / 2 + (y - h / 2) * s)
    img = Image.fromarray(np.clip(cv, 0, 255).astype(np.uint8)).convert("RGBA"); d = ImageDraw.Draw(img)
    cv = np.asarray(img.convert("RGB")).astype(np.float32)
    for (a, b) in STEMS:                                  # bronchioles as shaded tubes (chains of spheres)
        ax, ay = T(*a); bx, by = T(*b)
        n_ = int(max(abs(bx - ax), abs(by - ay)) / 6) + 1
        for k in range(n_ + 1):
            paste(cv, sphere(int(13 * s), (200, 118, 116), 0.18, 0.25), ax + (bx - ax) * k / n_, ay + (by - ay) * k / n_)
    dark = ease((u - 0.25) / 0.6)
    for i, (x, y, r_, depth) in enumerate(ALV):
        X, Y = T(x, y)
        tint = (232, 156, 150) if (i % 7) else (222, 140, 138)
        grey = dark * (0.55 if i % 4 == 0 else 0.15)
        col = tuple(int(c * (1 - grey) + 70 * grey) for c in tint)
        paste(cv, sphere(int(r_ * s), col, 0.25, 0.35, blur=int((1 - depth) * 4)), X, Y)
    # capillary net (red / blue) over the sacs
    net = Image.new("RGBA", (w, h), (0, 0, 0, 0)); nd = ImageDraw.Draw(net)
    for i in range(len(ALV)):
        for j in range(i + 1, min(i + 6, len(ALV))):
            (x1, y1, r1, _), (x2, y2, r2, _) = ALV[i], ALV[j]
            if math.hypot(x2 - x1, y2 - y1) < 70:
                X1, Y1 = T(x1, y1); X2, Y2 = T(x2, y2)
                nd.line((X1, Y1, X2, Y2), fill=((205, 40, 50, 130) if (i + j) % 3 else (80, 100, 210, 120)), width=2)
    no = np.asarray(net).astype(np.float32) / 255
    cv = cv * (1 - no[..., 3:4]) + no[..., :3] * 255 * no[..., 3:4]
    for (ai, ox, oy, t0) in SPOTS:                        # dark deposits accumulate on the sacs
        if u > 0.1 + 0.7 * t0:
            x, y, r_, _ = ALV[ai]; X, Y = T(x, y)
            paste(cv, glow(int(6 * s), (25, 22, 20), 1.2), X + ox * r_ * s, Y + oy * r_ * s, 0.85)
    for (x, y0, sp) in DUST:                              # particles still raining in
        y = (y0 + t * 70 * sp) % (h + 200) - 100
        paste(cv, sphere(3, (55, 52, 50), 0.2, 0.2), x + 10 * math.sin(t + sp * 5), y, 0.9)
    return cv

# ------------------------------------------------------------------ scene 4: into the bloodstream
CELLS = [(R.uniform(0, w * 1.6), R.uniform(470, 760), R.uniform(0.5, 1.0), R.uniform(0.35, 1.0)) for _ in range(46)]
CROSS = [(R.uniform(0, w), R.uniform(0, 1)) for _ in range(40)]
def scene_blood(t, dur):
    u = t / dur
    cv = vgrad((96, 34, 40), (40, 10, 14))
    img = Image.fromarray(np.clip(cv, 0, 255).astype(np.uint8)).convert("RGBA"); d = ImageDraw.Draw(img)
    # alveolar side (top) and vessel walls
    for x in range(-40, w + 40, 46):
        d.ellipse((x + (t * 6) % 46, 250, x + 60 + (t * 6) % 46, 330), fill=(206, 130, 126, 255))
    d.rectangle((0, 380, w, 440), fill=(176, 92, 88, 255)); d.rectangle((0, 790, w, 850), fill=(150, 70, 70, 255))
    for x in range(0, w, 38):
        d.ellipse((x, 388, x + 34, 432), fill=(196, 112, 104, 255)); d.ellipse((x + 10, 798, x + 44, 842), fill=(170, 86, 82, 255))
    cv = blur(np.asarray(img.convert("RGB")).astype(np.float32), 1.5)
    cv[440:790] = cv[440:790] * 0.55 + np.array([110, 18, 24], np.float32) * 0.45
    for (x0, y, depth, sq) in sorted(CELLS, key=lambda c: c[2]):
        x = (x0 + t * 120 * (0.6 + depth)) % (w * 1.6) - w * 0.3
        paste(cv, rbc(int(24 + 18 * depth), blur=int((1 - depth) * 5), squash=round(sq, 1)), x, y)
    for (x, k0) in CROSS:                                 # PM2.5 slipping through the wall into the blood
        k = (k0 + t * 0.18) % 1.0
        y = 300 + k * 470
        xx = x + (t * 60 * k if k > 0.33 else 0)
        paste(cv, sphere(4, (50, 48, 46), 0.25, 0.2), xx % w, y, 1.0)
        paste(cv, glow(10, (255, 210, 170), 0.3), xx % w, y, 0.6, add=True)
    return cv

# ------------------------------------------------------------------ scene 5 / 6: the artery
SPARKS = [(R.uniform(0, 6.28), R.uniform(0.3, 0.95), R.uniform(0, 6.28)) for _ in range(60)]
GLU = [(R.uniform(0, 6.28), R.uniform(0.1, 0.9), R.uniform(0, 1)) for _ in range(28)]
def scene_artery(t, dur, mode="plaque"):
    u = t / dur
    cx, cy = w / 2, h * 0.42
    beat = (math.sin(t * 2 * math.pi / 0.95) ** 8) if mode == "pressure" else 0.0
    Ro = 230 * (1 + 0.05 * beat)
    cv = rgrad((cx, cy), (60, 16, 20), (14, 4, 6), 600)
    img = Image.fromarray(np.clip(cv, 0, 255).astype(np.uint8)).convert("RGBA"); d = ImageDraw.Draw(img)
    d.ellipse((cx - Ro, cy - Ro, cx + Ro, cy + Ro), fill=(200, 120, 110, 255))                 # outer wall
    d.ellipse((cx - Ro * 0.84, cy - Ro * 0.84, cx + Ro * 0.84, cy + Ro * 0.84), fill=(176, 74, 72, 255))   # muscle layer
    pl = (0.15 + 0.85 * ease(u * 1.2)) if mode == "plaque" else 0.75
    Rl = Ro * 0.66
    d.ellipse((cx - Rl, cy - Rl, cx + Rl, cy + Rl), fill=(232, 168, 150, 255))                 # inner lining
    lum = Rl * 0.94
    d.ellipse((cx - lum, cy - lum, cx + lum, cy + lum), fill=(120, 14, 22, 255))                # blood
    # plaque: lumpy yellow mass growing from the lower right, narrowing the passage
    pcx, pcy = cx + lum * 0.45, cy + lum * 0.40
    for k in range(18):
        a_ = -0.5 + k * 0.12
        rr_ = lum * (0.28 + 0.42 * pl) * (0.8 + 0.2 * math.sin(k * 2.3))
        px, py = pcx + math.cos(a_ + 0.6) * lum * 0.25, pcy + math.sin(a_ + 0.6) * lum * 0.25
        d.ellipse((px - rr_ * 0.6, py - rr_ * 0.6, px + rr_ * 0.6, py + rr_ * 0.6), fill=(226, 190, 96, 255))
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    cv = np.asarray(img.convert("RGB")).astype(np.float32)
    # 3D-ish shading of the vessel: light from upper left
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    shade = 1 + 0.25 * (-(xx - cx) / Ro - (yy - cy) / Ro) * np.clip(1 - np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (Ro * 1.05), 0, 1)
    cv *= shade[..., None]
    # inflammation glow around the plaque (pulsing)
    infl = 0.55 + 0.45 * math.sin(t * 3.1)
    paste(cv, glow(int(lum * 0.9), (255, 70, 40), 0.9), pcx, pcy, 0.45 * infl * pl, add=True)
    # oxidative-stress sparks
    for (a_, rf, ph) in SPARKS:
        if math.sin(t * 4 + ph) > 0.6:
            sx, sy = cx + math.cos(a_) * lum * rf, cy + math.sin(a_) * lum * rf
            paste(cv, glow(7, (200, 240, 255), 1.0), sx, sy, 0.8, add=True)
    # red cells drifting through the lumen toward us
    for i in range(14):
        k = (t * 0.35 + i / 14) % 1.0
        a_ = i * 2.4
        rr_ = lum * 0.55 * (0.3 + 0.7 * ((i * 37) % 10) / 10)
        x, y = cx + math.cos(a_) * rr_ * 0.6 - lum * 0.15, cy + math.sin(a_) * rr_ * 0.6 - lum * 0.15
        paste(cv, rbc(int(8 + 26 * k), blur=int((1 - k) * 3)), x, y, min(1, k * 3))
    if mode == "pressure":                                 # sugar crystals in the blood
        for (a_, rf, ph) in GLU:
            x, y = cx + math.cos(a_ + t * 0.3) * lum * rf * 0.7, cy + math.sin(a_ + t * 0.3) * lum * rf * 0.7
            hx = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
            ImageDraw.Draw(hx).regular_polygon((12, 12, 9), 6, rotation=ph * 60, fill=(250, 236, 196, 235))
            paste(cv, np.asarray(hx).astype(np.float32) / 255, x, y, 0.9)
        paste(cv, glow(int(Ro * 1.15), (255, 60, 50), 0.6), cx, cy, 0.25 * beat, add=True)
    return cv

# ------------------------------------------------------------------ scene 8 / 9: the heart
_HY, _HX = np.mgrid[0:h, 0:w].astype(np.float32)
def heart_field(scale, cx, cy, tilt=-0.38):
    x0 = (_HX - cx) / scale; y0 = -(_HY - cy) / scale
    ca, sa = math.cos(tilt), math.sin(tilt)
    x = x0 * ca - y0 * sa; y = x0 * sa + y0 * ca
    x = x * (1.0 + 0.12 * (x > 0))                            # left ventricle fuller than the right
    f = (x * x + y * y - 1) ** 3 - x * x * y ** 3
    return f

def scene_heart(t, dur, scan=False):
    u = t / dur
    cv = rgrad((w / 2, h * 0.42), (40, 14, 20), (8, 6, 10), 560)
    beat = math.sin(t * 2 * math.pi / 0.95) ** 10
    sc = 150 * (1 + 0.05 * beat) * (1 + 0.04 * u)
    cx, cy = w / 2, h * 0.42
    # great vessels behind the top of the heart: aorta arch (red), pulmonary trunk (blue-violet), vena cava (blue)
    def tube(pts, r_, col):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            n_ = int(math.hypot(x2 - x1, y2 - y1) / 4) + 1
            for k in range(n_):
                paste(cv, sphere(int(r_), col, 0.3, 0.3), x1 + (x2 - x1) * k / n_, y1 + (y2 - y1) * k / n_)
    arch = [(cx - 0.05 * sc + 1.05 * sc * math.cos(a_) * 0.55, cy - 0.85 * sc - 0.75 * sc * math.sin(a_) * 0.9)
            for a_ in np.linspace(math.pi * 0.95, math.pi * 0.08, 16)]
    tube([(cx + 0.38 * sc, cy - 0.55 * sc), (cx + 0.40 * sc, cy - 1.25 * sc)], 0.17 * sc, (70, 80, 170))     # vena cava
    tube(arch + [(arch[-1][0] + 0.05 * sc, arch[-1][1] + 0.55 * sc)], 0.2 * sc, (196, 40, 44))              # aorta
    for k, dx in enumerate((-0.25, 0.0, 0.22)):                                                              # arch branches
        bx, by = arch[5 + 3 * k]
        tube([(bx, by), (bx + dx * sc * 0.4, by - 0.45 * sc)], 0.07 * sc, (190, 40, 44))
    tube([(cx - 0.35 * sc, cy - 0.45 * sc), (cx - 0.55 * sc, cy - 1.0 * sc), (cx - 0.85 * sc, cy - 1.15 * sc)], 0.16 * sc, (110, 70, 170))
    f = heart_field(sc, cx, cy)
    inside = f < 0
    depth = np.sqrt(np.clip(-f, 0, None)) ** 0.5
    gy, gx = np.gradient(depth)
    nx, ny, nz = -gx * 60, -gy * 60, np.ones_like(depth)
    nn = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    lam = np.clip((nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2]) / nn, 0, 1)
    spec = np.clip(lam, 0, 1) ** 30
    col = np.array([178, 34, 40], np.float32)
    shaded = col * (0.25 + 0.85 * lam)[..., None] + 120 * spec[..., None]
    a = np.clip(-f * 40, 0, 1)[..., None] * inside[..., None]
    cv = cv * (1 - a) + shaded * a
    # coronary arteries
    art = Image.new("RGBA", (w, h), (0, 0, 0, 0)); ad = ImageDraw.Draw(art)
    pts = [(cx - 0.1 * sc, cy - 0.75 * sc), (cx - 0.05 * sc, cy - 0.2 * sc), (cx + 0.15 * sc, cy + 0.35 * sc), (cx + 0.05 * sc, cy + 0.9 * sc)]
    ad.line(pts, fill=(255, 180, 150, 220), width=6, joint="curve")
    ad.line([(cx - 0.05 * sc, cy - 0.2 * sc), (cx - 0.6 * sc, cy + 0.1 * sc), (cx - 0.75 * sc, cy + 0.5 * sc)], fill=(255, 170, 140, 200), width=4, joint="curve")
    ad.line([(cx + 0.15 * sc, cy + 0.35 * sc), (cx + 0.6 * sc, cy + 0.25 * sc)], fill=(255, 170, 140, 200), width=4)
    ao = np.asarray(art.filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 255
    cv = cv * (1 - ao[..., 3:4] * a) + ao[..., :3] * 255 * ao[..., 3:4] * a
    paste(cv, glow(int(sc * 1.6), (255, 60, 60), 0.5), cx, cy + 0.1 * sc, 0.25 + 0.35 * beat, add=True)
    if scan:
        sy = cy - 1.1 * sc + (2.4 * sc) * ((t * 0.45) % 1.0)
        band = np.exp(-((_HY - sy) / 6) ** 2)[..., None]
        cv = cv + band * np.array([90, 220, 255], np.float32) * 0.9 * (0.4 + 0.6 * a)
        # ECG trace under the heart
        e = Image.new("RGBA", (w, h), (0, 0, 0, 0)); ed = ImageDraw.Draw(e)
        pts, y0 = [], cy + 1.55 * sc
        for x in range(30, w - 30, 2):
            ph = ((x / 170) - t * 1.05) % 1.0
            g = lambda c, wd, am: am * math.exp(-0.5 * ((ph - c) / wd) ** 2)
            v = g(0.3, 0.012, 1.0) - g(0.33, 0.012, 0.3) + g(0.5, 0.04, 0.25) + g(0.16, 0.03, 0.1)
            pts.append((x, y0 - v * 60))
        ed.line(pts, fill=(120, 230, 255, 230), width=3)
        eo = np.asarray(e.filter(ImageFilter.GaussianBlur(0.8))).astype(np.float32) / 255
        cv = cv + eo[..., :3] * 255 * eo[..., 3:4]
    return cv

SCENES = {"inhale": lambda t, d: scene_inhale(t, d), "airway": scene_airway, "alveoli": scene_alveoli,
          "blood": scene_blood, "artery": lambda t, d: scene_artery(t, d, "plaque"),
          "pressure": lambda t, d: scene_artery(t, d, "pressure"), "city": lambda t, d: scene_inhale(t, d, xray=False, dusk=0.6),
          "heart": lambda t, d: scene_heart(t, d), "scan": lambda t, d: scene_heart(t, d, scan=True)}

# ------------------------------------------------------------------ text (lower third) + label chips
def text_layer(lines, t, dur, cy=1440, hold=False):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    blocks = []
    for text, style in lines:
        big = style in ("big", "key", "red")
        f = font("anton", 110) if big else font("Medium", 50)
        words, rows, cur = text.split(), [], ""
        for w_ in words:
            tr = (cur + " " + w_).strip()
            if d.textlength(tr, font=f) > W - 150 and cur:
                rows.append(cur); cur = w_
            else:
                cur = tr
        rows.append(cur)
        col = {"big": WHITE, "key": CREAM, "red": RED}.get(style, WHITE)
        for r_ in rows:
            blocks.append((r_, f, col, 0.98 if big else 1.3))
    hts = [(b[1].getmetrics()[0] + b[1].getmetrics()[1]) * b[3] for b in blocks]
    y = cy - sum(hts) / 2
    out_a = 1.0 if hold else 1 - ease((t - (dur - 0.7)) / 0.7)
    for i, ((text, f, col, _), hh) in enumerate(zip(blocks, hts)):
        t_in = 0.35 + i * min(0.55, dur * 0.35 / max(len(blocks), 1))
        a = ease((t - t_in) / 0.8) * out_a
        rise = (1 - ease((t - t_in) / 1.2)) * 26 + t * 4
        if a > 0:
            d.text(((W - d.textlength(text, font=f)) / 2, y - rise), text, font=f, fill=col + (int(255 * a),))
        y += hh
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sh.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda v: min(255, int(v * 1.7))))
    sh.alpha_composite(img)
    return np.asarray(sh).astype(np.float32) / 255

def chips_layer(chips, t, dur):
    if not chips:
        return None
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for k, (text, x, y, ax, ay, t0) in enumerate(chips):
        a = ease((t - t0) / 0.5) * (1 - ease((t - (dur - 0.6)) / 0.6))
        if a > 0:
            chip(img, text, x, y, (ax, ay) if ax is not None else None, a)
    return np.asarray(img).astype(np.float32) / 255

# ------------------------------------------------------------------ build
SLIDES, (END_LINES, END_DUR) = C["SLIDES"], C["END"]
if os.environ.get("BIO_STILLS"):                       # quick review: one still per scene -> contact sheet
    tiles = []
    for scene, lines, dur, chips in SLIDES:
        ts = dur * 0.62
        fr = np.asarray(Image.fromarray(np.clip(SCENES[scene](ts, dur), 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)).astype(np.float32)
        yy_ = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        fr *= 1 - np.clip((yy_ - 0.55) / 0.35, 0, 1) * 0.55
        for L in (chips_layer(chips, ts, dur), text_layer(lines, ts, dur)):
            if L is not None:
                a_ = L[..., 3:4]; fr = fr * (1 - a_) + L[..., :3] * 255 * a_
        tiles.append(Image.fromarray(np.clip(fr, 0, 255).astype(np.uint8)).resize((270, 480)))
    sheet = Image.new("RGB", (270 * len(tiles), 480))
    for i, tl in enumerate(tiles):
        sheet.paste(tl, (i * 270, 0))
    sheet.save(os.environ["BIO_STILLS"]); print("stills ->", os.environ["BIO_STILLS"]); sys.exit(0)
XF = 0.8
starts, t = [], 0.0
for _, _, dur, _ in SLIDES:
    starts.append(t); t += dur - XF
END_START = t; TOTAL = END_START + END_DUR
print(f"{len(SLIDES)} scenes, total {TOTAL:.1f}s")
OUT = P(C.get("OUTPUT", "output/bio_9x16.mp4")); os.makedirs(os.path.dirname(OUT), exist_ok=True)
logo = Image.open(os.path.join(REPO, "assets", "logo_on_dark.png")); lw = 420
logo_l = np.asarray(logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)).astype(np.float32) / 255

# sound: low ambience, airflow whoosh in the lung scenes, heartbeat in the heart scenes
sr = 48000; n = int(TOTAL * sr); tt = np.arange(n) / sr
noise = np.random.default_rng(5).standard_normal(n).astype(np.float32)
rum = np.cumsum(noise); rum -= np.convolve(rum, np.ones(4800) / 4800, "same"); rum /= np.abs(rum).max() + 1e-9
mix = rum * 0.18 * (0.7 + 0.3 * np.sin(tt * 0.3))
air = noise - np.convolve(noise, np.ones(12) / 12, "same")                 # breathy band
for i, (scene, _, dur, _) in enumerate(SLIDES):
    s0, s1 = int(starts[i] * sr), int(min(TOTAL, starts[i] + dur) * sr)
    if scene in ("inhale", "airway", "alveoli"):
        env = np.clip(np.sin(np.linspace(0, math.pi, s1 - s0)) * (0.5 + 0.5 * np.sin(np.linspace(0, dur * 1.6, s1 - s0))), 0, 1)
        mix[s0:s1] += air[s0:s1] * env * 0.05
    if scene in ("artery", "pressure", "heart", "scan"):
        b = starts[i] + 0.3
        while b < starts[i] + dur - 0.3:
            for off, amp in ((0.0, 1.0), (0.22, 0.6)):
                q0, L = int((b + off) * sr), int(0.16 * sr)
                if q0 + L < n:
                    k = np.arange(L) / sr
                    mix[q0:q0 + L] += 0.5 * amp * np.sin(2 * np.pi * 52 * k) * np.exp(-k * 28)
            b += 0.95
mix *= np.minimum(1, np.minimum(tt / 1.0, (TOTAL - tt) / 1.5))
aud = os.path.join(TMP, "bio_sound.wav")
with wave.open(aud, "wb") as wf:
    wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(sr)
    wf.writeframes((np.clip(np.stack([mix, mix], 1), -1, 1) * 32767 * 0.8).astype("<i2").tobytes())

enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                        "-i", "-", "-i", aud, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
                        "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                        "-c:a", "aac", "-b:a", "192k", "-af", "loudnorm=I=-20:TP=-2", "-movflags", "+faststart",
                        "-shortest", OUT], stdin=subprocess.PIPE)
yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
SHADE = np.clip((yy - 0.55) / 0.35, 0, 1) * 0.55                           # lower-third darkening for the text
grain_rng = np.random.default_rng(9)
for fi in range(round(TOTAL * FPS)):
    t = fi / FPS
    acc, wsum = None, 0.0
    for i, (scene, lines, dur, chips) in enumerate(SLIDES):
        ts = t - starts[i]
        if -0.01 <= ts < dur:
            wgt = (ease(ts / XF) if i else 1.0) * (1 - ease((ts - (dur - XF)) / XF))
            if wgt > 0:
                fr = SCENES[scene](ts, dur)
                acc = fr * wgt if acc is None else acc + fr * wgt; wsum += wgt
    lo = acc / max(wsum, 1e-6) if acc is not None else np.full((h, w, 3), 10, np.float32)
    if t >= END_START - XF:
        e = ease((t - END_START + XF) / XF)
        lo = lo * (1 - e) + np.full((h, w, 3), 10, np.float32) * e
    fr = np.asarray(Image.fromarray(np.clip(lo, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)).astype(np.float32)
    fr *= 1 - SHADE
    for i, (scene, lines, dur, chips) in enumerate(SLIDES):
        ts = t - starts[i]
        if 0 <= ts < dur:
            for L in (chips_layer(chips, ts, dur), text_layer(lines, ts, dur)):
                if L is not None:
                    a = L[..., 3:4]; fr = fr * (1 - a) + L[..., :3] * 255 * a
    if t >= END_START:
        te = t - END_START
        L = text_layer(END_LINES, te, END_DUR, cy=900, hold=True)
        a = L[..., 3:4]; fr = fr * (1 - a) + L[..., :3] * 255 * a
        al = ease((te - 0.8) / 0.8)
        if al > 0:
            lh, lw_ = logo_l.shape[:2]; x0, y0 = (W - lw_) // 2, 1060
            a2 = logo_l[..., 3:4] * al
            roi = fr[y0:y0 + lh, x0:x0 + lw_]; roi[:] = roi * (1 - a2) + logo_l[..., :3] * 255 * a2
    g = grain_rng.standard_normal((H // 2, W // 2)).astype(np.float32) * 4
    fr += np.repeat(np.repeat(g, 2, 0), 2, 1)[..., None]
    enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait()
print("wrote", OUT)
