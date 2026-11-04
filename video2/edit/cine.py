"""Original cinematic CGI cutaways (no stock footage), rendered straight into HLG.

Each scene is rendered in display-linear light at half resolution (soft, filmic),
converted to HLG, upscaled, then gets type (if any) and film grain at full
resolution. Slow camera moves, shallow-focus bokeh, practical light sources.
"""
import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
LW, LH = 540, 960            # internal render size
FD = "/usr/share/fonts/opentype/inter/"
GOLD = (226, 196, 140)
WARM_WHITE = (246, 238, 226)

_M709_2020 = np.array([[0.6274, 0.3293, 0.0433],
                       [0.0691, 0.9195, 0.0114],
                       [0.0164, 0.0880, 0.8956]], np.float32)


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def lin_to_hlg(lin, white=0.203):
    """Display-linear (1.0 = SDR white) BT.709 -> HLG BT.2020, with a soft highlight shoulder."""
    x = np.maximum(lin, 0)
    x = x / (1 + x / 3.5)                       # filmic shoulder for bright practicals
    x = np.clip(x @ _M709_2020.T, 0, None)
    e = np.minimum(x * white, 1.0) ** (1 / 1.2)
    a, b, c = 0.17883277, 0.28466892, 0.55991073
    return np.where(e <= 1 / 12, np.sqrt(3 * e), a * np.log(np.maximum(12 * e - b, 1e-6)) + c).astype(np.float32)


def srgb_to_hlg(rgb, white=0.203):
    v = np.clip(rgb, 0, 1)
    lin = np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)
    lin = np.clip(lin @ _M709_2020.T, 0, 1)
    e = (lin * white) ** (1 / 1.2)
    a, b, c = 0.17883277, 0.28466892, 0.55991073
    return np.where(e <= 1 / 12, np.sqrt(3 * e), a * np.log(np.maximum(12 * e - b, 1e-6)) + c).astype(np.float32)


def upscale(arr):
    return np.stack([np.asarray(Image.fromarray(np.ascontiguousarray(arr[..., i]), "F").resize((W, H), Image.BICUBIC))
                     for i in range(3)], -1)


def box_blur(img, r):
    """Fast separable box blur (3 passes ~ gaussian). img: [h, w, c] float."""
    if r < 1:
        return img
    out = img
    for _ in range(3):
        for ax in (0, 1):
            pad = [(0, 0)] * out.ndim
            pad[ax] = (r + 1, r)
            p = np.pad(out, pad, mode="edge")
            cs = np.cumsum(p, axis=ax, dtype=np.float32)
            sl_hi = [slice(None)] * out.ndim
            sl_lo = [slice(None)] * out.ndim
            sl_hi[ax] = slice(2 * r + 1, None)
            sl_lo[ax] = slice(0, -(2 * r + 1))
            out = (cs[tuple(sl_hi)] - cs[tuple(sl_lo)]) / (2 * r + 1)
    return out


@lru_cache(maxsize=128)
def bokeh_kernel(r):
    r = max(2, int(r))
    yy, xx = np.mgrid[-r - 1:r + 2, -r - 1:r + 2].astype(np.float32)
    d = np.sqrt(xx ** 2 + yy ** 2) / r
    disc = np.clip((1.0 - d) / 0.08 + 0.5, 0, 1)                  # soft edge
    rim = 0.78 + 0.22 * np.clip((d - 0.55) / 0.4, 0, 1)            # slightly brighter rim, like real lenses
    return (disc * rim).astype(np.float32)


def stamp(canvas, x, y, k, col):
    h, w = k.shape
    x0, y0 = int(x) - w // 2, int(y) - h // 2
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, canvas.shape[1]), min(y0 + h, canvas.shape[0])
    if xb <= xa or yb <= ya:
        return
    canvas[ya:yb, xa:xb] += k[ya - y0:yb - y0, xa - x0:xb - x0, None] * col


@lru_cache(maxsize=64)
def font(name, size):
    return ImageFont.truetype(FD + name, int(size))


def tracked_layer(lines):
    """lines: list of (text, font, rgb, alpha, cy, track). Returns (HLG RGBA region, x, y) or None."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    for text, f, rgb, a, cy, track in lines:
        if a <= 0.003:
            continue
        widths = [d.textlength(ch, font=f) for ch in text]
        tw = sum(widths) + track * (len(text) - 1)
        x = W / 2 - tw / 2
        asc, desc = f.getmetrics()
        y = cy - (asc + desc) / 2
        for ch, wd in zip(text, widths):
            ds.text((x, y + 2), ch, font=f, fill=(0, 0, 0, int(140 * a)))
            d.text((x, y), ch, font=f, fill=rgb + (int(255 * a),))
            x += wd + track
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    sh.alpha_composite(img)
    bb = sh.getbbox()
    if not bb:
        return None
    reg = np.asarray(sh.crop(bb)).astype(np.float32) / 255
    reg[..., :3] = srgb_to_hlg(reg[..., :3], white=0.60)
    return reg, bb[0], bb[1]


def over(frame, layer, x, y, alpha=1.0):
    h, w = layer.shape[:2]
    roi = frame[y:y + h, x:x + w]
    a = layer[..., 3:4] * alpha
    roi[:] = roi * (1 - a) + layer[..., :3] * a


_rng_grain = np.random.default_rng(7)


def finish(lin_lowres, text_lines=None, grain=0.011):
    hlg = upscale(lin_to_hlg(lin_lowres))
    if text_lines:
        t = tracked_layer(text_lines)
        if t:
            over(hlg, *t)
    if grain:
        n = _rng_grain.standard_normal((H // 2, W // 2), dtype=np.float32) * grain
        n = np.repeat(np.repeat(n, 2, 0), 2, 1)[..., None]         # fine, slightly soft grain
        hlg = hlg + n * (0.35 + hlg)
    return np.clip(hlg, 0, 1)


def ecg_wave(phase):
    p = phase % 1.0
    g = lambda c, w, a: a * math.exp(-0.5 * ((p - c) / w) ** 2)
    return g(0.16, 0.025, 0.10) + g(0.29, 0.007, -0.12) + g(0.31, 0.009, 1.0) + \
        g(0.335, 0.010, -0.28) + g(0.53, 0.040, 0.24)


def draw_trace(canvas, t, cy, amp, col, beat, span, x0, x1, width=2.2, cam=(1.0, 0, 0)):
    """Monitor sweep trace drawn additively into a low-res linear canvas."""
    sweep = (t / (beat * span)) % 1.0
    xs = np.arange(x0, x1, 0.7)
    frac = (xs - x0) / (x1 - x0)
    age = (sweep - frac) % 1.0
    tw = t - age * beat * span
    ys = cy - amp * np.array([ecg_wave(v / beat) for v in tw])
    fade = np.clip(1.0 - age * 1.05, 0, 1) ** 1.4
    gap = (age < 0.012)
    s, ox, oy = cam
    img = np.zeros(canvas.shape[:2], np.float32)
    px = ((xs - LW / 2) * s + LW / 2 + ox).astype(int)
    py = ((ys - LH / 2) * s + LH / 2 + oy)
    for i in range(len(xs) - 1):
        if gap[i]:
            continue
        ya, yb = py[i], py[i + 1]
        lo, hi = int(min(ya, yb) - width), int(max(ya, yb) + width) + 1
        x = px[i]
        if 0 <= x < LW:
            lo, hi = max(lo, 0), min(hi, LH)
            img[lo:hi, x] = np.maximum(img[lo:hi, x], fade[i])
    core = box_blur(img[..., None], 1)
    glow = box_blur(img[..., None], 6)
    canvas += core * col * 1.6 + glow * col * 0.9
    # write head
    hx = ((x0 + (x1 - x0) * sweep - LW / 2) * s + LW / 2 + ox)
    hy = ((cy - amp * ecg_wave(t / beat) - LH / 2) * s + LH / 2 + oy)
    stamp(canvas, hx, hy, bokeh_kernel(5), np.array(col) * 1.5)


# ================================================================== scene A: lives (bokeh)
class Lives:
    """Warm out-of-focus lights in the dark. They go out one by one ('lives lost');
    at '80% preventable' most of them softly relight."""

    def __init__(self, t_millions, t_80, t_prev, dur, seed=3):
        self.t_m, self.t_80, self.t_prev, self.dur = t_millions, t_80, t_prev, dur
        rng = np.random.default_rng(seed)
        n = 150
        self.z = rng.uniform(0.0, 1.0, n) ** 0.8                  # depth (1 = far)
        self.x = rng.uniform(-80, LW + 80, n)
        self.y = rng.normal(LH * 0.52, LH * 0.22, n).clip(30, LH - 30)
        self.r = 5 + 52 * (1 - self.z) ** 2.0
        warm = np.array([[1.0, 0.58, 0.26], [1.0, 0.68, 0.36], [1.0, 0.80, 0.55], [0.98, 0.90, 0.80]], np.float32)
        self.col = warm[rng.choice(4, n, p=[0.35, 0.35, 0.2, 0.1])]
        self.i = rng.uniform(0.25, 0.9, n) * (0.35 + 0.65 * self.z) ** -0.2 * 0.55
        self.ph = rng.uniform(0, 6.28, n)
        # 55% of the lights go out between 'millions' and '80%'
        self.dies = rng.uniform(0, 1, n) < 0.55
        self.t_die = rng.uniform(t_millions - 0.4, t_80 - 0.2, n)
        # at '80%', 80% of the lost lights come back (staggered)
        self.back = self.dies & (rng.uniform(0, 1, n) < 0.80)
        self.t_back = rng.uniform(t_80, t_80 + 1.6, n)

    def __call__(self, t):
        cv = np.zeros((LH, LW, 3), np.float32)
        yy = np.linspace(0, 1, LH, dtype=np.float32)[:, None, None]
        cv += np.array([0.030, 0.022, 0.017], np.float32) * (0.7 + 0.6 * np.exp(-((yy - 0.6) / 0.35) ** 2))  # warm haze
        s = 1.0 + 0.07 * (t / self.dur)                                        # slow push-in
        drift = -5.0 * t
        for k in range(len(self.x)):
            a = 1.0
            if self.dies[k]:
                a = 1 - ease((t - self.t_die[k]) / 0.9)
                if self.back[k]:
                    a = max(a, ease((t - self.t_back[k]) / 1.1))
            if a <= 0.01:
                continue
            tw = 0.88 + 0.12 * math.sin(t * 1.3 + self.ph[k])
            x = (self.x[k] + drift / (0.4 + self.z[k]) - LW / 2) * s + LW / 2
            y = (self.y[k] - LH / 2) * s + LH / 2
            stamp(cv, x, y, bokeh_kernel(self.r[k] * s), self.col[k] * self.i[k] * a * tw)
        cv = cv + box_blur(cv, 18) * 0.35                                     # glow / atmosphere
        cv *= 1.35
        fm = font("InterDisplay-Light.otf", 112)
        fs = font("Inter-Medium.otf", 30)
        a_m = ease((t - self.t_m) / 0.8) * (1 - ease((t - self.t_80 + 0.5) / 0.4))
        a_80 = ease((t - self.t_80) / 0.6)
        a_p = ease((t - self.t_prev) / 0.6)
        lines = [("MILLIONS", fm, GOLD, a_m, 600, 26),
                 ("80%", font("InterDisplay-Light.otf", 190), GOLD, a_80, 560, 10),
                 ("PREVENTABLE", fs, WARM_WHITE, a_p * 0.9, 700, 12)]
        return finish(cv, lines)


# ================================================================== scene B: ICU monitor, 59,000 today
class Monitor:
    def __init__(self, t_count, t_today, dur, number=True, beat=0.85, calm=False, seed=5):
        self.t_count, self.t_today, self.dur, self.number = t_count, t_today, dur, number
        self.beat, self.calm = beat, calm
        rng = np.random.default_rng(seed)
        self.leds = [(rng.uniform(40, 500), rng.uniform(120, 520), rng.uniform(3, 9),
                      [np.array([0.9, 0.15, 0.1]), np.array([0.2, 0.9, 0.4]), np.array([1.0, 0.6, 0.2])][rng.integers(0, 3)],
                      rng.uniform(0.15, 0.5)) for _ in range(9)]
        self.dust = np.stack([rng.uniform(0, LW, 70), rng.uniform(0, LH, 70), rng.uniform(0.6, 2.2, 70),
                              rng.uniform(4, 14, 70), rng.uniform(0, 6.28, 70)], 1)
        base = np.zeros((LH, LW, 3), np.float32)
        yy = np.linspace(0, 1, LH, dtype=np.float32)[:, None, None]
        base += np.array([0.012, 0.017, 0.019], np.float32) * (1.25 - 0.6 * yy)
        # out-of-focus monitor glow behind (upper right) and a cold window strip (left)
        g = np.zeros((LH, LW, 1), np.float32)
        g[150:330, 300:500] = 1.0
        base += box_blur(g, 26) * np.array([0.05, 0.11, 0.10], np.float32)
        g2 = np.zeros((LH, LW, 1), np.float32)
        g2[60:700, 0:40] = 1.0
        base += box_blur(g2, 30) * np.array([0.03, 0.04, 0.055], np.float32)
        self.base = base

    def __call__(self, t):
        u = t / self.dur
        s = 1.0 + 0.06 * u
        cam = (s, -6 * u, 0)
        cv = self.base.copy()
        for x, y, r, c, i in self.leds:
            stamp(cv, (x - LW / 2) * s + LW / 2 - 8 * u, (y - LH / 2) * s + LH / 2, bokeh_kernel(r * 2.2 * s), c * i * 0.5)
        col = np.array([0.85, 0.95, 0.88] if self.calm else [0.35, 1.0, 0.62], np.float32)
        draw_trace(cv, t, 640, 85 if not self.calm else 70, col * (0.55 if self.calm else 0.6),
                   self.beat, 2.4, 30, LW - 30, cam=cam)
        for x, y, r, sp, ph in self.dust:
            yv = (y - sp * 6 * t) % LH
            xv = x + 6 * math.sin(t * 0.5 + ph)
            stamp(cv, xv, yv, bokeh_kernel(r * 0.35 + 1), np.array([0.05, 0.06, 0.06]) * (0.5 + 0.5 * math.sin(t + ph)))
        cv = cv * 2.6 + box_blur(cv, 14) * 0.5
        lines = None
        if self.number:
            n = int(round(ease_out((t - self.t_count) / 1.8) * 59000))
            a = ease((t - self.t_count + 0.1) / 0.6)
            lines = [(f"{n:,}", font("InterDisplay-Light.otf", 200), GOLD, a, 520, 6),
                     ("TODAY", font("Inter-Medium.otf", 32), WARM_WHITE, ease((t - self.t_today) / 0.6) * 0.9, 680, 14)]
        return finish(cv, lines)


# ================================================================== scene C: days passing (window light)
class Days:
    LABELS = ["TOMORROW", "THE DAY AFTER", "AND THE DAY AFTER THAT"]

    def __init__(self, t_days, t_total, dur, seed=9):
        self.t_days, self.t_total, self.dur = t_days, t_total, dur
        rng = np.random.default_rng(seed)
        tex = rng.standard_normal((LH, LW, 1)).astype(np.float32)
        tex = box_blur(tex, 2) * 0.35 + box_blur(tex, 12) * 1.2
        self.wall = (np.array([0.040, 0.032, 0.027], np.float32) * (1 + 0.25 * tex))
        yy, xx = np.mgrid[0:LH, 0:LW].astype(np.float32)
        self.xx, self.yy = xx, yy

    def light(self, t):
        """Blind-slatted sunlight patch that slides across the wall once per day."""
        bounds = self.t_days + [self.dur + 0.5]
        k = max(i for i, b in enumerate(bounds[:-1]) if t >= b - 0.6) if t >= bounds[0] - 0.6 else 0
        t0, t1 = bounds[k] - 0.6, bounds[k + 1] - 0.6
        u = min(max((t - t0) / max(t1 - t0, 0.5), 0), 1)
        cx = -120 + (LW + 240) * u
        inten = math.sin(math.pi * u) ** 0.8
        ang = math.radians(14)
        xr = (self.xx - cx) * math.cos(ang) + (self.yy - 480) * math.sin(ang)
        yr = -(self.xx - cx) * math.sin(ang) + (self.yy - 480) * math.cos(ang)
        win = np.clip(1 - np.maximum(np.abs(xr) / 230, np.abs(yr) / 380), 0, 1)
        win = np.clip(win * 4, 0, 1)
        slats = np.clip((np.sin(yr / 14.0) + 0.55) * 2.2, 0, 1)
        m = (win * (0.25 + 0.75 * slats))[..., None]
        m = box_blur(m, 5)
        return m * inten

    def __call__(self, t):
        cv = self.wall.copy()
        L = self.light(t)
        cv += L * np.array([0.95, 0.70, 0.42], np.float32)
        cv += box_blur(L, 40) * np.array([0.22, 0.16, 0.10], np.float32)  # warm bounce into the room
        cv *= 1.5
        k = sum(t >= td - 0.05 for td in self.t_days)
        total = t >= self.t_total
        lines = []
        f_big = font("InterDisplay-Light.otf", 200)
        if not total:
            lines.append(("59,000", f_big, GOLD, 1.0, 520, 6))
        else:
            u = ease_out((t - self.t_total) / 1.2)
            n = int(round(59000 + (236000 - 59000) * u))
            lines.append((f"{n:,}", f_big, GOLD, 1.0, 520, 6))
            lines.append(("IN JUST FOUR DAYS", font("Inter-Medium.otf", 32), WARM_WHITE, ease((t - self.t_total - 0.3) / 0.6) * 0.9, 680, 12))
        for i, lab in enumerate(self.LABELS):
            if total:
                break
            a_in = ease((t - self.t_days[i]) / 0.45)
            a_out = 1 - ease((t - self.t_days[i + 1] + 0.1) / 0.3) if i + 1 < len(self.t_days) else 1 - ease((t - self.t_total + 0.15) / 0.3)
            a = a_in * a_out
            if a > 0:
                lines.append((lab, font("Inter-Medium.otf", 32), WARM_WHITE, a * 0.9, 680, 12))
        return finish(cv, lines)


# ================================================================== scene D: ceiling lights overhead
class Ceiling:
    """Point of view from a hospital trolley: ceiling lights slide overhead."""

    def __init__(self, dur, seed=11):
        self.dur = dur
        rng = np.random.default_rng(seed)
        tex = rng.standard_normal((LH, LW, 1)).astype(np.float32)
        self.ceil = np.array([0.030, 0.033, 0.035], np.float32) * (1 + 0.15 * box_blur(tex, 10) * 3)
        yy = np.linspace(0, 1, LH, dtype=np.float32)[:, None, None]
        self.grad = 0.55 + 0.75 * yy                                     # nearer = brighter
        self.n, self.speed = 5, 0.42

    def __call__(self, t):
        cv = self.ceil * self.grad
        L = np.zeros((LH, LW, 1), np.float32)
        for k in range(self.n):
            p = (t * self.speed + k / self.n) % 1.0                      # 0 far (top) -> 1 overhead (bottom)
            sc = 0.25 + 1.6 * p ** 1.5
            y = -40 + (LH + 160) * p ** 1.35
            w, h = 150 * sc, 52 * sc
            x = LW / 2 + 10 * math.sin(t * 0.4) + (y - LH / 2) * 0.10     # slight diagonal, like a tilted head
            y0, y1, x0, x1 = int(y - h / 2), int(y + h / 2), int(x - w / 2), int(x + w / 2)
            ya, yb, xa, xb = max(y0, 0), min(y1, LH), max(x0, 0), min(x1, LW)
            if yb > ya and xb > xa:
                # taper: the far edge (top) of each panel is narrower, as in perspective
                for yy_ in range(ya, yb):
                    v = (yy_ - y0) / max(y1 - y0, 1)
                    half = w / 2 * (0.82 + 0.18 * v)
                    xa_, xb_ = max(int(x - half), 0), min(int(x + half), LW)
                    L[yy_, xa_:xb_] += min(1.0, p * 3)
        blur_v = 4 + int(10 * self.speed)
        Lb = box_blur(L, 5)                                              # shallow focus: lights are soft
        # vertical motion streak
        Lm = Lb.copy()
        for k in range(1, blur_v + 1):
            Lm[k:] += Lb[:-k] * (1 - k / (blur_v + 1))
        Lm /= 1 + sum(1 - k / (blur_v + 1) for k in range(1, blur_v + 1)) * 0.6
        col = np.array([0.92, 0.98, 1.0], np.float32)
        cv = cv + Lm * col * 1.4 + box_blur(Lm, 22) * col * 0.55 + box_blur(Lm, 60) * col * 0.25
        cv *= np.array([1.03, 1.0, 0.96], np.float32) * 1.45               # sit warm, like the speaker footage
        return finish(cv)
